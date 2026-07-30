import json
import importlib.util
import os
import re
import shutil
import tkinter as tk
import winreg
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from portable_common import (
    DATA_DIR,
    PACKAGE_ROOT,
    copy_excel_template_if_needed,
    ensure_dirs,
    initialize_state,
    load_config,
    load_secrets,
    save_config,
    save_secrets,
    upsert_ciphertalk_configuration,
)


LOCATOR_DIR = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "WechatRpaPortable"
LOCATOR_PATH = LOCATOR_DIR / "install.json"


def find_installed_ciphertalk():
    local = Path(os.environ.get("LOCALAPPDATA", str(Path.home())))
    program_files = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
    program_files_x86 = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"))
    candidates = [
        local / "Programs" / "CipherTalk" / "CipherTalk.exe",
        local / "Programs" / "ciphertalk" / "CipherTalk.exe",
        program_files / "CipherTalk" / "CipherTalk.exe",
        program_files_x86 / "CipherTalk" / "CipherTalk.exe",
    ]

    registry_roots = (
        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
    )
    for hive, key_path in registry_roots:
        try:
            with winreg.OpenKey(hive, key_path) as root:
                for index in range(winreg.QueryInfoKey(root)[0]):
                    try:
                        with winreg.OpenKey(root, winreg.EnumKey(root, index)) as item:
                            name = str(winreg.QueryValueEx(item, "DisplayName")[0] or "")
                            if "ciphertalk" not in name.lower() and "密语" not in name:
                                continue
                            try:
                                location = str(winreg.QueryValueEx(item, "InstallLocation")[0] or "")
                            except OSError:
                                location = ""
                            try:
                                icon = str(winreg.QueryValueEx(item, "DisplayIcon")[0] or "")
                            except OSError:
                                icon = ""
                            if location:
                                candidates.append(Path(location.strip('"')) / "CipherTalk.exe")
                            if icon:
                                candidates.append(Path(icon.split(",", 1)[0].strip('"')))
                    except OSError:
                        continue
        except OSError:
            continue

    for executable in candidates:
        if executable.is_file():
            return executable.parent, executable
    return None, None


class SetupApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("微信消息采集便携版 - 首次配置")
        self.geometry("840x720")
        self.minsize(780, 660)
        self.vars = {}
        self.show_secrets = tk.BooleanVar(value=False)
        self.status = tk.StringVar(
            value="请填写本机配置。密钥将使用 Windows DPAPI 加密保存。"
        )
        self._build()
        self._load_existing()

    def _row(self, parent, row, label, key, secret=False, browse=None):
        ttk.Label(parent, text=label, width=24).grid(
            row=row, column=0, sticky="w", padx=8, pady=6
        )
        var = tk.StringVar()
        self.vars[key] = var
        entry = ttk.Entry(parent, textvariable=var, show="*" if secret else "")
        entry.grid(row=row, column=1, sticky="ew", padx=8, pady=6)
        if browse:
            ttk.Button(
                parent,
                text="浏览",
                command=lambda: self._browse(var, browse),
            ).grid(row=row, column=2, padx=8, pady=6)
        return entry

    def _build(self):
        container = ttk.Frame(self, padding=12)
        container.pack(fill="both", expand=True)
        container.columnconfigure(0, weight=1)

        basic = ttk.LabelFrame(container, text="路径配置", padding=10)
        basic.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        basic.columnconfigure(1, weight=1)
        self._row(basic, 0, "CipherTalk 目录", "ciphertalkRoot", browse="dir")
        self._row(
            basic,
            1,
            "CipherTalk 启动文件/命令",
            "ciphertalkStartCommand",
            browse="file",
        )
        self._row(
            basic,
            2,
            "CipherTalk 配置数据库",
            "ciphertalkConfigDb",
            browse="file",
        )
        self._row(basic, 3, "微信数据目录", "wechatDbPath", browse="dir")
        self._row(basic, 4, "微信账号 wxid", "wxid")
        self._row(basic, 5, "Excel 保存路径", "excelPath", browse="save")

        secrets = ttk.LabelFrame(
            container, text="当前用户密钥（不会写入普通 JSON 或日志）", padding=10
        )
        secrets.grid(row=1, column=0, sticky="nsew", pady=(0, 10))
        secrets.columnconfigure(1, weight=1)
        self.secret_entries = [
            self._row(
                secrets, 0, "数据库密钥（64 位 HEX）", "decryptKey", secret=True
            ),
            self._row(secrets, 1, "图片 XOR 密钥", "imageXorKey", secret=True),
            self._row(secrets, 2, "图片 AES 密钥", "imageAesKey", secret=True),
        ]
        ttk.Checkbutton(
            secrets,
            text="显示密钥",
            variable=self.show_secrets,
            command=self._toggle_secrets,
        ).grid(row=3, column=1, sticky="w", padx=8)

        options = ttk.LabelFrame(container, text="运行参数", padding=10)
        options.grid(row=2, column=0, sticky="nsew", pady=(0, 10))
        options.columnconfigure(1, weight=1)
        self._row(options, 0, "轮询间隔（秒）", "pollIntervalSeconds")
        self._row(options, 1, "每次消息上限", "messageLimit")

        notes = (
            "配置前建议关闭 CipherTalk 和影刀流程。保存后会：\n"
            "1. 生成 app.json 和由 DPAPI 加密的 secrets.dat；\n"
            "2. 备份并更新当前用户的 CipherTalk 账号配置，启用本地 MCP；\n"
            "3. 创建空白 Excel 和运行状态文件；\n"
            "4. 注册便携包位置，供影刀 module1.py 自动发现。"
        )
        ttk.Label(container, text=notes, justify="left").grid(
            row=3, column=0, sticky="w", pady=(0, 10)
        )
        ttk.Label(
            container,
            textvariable=self.status,
            foreground="#1f4e78",
            wraplength=790,
        ).grid(row=4, column=0, sticky="ew", pady=(0, 10))
        buttons = ttk.Frame(container)
        buttons.grid(row=5, column=0, sticky="e")
        ttk.Button(buttons, text="检测基础环境", command=self._doctor).pack(
            side="left", padx=5
        )
        ttk.Button(buttons, text="保存并初始化", command=self._save).pack(
            side="left", padx=5
        )
        ttk.Button(buttons, text="退出", command=self.destroy).pack(
            side="left", padx=5
        )

    def _browse(self, var, mode):
        if mode == "dir":
            value = filedialog.askdirectory()
        elif mode == "save":
            value = filedialog.asksaveasfilename(
                defaultextension=".xlsx", filetypes=[("Excel 工作簿", "*.xlsx")]
            )
        else:
            value = filedialog.askopenfilename()
        if value:
            var.set(value)

    def _toggle_secrets(self):
        show = "" if self.show_secrets.get() else "*"
        for entry in self.secret_entries:
            entry.configure(show=show)

    def _load_existing(self):
        defaults = load_config(require=False)
        try:
            encrypted = load_secrets(require=False)
        except Exception:
            encrypted = {}
            self.status.set("检测到无法解密的旧 secrets.dat，请重新输入本机密钥。")
        home = Path.home()
        suggested_roots = [home / "CipherTalk", home / "Downloads" / "CipherTalk-latest"]
        suggested_root = next((path for path in suggested_roots if path.exists()), None)
        installed_root, installed_executable = find_installed_ciphertalk()
        if installed_root:
            suggested_root = installed_root
        suggested_db = (
            Path(os.environ.get("APPDATA", home))
            / "ciphertalk"
            / "ciphertalk-config.db"
        )
        values = {
            "ciphertalkRoot": defaults.get("ciphertalkRoot")
            or (str(suggested_root) if suggested_root else ""),
            "ciphertalkStartCommand": defaults.get("ciphertalkStartCommand") or "",
            "ciphertalkConfigDb": defaults.get("ciphertalkConfigDb")
            or str(suggested_db),
            "wechatDbPath": defaults.get("wechatDbPath") or "",
            "wxid": defaults.get("wxid") or "",
            "excelPath": defaults.get("excelPath")
            or str(DATA_DIR / "wechat_messages.xlsx"),
            "pollIntervalSeconds": str(defaults.get("pollIntervalSeconds", 5)),
            "messageLimit": str(defaults.get("messageLimit", 200)),
            "decryptKey": encrypted.get("decryptKey", ""),
            "imageXorKey": encrypted.get("imageXorKey", ""),
            "imageAesKey": encrypted.get("imageAesKey", ""),
        }
        if not values["ciphertalkStartCommand"] and installed_executable:
            values["ciphertalkStartCommand"] = str(installed_executable)
        for key, value in values.items():
            self.vars[key].set(value)

    def _validate(self):
        values = {key: var.get().strip() for key, var in self.vars.items()}
        required = (
            "ciphertalkRoot",
            "ciphertalkConfigDb",
            "wechatDbPath",
            "wxid",
            "excelPath",
            "decryptKey",
        )
        missing = [key for key in required if not values.get(key)]
        if missing:
            raise ValueError("以下字段不能为空：" + ", ".join(missing))
        if not re.fullmatch(r"[0-9a-fA-F]{64}", values["decryptKey"]):
            raise ValueError("数据库密钥必须是 64 位十六进制字符")
        if not Path(values["ciphertalkRoot"]).is_dir():
            raise ValueError("CipherTalk 目录不存在")
        if not Path(os.path.expandvars(values["ciphertalkConfigDb"])).is_file():
            raise ValueError("CipherTalk 配置数据库不存在，请先启动一次 CipherTalk")
        if not Path(values["wechatDbPath"]).is_dir():
            raise ValueError("微信数据目录不存在")
        poll_interval = int(values["pollIntervalSeconds"])
        message_limit = int(values["messageLimit"])
        if not 2 <= poll_interval <= 3600:
            raise ValueError("轮询间隔必须在 2 到 3600 秒之间")
        if not 1 <= message_limit <= 1000:
            raise ValueError("每次消息上限必须在 1 到 1000 之间")
        return values

    def _doctor(self):
        try:
            self._validate()
            problems = []
            office_roots = (
                Path(r"C:\Program Files\Microsoft Office"),
                Path(r"C:\Program Files (x86)\Microsoft Office"),
            )
            has_excel = bool(shutil.which("EXCEL.EXE")) or any(
                path.exists() for path in office_roots
            )
            if not has_excel and importlib.util.find_spec("openpyxl") is None:
                problems.append("未检测到 Excel 桌面版或 openpyxl，无法写入工作簿")
            elif not has_excel:
                problems.append("未检测到 Excel 桌面版，将使用兼容写入")
            if not Path(r"C:\Program Files\ShadowBot").exists():
                problems.append("未检测到影刀安装目录")
            if problems:
                self.status.set("基础路径有效；提示：" + "；".join(problems))
            else:
                self.status.set("基础环境检测通过，可以保存并初始化。")
        except Exception as error:
            self.status.set("环境检测失败：" + str(error))

    def _save(self):
        try:
            values = self._validate()
            config = load_config(require=False)
            config.update(
                {
                    "ciphertalkRoot": values["ciphertalkRoot"],
                    "ciphertalkConfigDb": values["ciphertalkConfigDb"],
                    "ciphertalkStartCommand": values["ciphertalkStartCommand"],
                    "wechatDbPath": values["wechatDbPath"],
                    "wxid": values["wxid"],
                    "excelPath": values["excelPath"],
                    "pollIntervalSeconds": int(values["pollIntervalSeconds"]),
                    "messageLimit": int(values["messageLimit"]),
                }
            )
            secrets = {
                "decryptKey": values["decryptKey"].lower(),
                "imageXorKey": values["imageXorKey"],
                "imageAesKey": values["imageAesKey"],
            }
            resolved_config = dict(config)
            resolved_config["ciphertalkConfigDbResolved"] = str(
                Path(os.path.expandvars(values["ciphertalkConfigDb"])).resolve()
            )
            backup_path = upsert_ciphertalk_configuration(resolved_config, secrets)
            save_config(config)
            save_secrets(secrets)
            config = load_config()
            initialize_state()
            excel_path = copy_excel_template_if_needed()
            LOCATOR_DIR.mkdir(parents=True, exist_ok=True)
            LOCATOR_PATH.write_text(
                json.dumps(
                    {"packageRoot": str(PACKAGE_ROOT), "schemaVersion": 1}, indent=2
                ),
                encoding="utf-8",
            )
            self.status.set(
                f"初始化完成。Excel：{excel_path}；CipherTalk 配置备份：{backup_path}"
            )
            messagebox.showinfo(
                "完成", "配置与空白运行环境已创建。请重启 CipherTalk 后运行 doctor.exe。"
            )
        except Exception as error:
            self.status.set("初始化失败：" + str(error))
            messagebox.showerror("初始化失败", str(error))


if __name__ == "__main__":
    ensure_dirs()
    SetupApp().mainloop()
