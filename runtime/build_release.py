import hashlib
import re
import shutil
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT.parent
ZIP_PATH = OUTPUT_DIR / "wechat-rpa-portable-v1.2.zip"
EXCLUDED_NAMES = {
    "app.json",
    "secrets.dat",
    "wechat_messages.xlsx",
    "collector_state.json",
    "new_messages.json",
}
EXCLUDED_PARTS = {".git", "logs", "state", "__pycache__", "ciphertalk-cache"}
EXCLUDED_SUFFIXES = {".pyc", ".tmp", ".db", ".db-wal", ".db-shm"}
TEXT_SUFFIXES = {
    ".bat", ".cfg", ".cmd", ".cs", ".css", ".html", ".ini", ".js",
    ".json", ".md", ".ps1", ".py", ".toml", ".txt", ".yaml", ".yml",
}
SENSITIVE_PATTERNS = {
    "real wxid": re.compile(r"wxid_[A-Za-z0-9]{8,}"),
    "assigned key": re.compile(
        r"(?i)(keyHex|databaseKey|xorKey|aesKey|dbKey)[^\r\n]{0,40}[0-9a-f]{32,}"
    ),
    "personal absolute path": re.compile(
        r"(?i)C:[\\/]+Users[\\/]+Administrator[\\/]+(Documents|Desktop|Downloads|AppData)"
    ),
}


def is_ciphertalk_installer(path):
    return path.name.startswith("CipherTalk-") and path.name.endswith("-Setup.exe")


def include(path):
    relative = path.relative_to(ROOT)
    if any(part in EXCLUDED_PARTS for part in relative.parts):
        return False
    if path.name in EXCLUDED_NAMES or path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    if is_ciphertalk_installer(path) or ".before_" in path.name.lower():
        return False
    return path.is_file()


def validate_stage(stage):
    forbidden = []
    sensitive = []
    for path in stage.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(stage)
        if (
            path.name in EXCLUDED_NAMES
            or path.suffix.lower() in EXCLUDED_SUFFIXES
            or any(part in EXCLUDED_PARTS for part in relative.parts)
            or is_ciphertalk_installer(path)
            or ".before_" in path.name.lower()
        ):
            forbidden.append(relative.as_posix())
            continue
        if path.suffix.lower() in TEXT_SUFFIXES and path.stat().st_size <= 5 * 1024 * 1024:
            content = path.read_text(encoding="utf-8", errors="replace")
            for label, pattern in SENSITIVE_PATTERNS.items():
                if pattern.search(content):
                    sensitive.append(f"{relative.as_posix()} ({label})")
    if forbidden:
        raise RuntimeError("隐私或第三方安装文件清理失败：" + ", ".join(forbidden))
    if sensitive:
        raise RuntimeError("敏感内容检查失败：" + ", ".join(sensitive))

    required = (
        "LICENSE",
        "SECURITY.md",
        "setup.exe",
        "collect_silent.exe",
        "ack_silent.exe",
        "doctor.exe",
        "1-安装密语.exe",
        "tools/download-ciphertalk-installer.ps1",
        "vendor/ciphertalk/LICENSE.txt",
        "vendor/ciphertalk/manifest.json",
        "config/app.example.json",
        "data/wechat_messages_template.xlsx",
        "shadowbot/module1.py",
        "README.md",
    )
    missing = [name for name in required if not (stage / name).is_file()]
    if missing:
        raise RuntimeError("安装包缺少文件：" + ", ".join(missing))


def write_checksums(stage):
    lines = []
    for path in sorted(stage.rglob("*")):
        if path.is_file() and path.name != "SHA256SUMS.txt":
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            relative = path.relative_to(stage).as_posix()
            lines.append(f"{digest}  {relative}")
    (stage / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    with tempfile.TemporaryDirectory(prefix="wechat-rpa-release-") as temp:
        stage = Path(temp) / "wechat-rpa-portable"
        for path in ROOT.rglob("*"):
            if include(path):
                target = stage / path.relative_to(ROOT)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(path, target)
        validate_stage(stage)
        write_checksums(stage)
        with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(stage.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(stage.parent))
    print(ZIP_PATH)


if __name__ == "__main__":
    main()
