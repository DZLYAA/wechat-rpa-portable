import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
RUNTIME = ROOT / "runtime"
LOGS = ROOT / "logs"


def find_python():
    current = Path(sys.executable)
    if current.name.lower() in ("python.exe", "pythonw.exe") and current.is_file():
        console_python = current.with_name("python.exe")
        return console_python if console_python.is_file() else current
    shadowbot_root = Path(r"C:\Program Files\ShadowBot")
    if shadowbot_root.exists():
        matches = sorted(
            shadowbot_root.glob("shadowbot-*\\python\\python.exe"), reverse=True
        )
        if matches:
            return matches[0]
    raise RuntimeError("找不到 Python 运行环境")


def main():
    action = sys.argv[1].lower() if len(sys.argv) > 1 else "collect"
    script = RUNTIME / ("ack.py" if action == "ack" else "collector.py")
    LOGS.mkdir(parents=True, exist_ok=True)
    startup = subprocess.STARTUPINFO()
    startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startup.wShowWindow = subprocess.SW_HIDE
    result = subprocess.run(
        [str(find_python()), str(script)],
        cwd=str(RUNTIME),
        creationflags=subprocess.CREATE_NO_WINDOW,
        startupinfo=startup,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    (LOGS / f"{action}_exit_code.txt").write_text(str(result.returncode), encoding="ascii")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
