import ctypes
import json
import os
import shutil
import sqlite3
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from ctypes import wintypes
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PACKAGE_ROOT / "config"
DATA_DIR = PACKAGE_ROOT / "data"
LOG_DIR = PACKAGE_ROOT / "logs"
STATE_DIR = PACKAGE_ROOT / "state"
APP_CONFIG_PATH = CONFIG_DIR / "app.json"
APP_EXAMPLE_PATH = CONFIG_DIR / "app.example.json"
SECRETS_PATH = CONFIG_DIR / "secrets.dat"


class DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


def ensure_dirs():
    for directory in (CONFIG_DIR, DATA_DIR, LOG_DIR, STATE_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def expand_path(value, base=PACKAGE_ROOT):
    text = os.path.expandvars(str(value or "").strip())
    if not text:
        return None
    path = Path(text).expanduser()
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def load_config(require=True):
    ensure_dirs()
    source = APP_CONFIG_PATH if APP_CONFIG_PATH.exists() else APP_EXAMPLE_PATH
    if require and not APP_CONFIG_PATH.exists():
        raise RuntimeError("尚未完成配置，请先运行 setup.exe")
    data = json.loads(source.read_text(encoding="utf-8-sig"))
    excel_path = expand_path(data.get("excelPath") or r"data\wechat_messages.xlsx")
    config_db = expand_path(
        data.get("ciphertalkConfigDb")
        or r"%APPDATA%\ciphertalk\ciphertalk-config.db"
    )
    data["packageRoot"] = str(PACKAGE_ROOT)
    data["excelPathResolved"] = str(excel_path)
    data["ciphertalkConfigDbResolved"] = str(config_db)
    return data


def save_config(data):
    ensure_dirs()
    generated = {"packageRoot", "excelPathResolved", "ciphertalkConfigDbResolved"}
    clean = {key: value for key, value in data.items() if key not in generated}
    atomic_write_json(APP_CONFIG_PATH, clean)


def _blob(data):
    if not data:
        return None, DataBlob(0, None)
    buffer = (ctypes.c_ubyte * len(data)).from_buffer_copy(data)
    return buffer, DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))


def _local_free(pointer):
    ctypes.windll.kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    ctypes.windll.kernel32.LocalFree.restype = ctypes.c_void_p
    ctypes.windll.kernel32.LocalFree(pointer)


def protect_bytes(data):
    buffer, input_blob = _blob(data)
    output_blob = DataBlob()
    description = "wechat-rpa-portable"
    ok = ctypes.windll.crypt32.CryptProtectData(
        ctypes.byref(input_blob),
        description,
        None,
        None,
        None,
        0,
        ctypes.byref(output_blob),
    )
    if not ok:
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        _local_free(output_blob.pbData)


def unprotect_bytes(data):
    buffer, input_blob = _blob(data)
    output_blob = DataBlob()
    ok = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(input_blob), None, None, None, None, 0, ctypes.byref(output_blob)
    )
    if not ok:
        raise ctypes.WinError()
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        _local_free(output_blob.pbData)


def save_secrets(secrets):
    ensure_dirs()
    raw = json.dumps(secrets, ensure_ascii=False).encode("utf-8")
    SECRETS_PATH.write_bytes(protect_bytes(raw))


def load_secrets(require=True):
    if not SECRETS_PATH.exists():
        if require:
            raise RuntimeError("缺少加密密钥配置，请先运行 setup.exe")
        return {}
    return json.loads(unprotect_bytes(SECRETS_PATH.read_bytes()).decode("utf-8"))


def atomic_write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(temp, path)


def read_json(path, default=None):
    path = Path(path)
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8-sig"))


def log_status(name, data):
    ensure_dirs()
    safe = dict(data)
    for key in list(safe):
        if any(word in key.lower() for word in ("key", "token", "secret")):
            safe[key] = "[redacted]"
    atomic_write_json(LOG_DIR / name, safe)


def load_ciphertalk_proxy(config):
    db_path = Path(config["ciphertalkConfigDbResolved"])
    if not db_path.is_file():
        raise RuntimeError("找不到 CipherTalk 配置数据库")
    connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        rows = dict(
            connection.execute(
                "select key, value from config "
                "where key in ('mcpProxyToken','mcpProxyPort')"
            ).fetchall()
        )
    finally:
        connection.close()
    if "mcpProxyToken" not in rows:
        raise RuntimeError("CipherTalk 尚未生成 MCP 访问令牌，请先启动一次 CipherTalk")
    return json.loads(rows["mcpProxyToken"]), json.loads(rows.get("mcpProxyPort", "5032"))


