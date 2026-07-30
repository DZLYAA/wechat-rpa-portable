using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Windows.Forms;

internal static class Launcher
{
    private static string FindPython(bool windowed)
    {
        string shadowRoot = @"C:\Program Files\ShadowBot";
        if (Directory.Exists(shadowRoot))
        {
            string[] matches = Directory.GetDirectories(shadowRoot, "shadowbot-*")
                .OrderByDescending(path => path)
                .ToArray();
            foreach (string folder in matches)
            {
                string candidate = Path.Combine(folder, "python", windowed ? "pythonw.exe" : "python.exe");
                if (File.Exists(candidate)) return candidate;
            }
        }

        string executable = windowed ? "pythonw.exe" : "python.exe";
        string pathValue = Environment.GetEnvironmentVariable("PATH") ?? "";
        foreach (string folder in pathValue.Split(Path.PathSeparator))
        {
            try
            {
                string candidate = Path.Combine(folder.Trim(), executable);
                if (File.Exists(candidate)) return candidate;
            }
            catch { }
        }
        return "";
    }

    [STAThread]
    private static int Main()
    {
        string root = AppDomain.CurrentDomain.BaseDirectory.TrimEnd(Path.DirectorySeparatorChar);
        string name = Path.GetFileNameWithoutExtension(Application.ExecutablePath).ToLowerInvariant();
        string script;
        string arguments = "";
        bool wait = true;

        if (name.StartsWith("collect"))
        {
            script = Path.Combine(root, "runtime", "silent_entry.py");
            arguments = "collect";
        }
        else if (name.StartsWith("ack"))
        {
            script = Path.Combine(root, "runtime", "silent_entry.py");
            arguments = "ack";
        }
        else if (name.StartsWith("doctor"))
        {
            script = Path.Combine(root, "runtime", "doctor_gui.py");
        }
        else
        {
            script = Path.Combine(root, "runtime", "setup_gui.py");
        }

        if (!File.Exists(script))
        {
            MessageBox.Show("安装包不完整：找不到 " + script, "微信消息采集便携版",
                MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 2;
        }

        string python = FindPython(true);
        if (String.IsNullOrEmpty(python))
        {
            MessageBox.Show("找不到 Python。请先安装影刀客户端，或安装 Python 3.10 及以上版本。",
                "缺少运行环境", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 3;
        }

        var start = new ProcessStartInfo
        {
            FileName = python,
            Arguments = "\"" + script + "\"" + (arguments.Length > 0 ? " " + arguments : ""),
            WorkingDirectory = Path.Combine(root, "runtime"),
            UseShellExecute = false,
            CreateNoWindow = true,
            WindowStyle = ProcessWindowStyle.Hidden
        };
        try
        {
            using (Process process = Process.Start(start))
            {
                if (wait)
                {
                    process.WaitForExit();
                    return process.ExitCode;
                }
            }
            return 0;
        }
        catch (Exception error)
        {
            MessageBox.Show("启动失败：" + error.Message, "微信消息采集便携版",
                MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 4;
        }
    }
}
