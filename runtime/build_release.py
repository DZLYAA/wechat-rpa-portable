import shutil
import hashlib
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT.parent
ZIP_PATH = OUTPUT_DIR / "wechat-rpa-portable-with-ciphertalk-v1.1.zip"
EXCLUDED_NAMES = {
    "app.json",
    "secrets.dat",
    "wechat_messages.xlsx",
    "collector_state.json",
    "new_messages.json",
}
EXCLUDED_PARTS = {"logs", "__pycache__", "ciphertalk-cache"}
EXCLUDED_SUFFIXES = {".pyc", ".tmp"}


def include(path):
    relative = path.relative_to(ROOT)
    if any(part in EXCLUDED_PARTS for part in relative.parts):
        return False
    if path.name in EXCLUDED_NAMES or path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    if ".before_" in path.name.lower():
        return False
    return path.is_file()


def validate_stage(stage):
    forbidden = []
    for path in stage.rglob("*"):
        if path.is_file() and (
            path.name in EXCLUDED_NAMES
            or path.suffix.lower() == ".pyc"
            or "logs" in path.parts
        ):
            forbidden.append(str(path.relative_to(stage)))
    if forbidden:
        raise RuntimeError("隐私清理失败：" + ", ".join(forbidden))
    required = (
        "setup.exe",
        "collect_silent.exe",
        "ack_silent.exe",
        "doctor.exe",
        "1-安装密语.exe",
        "vendor/ciphertalk/CipherTalk-2026.729.0-Setup.exe",
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
