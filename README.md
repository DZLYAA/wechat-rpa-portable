# 微信消息采集便携版

> 普通使用者请从 GitHub Releases 下载完整 ZIP，不要直接下载仓库源码压缩包。完整 Release ZIP 包含经过 SHA-256 校验的 CipherTalk 官方安装程序；Git 仓库因 GitHub 100 MB 单文件限制不提交该安装程序。

源码构建者如需恢复官方安装程序，可运行：

```powershell
powershell -ExecutionPolicy Bypass -File tools\download-ciphertalk-installer.ps1
```

脚本下载 CipherTalk v2026.729.0 官方 Release 文件，并验证 SHA-256：

```text
48354069b274591a2ca855fee8100addde3b0f75d05e8336ebb509f6a94bf88b
```

这是原有稳定流程的独立副本。它不会读取或修改旧版 `wechat-rpa` 目录。

## 能做什么

- 通过 CipherTalk 桌面端本地 MCP 接口增量读取当前用户的微信消息。
- 由影刀把新消息写入 Excel，并按消息键二次去重。
- 显示中文表头、发送者微信名，图片可嵌入预览并保留原文件链接。
- 采集与确认程序可静默运行；Excel 保存失败时 pending 消息不会被确认删除。
- 所有路径由 `config/app.json` 管理，密钥保存在当前 Windows 用户 DPAPI 加密的 `config/secrets.dat` 中。

## 最短安装路径

1. 解压到一个长期不移动的目录，例如 `D:\WechatRpaPortable`。
2. 安装微信和影刀；建议安装 Microsoft Excel 桌面版。
3. 如果没有 CipherTalk，双击 `1-安装密语.exe`，完成官方安装向导并启动一次 CipherTalk。
4. 双击 `setup.exe`，填写本机路径、wxid 和三种密钥，点击“保存并初始化”。
5. 重启 CipherTalk，双击 `doctor.exe`，确保所有项目通过。
6. 把 `shadowbot\module1.py` 的完整内容复制到影刀自定义模块 `module1`，函数选择 `main`，参数传入空字典 `{}`，返回变量设为 `invoke_result`。
7. 按《使用说明-请先阅读》修改并运行影刀流程。

首次采集只建立基线，不导入历史消息。此后收到或发出的新消息才写入 Excel。

## 重要限制

- 仅用于你本人账号及你有权处理的数据；转交消息数据前请获得相关人员同意。
- 不包含微信、Excel 或影刀。本包附带 CipherTalk v2026.729.0 官方未修改安装器，使用前必须接受其 CC BY-NC-SA 4.0 非商业许可；没有 Excel 桌面版时使用内置兼容写入。
- `secrets.dat` 不能复制到另一名 Windows 用户使用；对方必须运行自己的 `setup.exe`。
- CipherTalk 使用 CC BY-NC-SA 4.0，商业部署前需单独确认许可。
- 微信或 CipherTalk 更新后接口、数据库格式、媒体解密方式可能变化，升级前应先备份并测试。

详细说明见 `docs` 目录。
