"""快速查看 _get_os_info() 的输出，用于在不同系统中手动验证。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from a_cli.llm import _get_os_info

print(_get_os_info())
