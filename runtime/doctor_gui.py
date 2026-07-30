import json
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox


ROOT = Path(__file__).resolve().parent.parent


def main():
    python = Path(sys.executable)
    if python.name.lower() == "pythonw.exe" and python.with_name("python.exe").is_file():
        python = python.with_name("python.exe")
    result = subprocess.run(
        [str(python), str(ROOT / "runtime" / "doctor.py")],
        cwd=str(ROOT / "runtime"),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    try:
        report = json.loads(result.stdout)
        lines = []
        for name, item in report.get("checks", {}).items():
            state = "通过" if item.get("ok") else "失败"
            detail = str(item.get("detail") or "")
            lines.append(f"[{state}] {name}" + (f"：{detail}" if detail else ""))
        text = "\n".join(lines) or "未生成检测结果"
        title = "环境检测通过" if report.get("ok") else "环境检测未通过"
        if report.get("ok"):
            messagebox.showinfo(title, text)
        else:
            messagebox.showwarning(title, text)
    except Exception:
        messagebox.showerror("检测失败", "无法读取检测结果，请查看 logs\\doctor.json")
    return result.returncode


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    raise SystemExit(main())
