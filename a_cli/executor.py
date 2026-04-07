"""
命令执行器
- 将命令注入到当前 shell 历史 + 执行
- 跨平台剪贴板支持
- 历史记录持久化
"""
import os
import platform
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def execute_command(command: str):
    """
    在当前进程的子 shell 中执行命令，继承 stdin/stdout/stderr，
    用户能看到完整输出并可交互。

    注意：受限于进程隔离，无法修改父 shell 的 $PWD / env，
    cd 等改变父 shell 状态的命令会有说明提示。
    """
    _warn_if_stateful(command)
    _append_to_history(command)

    try:
        result = subprocess.run(
            command,
            shell=True,
            executable=_get_shell_executable(),
        )
        return result.returncode
    except KeyboardInterrupt:
        print("\n[已中断]")
        return 130


def copy_to_clipboard(command: str) -> bool:
    """
    将命令复制到系统剪贴板，返回是否成功。
    """
    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.run(["pbcopy"], input=command.encode(), check=True)
        elif system == "Linux":
            # 优先 xclip，其次 xsel，其次 wl-clipboard
            for prog, args in [
                ("xclip", ["-selection", "clipboard"]),
                ("xsel", ["--clipboard", "--input"]),
                ("wl-copy", []),
            ]:
                if _cmd_exists(prog):
                    subprocess.run([prog] + args, input=command.encode(), check=True)
                    break
            else:
                return False
        elif system == "Windows":
            subprocess.run(["clip"], input=command.encode("gbk"), check=True)
        else:
            return False
        return True
    except Exception:
        return False


# ── 内部工具函数 ──────────────────────────────────────────────────────────────

def _get_shell_executable() -> str:
    """获取当前用户的 shell 可执行文件路径"""
    shell = os.environ.get("SHELL", "")
    if shell and Path(shell).exists():
        return shell
    for candidate in ("/bin/zsh", "/bin/bash", "/bin/sh"):
        if Path(candidate).exists():
            return candidate
    return "/bin/sh"


def _cmd_exists(name: str) -> bool:
    return subprocess.run(
        ["which", name], capture_output=True
    ).returncode == 0


STATEFUL_PREFIXES = ("cd ", "export ", "unset ", "source ", ". ", "alias ")


def _warn_if_stateful(command: str):
    """提示用户某些命令无法改变父 shell 状态"""
    stripped = command.strip()
    for prefix in STATEFUL_PREFIXES:
        if stripped.startswith(prefix):
            from rich.console import Console
            Console().print(
                f"\n[yellow]⚠ 提示[/yellow] [dim]`{prefix.strip()}` "
                "等命令在子 shell 中执行，不会影响当前终端环境。\n"
                "如需影响当前 shell，请手动运行或使用 `eval $(a ...)` 模式。[/dim]\n"
            )
            break


def _append_to_history(command: str):
    """将执行的命令追加到 a-cli 历史记录文件"""
    try:
        from .config import load_config
        cfg = load_config()
        history_path = Path(cfg.behavior.history_file)
        history_path.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(history_path, "a", encoding="utf-8") as f:
            f.write(f"[{ts}] {command}\n")
    except Exception:
        pass  # 历史记录写失败不影响主流程
