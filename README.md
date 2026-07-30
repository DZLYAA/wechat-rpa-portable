# 微信消息采集便携版

> 仅用于本人账号和已获授权的数据，且仅限学习与个人非商业用途。禁止用于未授权访问、秘密监控或商业部署。

这是原有稳定流程的独立便携副本。它通过 CipherTalk 桌面端本地 MCP 接口增量读取当前用户的微信消息，再由影刀写入 Excel。

## 下载说明

普通使用者请从 GitHub Releases 下载 `wechat-rpa-portable-v1.2.zip`，不要直接下载仓库源码压缩包。

公开仓库和 Release **不包含 CipherTalk 安装程序**。双击 `1-安装密语.exe` 后，工具会：

1. 提示 CipherTalk 的非商业许可证；
2. 从 CipherTalk 官方 GitHub Release 下载 v2026.729.0；
3. 核验固定 SHA-256；
4. 只有校验成功后才打开官方安装向导。

官方来源：<https://github.com/ILoveBingLu/CipherTalk/releases/tag/v2026.729.0>

```text
SHA-256: 48354069b274591a2ca855fee8100addde3b0f75d05e8336ebb509f6a94bf88b
```

也可以手动运行官方下载脚本：

```powershell
powershell -ExecutionPolicy Bypass -File tools\download-ciphertalk-installer.ps1
```

## 能做什么

- 增量读取当前用户的新微信消息。
- 按消息键去重后写入 Excel。
- 显示中文表头和发送者微信名。
- 在条件满足时嵌入图片预览并保留本地媒体链接。
- 使用 pending/ACK 机制，Excel 保存失败时不会提前确认消息。
- 使用 Windows DPAPI 加密本机 `config/secrets.dat`。

## 最短安装路径

1. 解压到长期固定目录，例如 `D:\WechatRpaPortable`。
2. 安装微信和影刀；建议安装 Microsoft Excel 桌面版。
3. 双击 `1-安装密语.exe`，从官方地址下载并安装 CipherTalk，然后启动一次 CipherTalk。
4. 双击 `setup.exe`，填写本机路径、wxid 和三种密钥。
5. 重启 CipherTalk，双击 `doctor.exe`，确认检测通过。
6. 从[影刀流程分享页](https://api.winrobot360.com/redirect/robot/share?inviteKey=dd2b99dec2af6ed9)获取“微信消息抓取3.0”。
7. 将 `shadowbot\module1.py` 导入影刀模块 `module1`，函数选择 `main`，参数传入空字典 `{}`。
8. 按《使用说明-请先阅读》修改本机路径并运行影刀流程。

首次采集只建立基线，不导入历史消息；后续收到或发出的新消息才写入 Excel。

## 安全与隐私

- 不要把 `config/app.json`、`config/secrets.dat`、`state/`、`logs/`、消息 Excel、微信数据库或媒体缓存提交到 GitHub。
- 不要在公开 Issue 中发送密钥、真实 wxid、联系人、聊天内容或本机路径。
- `secrets.dat` 与创建它的 Windows 用户绑定，不能作为预配置文件转发。
- 微信或 CipherTalk 更新可能改变接口和数据库格式，升级前应备份并测试。

详见 [SECURITY.md](SECURITY.md) 和 `docs/04-打包与隐私清理.md`。

## 许可证

- 本项目原创代码和文档：CC BY-NC-SA 4.0，详见 [LICENSE](LICENSE)。
- CipherTalk：归 ILoveBingLu 所有，采用 CC BY-NC-SA 4.0，仅限学习和个人非商业用途；详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
- 本项目与微信、腾讯、CipherTalk 作者、影刀或 Microsoft 不存在背书或官方合作关系。
