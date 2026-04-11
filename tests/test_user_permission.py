"""
用户权限检测的单元测试。

检测当前用户是否为 root，用于决定命令中是否需要 sudo。
"""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from a_cli.llm import is_root_user, _build_messages, _adjust_command_sudo, CommandSuggestion


class TestIsRootUser(unittest.TestCase):
    """测试 is_root_user 函数"""

    @patch("a_cli.llm.os.geteuid", return_value=0)
    def test_is_root_when_euid_0(self, mock_geteuid):
        """当 euid 为 0 时，返回 True（root 用户）"""
        result = is_root_user()
        self.assertTrue(result)
        mock_geteuid.assert_called_once()

    @patch("a_cli.llm.os.geteuid", return_value=501)
    def test_is_not_root_when_euid_non_zero(self, mock_geteuid):
        """当 euid 非 0 时，返回 False（普通用户）"""
        result = is_root_user()
        self.assertFalse(result)
        mock_geteuid.assert_called_once()

    @patch("a_cli.llm.os.geteuid", side_effect=AttributeError("geteuid not found"))
    @patch("a_cli.llm.platform.system", return_value="Windows")
    def test_windows_false(self, mock_sys, mock_geteuid):
        """Windows 平台没有 geteuid，返回 False"""
        result = is_root_user()
        self.assertFalse(result)

    @patch("a_cli.llm.os.geteuid", side_effect=AttributeError("geteuid not found"))
    @patch("a_cli.llm.platform.system", return_value="Java")
    def test_unknown_platform_false(self, mock_sys, mock_geteuid):
        """未知平台返回 False"""
        result = is_root_user()
        self.assertFalse(result)


class TestBuildMessagesWithUserPermission(unittest.TestCase):
    """测试 _build_messages 包含用户权限信息"""

    @patch("a_cli.llm._get_os_info", return_value="Linux (Ubuntu 24.04)")
    @patch("a_cli.llm.is_root_user", return_value=True)
    def test_build_messages_includes_root_user(self, mock_is_root, mock_os_info):
        """当是 root 用户时，prompt 应包含当前是 root 的信息"""
        messages = _build_messages("test query", 3, "bash")
        system_prompt = messages[0]["content"]
        self.assertIn("Current user: root (no sudo needed)", system_prompt)

    @patch("a_cli.llm._get_os_info", return_value="Linux (Ubuntu 24.04)")
    @patch("a_cli.llm.is_root_user", return_value=False)
    def test_build_messages_includes_non_root_user(self, mock_is_root, mock_os_info):
        """当不是 root 用户时，prompt 应包含需要 sudo 的信息"""
        messages = _build_messages("test query", 3, "bash")
        system_prompt = messages[0]["content"]
        self.assertIn("Current user: non-root (use sudo for privileged commands)", system_prompt)


class TestAdjustCommandSudo(unittest.TestCase):
    """测试 _adjust_command_sudo 函数调整命令中的 sudo"""

    @patch("a_cli.llm.is_root_user", return_value=True)
    def test_root_user_removes_sudo(self, mock_is_root):
        """root 用户时，移除命令开头的 sudo"""
        result = _adjust_command_sudo("sudo apt update")
        self.assertEqual(result, "apt update")

    @patch("a_cli.llm.is_root_user", return_value=True)
    def test_root_user_removes_sudo_with_whitespace(self, mock_is_root):
        """root 用户时，移除命令开头带空格的 sudo"""
        result = _adjust_command_sudo("  sudo  apt update")
        self.assertEqual(result, "apt update")

    @patch("a_cli.llm.is_root_user", return_value=True)
    def test_root_user_preserves_non_sudo(self, mock_is_root):
        """root 用户时，保留不带 sudo 的命令"""
        result = _adjust_command_sudo("ls -la")
        self.assertEqual(result, "ls -la")

    @patch("a_cli.llm.is_root_user", return_value=True)
    def test_root_user_preserves_sudo_in_middle(self, mock_is_root):
        """root 用户时，保留命令中间的 sudo（简化版只处理开头）"""
        # 简化版只处理开头的 sudo，中间的保持不变
        # 主要依赖 LLM prompt 来避免这种情况
        result = _adjust_command_sudo("echo hello | sudo tee file.txt")
        self.assertEqual(result, "echo hello | sudo tee file.txt")

    @patch("a_cli.llm.is_root_user", return_value=False)
    def test_non_root_preserves_sudo(self, mock_is_root):
        """非 root 用户时，保留带 sudo 的命令"""
        result = _adjust_command_sudo("sudo apt update")
        self.assertEqual(result, "sudo apt update")

    @patch("a_cli.llm.is_root_user", return_value=False)
    def test_non_root_preserves_non_sudo(self, mock_is_root):
        """非 root 用户时，保留不带 sudo 的命令"""
        result = _adjust_command_sudo("ls -la")
        self.assertEqual(result, "ls -la")

    @patch("a_cli.llm.is_root_user", return_value=True)
    def test_root_user_case_insensitive(self, mock_is_root):
        """root 用户时，不区分大小写的 sudo"""
        result = _adjust_command_sudo("Sudo apt update")
        self.assertEqual(result, "apt update")

    @patch("a_cli.llm.is_root_user", return_value=True)
    def test_root_user_preserves_sudoku(self, mock_is_root):
        """root 用户时，不误删 sudoku 等词"""
        result = _adjust_command_sudo("sudoku game")
        self.assertEqual(result, "sudoku game")

    @patch("a_cli.llm.is_root_user", return_value=True)
    def test_root_user_sudo_with_options(self, mock_is_root):
        """root 用户时，处理带选项的 sudo"""
        result = _adjust_command_sudo("sudo -u www-data ls")
        self.assertEqual(result, "-u www-data ls")


if __name__ == "__main__":
    unittest.main()
