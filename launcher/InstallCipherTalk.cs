using System;
using System.Diagnostics;
using System.IO;
using System.Security.Cryptography;
using System.Windows.Forms;

internal static class InstallCipherTalk
{
    private const string InstallerName = "CipherTalk-2026.729.0-Setup.exe";
    private const string ExpectedSha256 = "48354069b274591a2ca855fee8100addde3b0f75d05e8336ebb509f6a94bf88b";

    private static string Sha256(string path)
    {
        using (var stream = File.OpenRead(path))
        using (var sha = SHA256.Create())
        {
            return BitConverter.ToString(sha.ComputeHash(stream)).Replace("-", "").ToLowerInvariant();
        }
    }

    private static bool DownloadInstaller(string root, string installer)
    {
        string script = Path.Combine(root, "tools", "download-ciphertalk-installer.ps1");
        if (!File.Exists(script))
        {
            MessageBox.Show(
                "找不到官方下载脚本：\n" + script,
                "无法下载密语",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
            return false;
        }

        var answer = MessageBox.Show(
            "此公开工具包不内附 CipherTalk 安装程序。\n\n" +
            "是否现在从 CipherTalk 官方 GitHub Release 下载 v2026.729.0？\n" +
            "下载完成后会自动核验固定 SHA-256；校验失败时不会运行文件。\n\n" +
            "CipherTalk 采用 CC BY-NC-SA 4.0，仅限学习和个人非商业用途。",
            "下载密语 CipherTalk",
            MessageBoxButtons.YesNo,
            MessageBoxIcon.Information);
        if (answer != DialogResult.Yes) return false;

        try
        {
            using (var process = Process.Start(new ProcessStartInfo
            {
                FileName = "powershell.exe",
                Arguments = "-NoProfile -ExecutionPolicy Bypass -File \"" + script + "\"",
                UseShellExecute = false,
                CreateNoWindow = false,
                WorkingDirectory = root
            }))
            {
                if (process == null) throw new InvalidOperationException("无法启动 PowerShell 下载程序");
                process.WaitForExit();
                if (process.ExitCode != 0 || !File.Exists(installer))
                {
                    MessageBox.Show(
                        "官方下载或完整性校验失败。请检查网络后重试。\n" +
                        "不要从不明来源获取安装程序。",
                        "无法下载密语",
                        MessageBoxButtons.OK,
                        MessageBoxIcon.Error);
                    return false;
                }
            }
        }
        catch (Exception error)
        {
            MessageBox.Show("无法运行官方下载脚本：" + error.Message, "无法下载密语",
                MessageBoxButtons.OK, MessageBoxIcon.Error);
            return false;
        }

        return true;
    }

    [STAThread]
    private static int Main()
    {
        string root = AppDomain.CurrentDomain.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar);
        string installer = Path.Combine(root, "vendor", "ciphertalk", InstallerName);
        if (!File.Exists(installer) && !DownloadInstaller(root, installer)) return 2;

        string actual;
        try
        {
            actual = Sha256(installer);
        }
        catch (Exception error)
        {
            MessageBox.Show("无法校验安装程序：" + error.Message, "无法安装密语",
                MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 3;
        }
        if (!String.Equals(actual, ExpectedSha256, StringComparison.OrdinalIgnoreCase))
        {
            MessageBox.Show(
                "安装程序的 SHA-256 与官方发布值不一致。为保护安全，已停止运行。",
                "完整性校验失败",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error);
            return 4;
        }

        var answer = MessageBox.Show(
            "即将打开 CipherTalk v2026.729.0 官方原版安装向导。\n\n" +
            "CipherTalk 使用 CC BY-NC-SA 4.0 许可，仅限学习和个人非商业用途，" +
            "不得用于商业环境。继续表示你已阅读 vendor\\ciphertalk\\LICENSE.txt。\n\n" +
            "安装完成后：\n" +
            "1. 启动一次 CipherTalk；\n" +
            "2. 再运行本文件夹中的 setup.exe；\n" +
            "3. 最后运行 doctor.exe。\n\n现在继续吗？",
            "安装密语 CipherTalk",
            MessageBoxButtons.YesNo,
            MessageBoxIcon.Information);
        if (answer != DialogResult.Yes) return 0;

        try
        {
            Process.Start(new ProcessStartInfo
            {
                FileName = installer,
                UseShellExecute = true,
                WorkingDirectory = Path.GetDirectoryName(installer)
            });
            return 0;
        }
        catch (Exception error)
        {
            MessageBox.Show("启动官方安装向导失败：" + error.Message, "无法安装密语",
                MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 5;
        }
    }
}
