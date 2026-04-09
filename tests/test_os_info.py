"""
_get_os_info 函数的单元测试。

通过 mock 模拟不同操作系统环境，覆盖所有代码路径。

用法: python tests/test_os_info.py
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from a_cli.llm import _get_os_info


class TestGetOsInfo(unittest.TestCase):
    """测试 _get_os_info 在各操作系统下的行为"""

    # ── Linux 相关测试 ─────────────────────────────────────────────

    @patch("a_cli.llm.platform.system", return_value="Linux")
    @patch("a_cli.llm.os.path.isfile", return_value=True)
    @patch("builtins.open", new_callable=mock_open, read_data='PRETTY_NAME="Debian GNU/Linux 12 (bookworm)"\n')
    def test_linux_pretty_name(self, mock_file, mock_isfile, mock_sys):
        """Linux: 从 /etc/os-release 读取 PRETTY_NAME"""
        result = _get_os_info()
        self.assertEqual(result, 'Linux (Debian GNU/Linux 12 (bookworm))')
        mock_isfile.assert_called_with("/etc/os-release")

    @patch("a_cli.llm.platform.system", return_value="Linux")
    @patch("a_cli.llm.os.path.isfile", return_value=True)
    @patch("builtins.open", new_callable=mock_open, read_data='PRETTY_NAME="Alpine Linux v3.23"\n')
    def test_linux_alpine(self, mock_file, mock_isfile, mock_sys):
        """Linux: Alpine Linux"""
        result = _get_os_info()
        self.assertEqual(result, 'Linux (Alpine Linux v3.23)')

    @patch("a_cli.llm.platform.system", return_value="Linux")
    @patch("a_cli.llm.os.path.isfile", return_value=True)
    @patch("builtins.open", new_callable=mock_open, read_data='PRETTY_NAME="Ubuntu 24.04.2 LTS"\n')
    def test_linux_ubuntu(self, mock_file, mock_isfile, mock_sys):
        """Linux: Ubuntu"""
        result = _get_os_info()
        self.assertEqual(result, 'Linux (Ubuntu 24.04.2 LTS)')

    @patch("a_cli.llm.platform.system", return_value="Linux")
    @patch("a_cli.llm.os.path.isfile", return_value=True)
    @patch("builtins.open", new_callable=mock_open, read_data='PRETTY_NAME="Fedora Linux 41 (Forty One)"\n')
    def test_linux_fedora(self, mock_file, mock_isfile, mock_sys):
        """Linux: Fedora"""
        result = _get_os_info()
        self.assertEqual(result, 'Linux (Fedora Linux 41 (Forty One))')

    @patch("a_cli.llm.platform.system", return_value="Linux")
    @patch("a_cli.llm.os.path.isfile", return_value=True)
    @patch("builtins.open", new_callable=mock_open, read_data='PRETTY_NAME="Arch Linux"\nID=arch\n')
    def test_linux_pretty_name_with_quotes(self, mock_file, mock_isfile, mock_sys):
        """Linux: PRETTY_NAME 的引号应被正确去除"""
        result = _get_os_info()
        self.assertEqual(result, 'Linux (Arch Linux)')

    @patch("a_cli.llm.platform.system", return_value="Linux")
    @patch("a_cli.llm.os.path.isfile", return_value=False)
    @patch("a_cli.llm.subprocess.run")
    def test_linux_fallback_lsb_release(self, mock_run, mock_isfile, mock_sys):
        """Linux: 无 /etc/os-release 时回退到 lsb_release"""
        mock_run.return_value = MagicMock(returncode=0, stdout="Ubuntu 22.04 LTS\n")
        result = _get_os_info()
        self.assertEqual(result, 'Linux (Ubuntu 22.04 LTS)')
        mock_run.assert_called_once_with(
            ["lsb_release", "-ds"], capture_output=True, text=True, timeout=3,
        )

    @patch("a_cli.llm.platform.system", return_value="Linux")
    @patch("a_cli.llm.os.path.isfile")
    @patch("a_cli.llm.subprocess.run", side_effect=FileNotFoundError)
    def test_linux_fallback_redhat_release(self, mock_run, mock_isfile, mock_sys):
        """Linux: lsb_release 不可用时回退到 /etc/redhat-release"""
        # /etc/os-release 不存在，/etc/redhat-release 存在
        mock_isfile.side_effect = lambda p: p == "/etc/redhat-release"

        with patch("builtins.open", mock_open(read_data="CentOS Linux release 7.9.2009 (Core)\n")):
            result = _get_os_info()
        self.assertEqual(result, "Linux (CentOS Linux release 7.9.2009 (Core))")

    @patch("a_cli.llm.platform.system", return_value="Linux")
    @patch("a_cli.llm.os.path.isfile", return_value=False)
    @patch("a_cli.llm.subprocess.run", side_effect=FileNotFoundError)
    def test_linux_fallback_nothing(self, mock_run, mock_isfile, mock_sys):
        """Linux: 所有检测方式都不可用时返回 'Linux'"""
        mock_isfile.return_value = False
        result = _get_os_info()
        self.assertEqual(result, "Linux")

    @patch("a_cli.llm.platform.system", return_value="Linux")
    @patch("a_cli.llm.os.path.isfile", return_value=True)
    def test_linux_os_release_read_error(self, mock_isfile, mock_sys):
        """Linux: /etc/os-release 读取失败时回退"""
        with patch("builtins.open", side_effect=OSError("Permission denied")):
            # 回退到 lsb_release 也失败
            with patch("a_cli.llm.subprocess.run", side_effect=FileNotFoundError):
                result = _get_os_info()
        self.assertEqual(result, "Linux")

    # ── macOS (Darwin) 相关测试 ────────────────────────────────────

    @patch("a_cli.llm.platform.system", return_value="Darwin")
    @patch("a_cli.llm.subprocess.run")
    def test_darwin_sw_vers(self, mock_run, mock_sys):
        """macOS: sw_vers 正常输出"""
        mock_run.return_value = MagicMock(returncode=0, stdout=(
            "ProductName:\t\tmacOS\n"
            "ProductVersion:\t\t14.0\n"
            "BuildVersion:\t\t23A344\n"
        ))
        result = _get_os_info()
        self.assertEqual(result, "Darwin (macOS 14.0 23A344)")

    @patch("a_cli.llm.platform.system", return_value="Darwin")
    @patch("a_cli.llm.subprocess.run", side_effect=FileNotFoundError)
    @patch("a_cli.llm.platform.mac_ver", return_value=("14.5", ("", "", ""), "arm64"))
    def test_darwin_fallback_mac_ver(self, mock_mac_ver, mock_run, mock_sys):
        """macOS: sw_vers 不可用时回退到 platform.mac_ver()"""
        result = _get_os_info()
        self.assertEqual(result, "Darwin (macOS 14.5)")

    @patch("a_cli.llm.platform.system", return_value="Darwin")
    @patch("a_cli.llm.subprocess.run", side_effect=FileNotFoundError)
    @patch("a_cli.llm.platform.mac_ver", return_value=("", ("", "", ""), ""))
    def test_darwin_no_version(self, mock_mac_ver, mock_run, mock_sys):
        """macOS: 所有检测都失败时返回 'Darwin'"""
        result = _get_os_info()
        self.assertEqual(result, "Darwin")

    @patch("a_cli.llm.platform.system", return_value="Darwin")
    @patch("a_cli.llm.subprocess.run")
    def test_darwin_sw_vers_partial(self, mock_run, mock_sys):
        """macOS: sw_vers 仅输出部分字段"""
        mock_run.return_value = MagicMock(returncode=0, stdout="ProductName:\t\tmacOS\n")
        result = _get_os_info()
        self.assertEqual(result, "Darwin (macOS)")

    # ── Windows 相关测试 ───────────────────────────────────────────

    @patch("a_cli.llm.platform.system", return_value="Windows")
    @patch("a_cli.llm.platform.win32_ver", return_value=("10", "10.0.19045", "SP0", "AMD64"))
    def test_windows_full(self, mock_win32, mock_sys):
        """Windows: 完整版本信息"""
        result = _get_os_info()
        self.assertEqual(result, "Windows (10 Build 10.0.19045 SP0 AMD64)")

    @patch("a_cli.llm.platform.system", return_value="Windows")
    @patch("a_cli.llm.platform.win32_ver", return_value=("10", "10.0.22631", "", "AMD64"))
    def test_windows_no_sp(self, mock_win32, mock_sys):
        """Windows: 无 Service Pack"""
        result = _get_os_info()
        self.assertEqual(result, "Windows (10 Build 10.0.22631 AMD64)")

    @patch("a_cli.llm.platform.system", return_value="Windows")
    @patch("a_cli.llm.platform.win32_ver", return_value=("11", "", "", ""))
    def test_windows_release_only(self, mock_win32, mock_sys):
        """Windows: 仅有 release 名称"""
        result = _get_os_info()
        self.assertEqual(result, "Windows (11)")

    @patch("a_cli.llm.platform.system", return_value="Windows")
    @patch("a_cli.llm.platform.win32_ver", return_value=("", "", "", ""))
    def test_windows_no_info(self, mock_win32, mock_sys):
        """Windows: win32_ver 无任何信息"""
        result = _get_os_info()
        self.assertEqual(result, "Windows")

    # ── 其他/未知系统 ──────────────────────────────────────────────

    @patch("a_cli.llm.platform.system", return_value="FreeBSD")
    def test_unknown_os(self, mock_sys):
        """未知系统: 直接返回 platform.system() 的值"""
        result = _get_os_info()
        self.assertEqual(result, "FreeBSD")


if __name__ == "__main__":
    unittest.main()