def call_ciphertalk(tool, args, config=None, timeout=60):
    config = config or load_config()
    token, port = load_ciphertalk_proxy(config)
    request = urllib.request.Request(
        f"http://127.0.0.1:{port}/tool/{tool}",
        data=json.dumps({"args": args}).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        try:
            result = json.loads(error.read().decode("utf-8"))
        except Exception:
            raise RuntimeError(f"CipherTalk HTTP {error.code}") from error
    if not result.get("success"):
        details = result.get("error") or {}
        failure = RuntimeError(details.get("message") or f"CipherTalk tool failed: {tool}")
        failure.code = details.get("code") or "CIPHERTALK_ERROR"
        raise failure
    return result.get("data") or {}


def is_ciphertalk_ready(config):
    try:
        call_ciphertalk(
            "list_sessions", {"offset": 0, "limit": 1}, config=config, timeout=10
        )
        return True
    except Exception:
        return False


def default_start_command(config):
    root_value = str(config.get("ciphertalkRoot") or "").strip()
    if not root_value:
        return ""
    root = expand_path(root_value)
    candidates = [root / "start-dev.bat", root / "CipherTalk.exe"]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return ""


def start_ciphertalk(config):
    command = str(
        config.get("ciphertalkStartCommand") or default_start_command(config)
    ).strip()
    if not command:
        raise RuntimeError("未配置 CipherTalk 启动命令")

    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    flags = subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP
    exact_path = Path(command.strip('"'))
    if exact_path.is_file() and exact_path.suffix.lower() in (".bat", ".cmd"):
        args = ["cmd.exe", "/d", "/c", "call", str(exact_path)]
    elif exact_path.is_file():
        args = [str(exact_path)]
    else:
        args = ["cmd.exe", "/d", "/s", "/c", command]
    root = expand_path(config.get("ciphertalkRoot")) or PACKAGE_ROOT
    subprocess.Popen(
        args,
        cwd=str(root),
        startupinfo=startup,
        creationflags=flags,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )


def ensure_ciphertalk_ready(config=None):
    config = config or load_config()
    if is_ciphertalk_ready(config):
        return {"ok": True, "started": False}
    if not config.get("autoStartCipherTalk", True):
        raise RuntimeError("CipherTalk 未就绪，且自动启动已关闭")
    start_ciphertalk(config)
    deadline = time.monotonic() + int(config.get("mcpReadyTimeoutSeconds", 90))
    while time.monotonic() < deadline:
        time.sleep(2)
        if is_ciphertalk_ready(config):
            return {"ok": True, "started": True}
    raise RuntimeError("CipherTalk 就绪超时")


def upsert_ciphertalk_configuration(config, secrets):
    db_path = Path(config["ciphertalkConfigDbResolved"])
    if not db_path.is_file():
        raise RuntimeError("找不到 CipherTalk 配置数据库，请先启动一次 CipherTalk")

    now_ms = int(time.time() * 1000)
    wxid = str(config.get("wxid") or "").strip()
    account_id = f"portable-{uuid.uuid5(uuid.NAMESPACE_URL, wxid)}"
    account = {
        "id": account_id,
        "wxid": wxid,
        "dbPath": str(config.get("wechatDbPath") or ""),
        "decryptKey": str(secrets.get("decryptKey") or ""),
        "cachePath": str(DATA_DIR / "ciphertalk-cache"),
        "imageXorKey": str(secrets.get("imageXorKey") or ""),
        "imageAesKey": str(secrets.get("imageAesKey") or ""),
        "wechatNumber": "",
        "phone": "",
        "displayName": wxid,
        "createdAt": now_ms,
        "updatedAt": now_ms,
        "lastUsedAt": now_ms,
    }

    backup_dir = db_path.parent / "wechat-rpa-backups"
    backup_dir.mkdir(exist_ok=True)
    backup_path = backup_dir / f"ciphertalk-config-{time.strftime('%Y%m%d-%H%M%S')}.db"
    shutil.copy2(db_path, backup_path)

    connection = sqlite3.connect(str(db_path), timeout=10)
    try:
        existing_row = connection.execute(
            "select value from config where key='accounts'"
        ).fetchone()
        accounts = json.loads(existing_row[0]) if existing_row else []
        accounts = [
            item
            for item in accounts
            if str(item.get("wxid") or "") != wxid
            and str(item.get("id") or "") != account_id
        ]
        accounts.append(account)
        values = {
            "accounts": accounts,
            "activeAccountId": account["id"],
            "dbPath": account["dbPath"],
            "lastOpenedDb": account["dbPath"],
            "decryptKey": account["decryptKey"],
            "imageXorKey": account["imageXorKey"],
            "imageAesKey": account["imageAesKey"],
            "myWxid": wxid,
            "cachePath": account["cachePath"],
            "mcpEnabled": True,
            "mcpExposeMediaPaths": bool(config.get("includeMediaPaths", True)),
        }
        for key, value in values.items():
            connection.execute(
                "insert into config(key,value) values(?,?) "
                "on conflict(key) do update set value=excluded.value",
                (key, json.dumps(value, ensure_ascii=False)),
            )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()
    return backup_path


def initialize_state():
    ensure_dirs()
    atomic_write_json(
        STATE_DIR / "collector_state.json",
        {
            "initialized": False,
            "sessions": {},
            "pending": [],
            "schemaVersion": 1,
        },
    )
    atomic_write_json(
        STATE_DIR / "new_messages.json",
        {
            "ok": True,
            "data": {"messages": []},
            "meta": {"total": 0, "initialized": False},
        },
    )


def copy_excel_template_if_needed():
    config = load_config()
    target = Path(config["excelPathResolved"])
    template = DATA_DIR / "wechat_messages_template.xlsx"
    if not template.is_file():
        raise RuntimeError("安装包缺少 Excel 模板")
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        shutil.copy2(template, target)
    return target
