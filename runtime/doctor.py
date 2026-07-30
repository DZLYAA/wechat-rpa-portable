import json
import importlib.util
import shutil
import sys
from pathlib import Path

from portable_common import (
    APP_CONFIG_PATH,
    SECRETS_PATH,
    call_ciphertalk,
    load_config,
    load_secrets,
    log_status,
)


def check(online=True):
    result = {"ok": True, "checks": {}}

    def item(name, ok, detail=""):
        result["checks"][name] = {"ok": bool(ok), "detail": detail}
        if not ok:
            result["ok"] = False

    item(
        "appConfig",
        APP_CONFIG_PATH.exists(),
        "已配置" if APP_CONFIG_PATH.exists() else "请运行 setup.exe",
    )
    item(
        "encryptedSecrets",
        SECRETS_PATH.exists(),
        "DPAPI 文件存在" if SECRETS_PATH.exists() else "缺少 secrets.dat",
    )
    if not result["ok"]:
        return result

    try:
        config = load_config()
        secrets = load_secrets()
        key = str(secrets.get("decryptKey") or "")
        item(
            "decryptKeyFormat",
            len(key) == 64 and all(character in "0123456789abcdefABCDEF" for character in key),
            "仅校验格式，不输出密钥",
        )
        item(
            "ciphertalkRoot",
            Path(config.get("ciphertalkRoot") or "").is_dir(),
            "",
        )
        item(
            "wechatDbPath", Path(config.get("wechatDbPath") or "").is_dir(), ""
        )
        item(
            "ciphertalkConfigDb",
            Path(config["ciphertalkConfigDbResolved"]).is_file(),
            "",
        )
        item("excelPath", Path(config["excelPathResolved"]).is_file(), "")
        office_roots = (
            Path(r"C:\Program Files\Microsoft Office"),
            Path(r"C:\Program Files (x86)\Microsoft Office"),
        )
        excel_installed = bool(
            shutil.which("EXCEL.EXE") or any(path.exists() for path in office_roots)
        )
        openpyxl_available = importlib.util.find_spec("openpyxl") is not None
        item(
            "excelWriter",
            excel_installed or openpyxl_available,
            (
                "检测到 Excel COM"
                if excel_installed
                else "使用内置 openpyxl 兼容写入"
                if openpyxl_available
                else "未检测到 Excel COM 或 openpyxl"
            ),
        )
        item("shadowbot", Path(r"C:\Program Files\ShadowBot").exists(), "")
        if online:
            try:
                data = call_ciphertalk(
                    "list_sessions", {"offset": 0, "limit": 1}, config=config, timeout=10
                )
                item(
                    "ciphertalkMcp",
                    True,
                    f"会话接口可用，总数={data.get('total', 'unknown')}",
                )
            except Exception as error:
                item("ciphertalkMcp", False, str(error))
    except Exception as error:
        item("configuration", False, str(error))
    return result


if __name__ == "__main__":
    report = check(online="--offline" not in sys.argv)
    log_status("doctor.json", report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(0 if report["ok"] else 1)
