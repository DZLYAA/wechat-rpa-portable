此目录保存当前电脑的本地配置。

首次使用请运行包根目录的 setup.exe。

app.json：路径和运行参数，不含密钥，但可能包含本机用户名和 wxid。
secrets.dat：由 Windows DPAPI 加密，仅创建它的 Windows 用户可以解密。

分享工具包前不要复制 app.json 和 secrets.dat，只保留示例文件。
