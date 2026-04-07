"""
终端交互 UI 模块
- 用 rich 渲染命令卡片
- 用 inquirerpy 做交互式选择
- 单条结果时直接确认执行
- placeholder 占位符检测与填充
- 高风险命令警告与强制二次确认
"""
import re
import sys
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table
from rich.text import Text
from rich.theme import Theme

from .llm import CommandSuggestion

# ── 自定义主题 ────────────────────────────────────────────────────────────────
THEME = Theme(
    {
        "cmd": "bold cyan",
        "explain": "dim white",
        "label": "bold magenta",
        "hint": "dim italic",
        "ok": "bold green",
        "warn": "bold yellow",
        "err": "bold red",
    }
)
console = Console(theme=THEME, highlight=False)


def _confidence_bar(score: float, width: int = 10) -> str:
    """把置信度转成可视化进度条"""
    filled = round(score * width)
    bar = "█" * filled + "░" * (width - filled)
    pct = f"{score:.0%}"
    return f"[dim]{bar}[/dim] [hint]{pct}[/hint]"


def _render_single(suggestion: CommandSuggestion, show_explanation: bool):
    """渲染单条命令建议"""
    console.print()
    syntax = Syntax(suggestion.command, "bash", theme="monokai", word_wrap=True)
    panel = Panel(
        syntax,
        title="[label]💡 建议命令[/label]",
        border_style="cyan",
        padding=(0, 2),
    )
    console.print(panel)
    if show_explanation and suggestion.explanation:
        console.print(f"  [explain]说明：{suggestion.explanation}[/explain]")
    console.print(
        f"  [hint]置信度：[/hint]{_confidence_bar(suggestion.confidence)}"
    )
    console.print()


def _render_multiple(suggestions: list[CommandSuggestion], show_explanation: bool):
    """渲染多条命令建议：每条命令独占一行，说明紧跟其后换行显示"""
    console.print()
    parts = []
    for i, s in enumerate(suggestions, 1):
        segment = Text()
        segment.append(f"{i}. ", style="dim")
        segment.append(s.command, style="cmd")  # plain text，不经过 markup 解析
        if show_explanation and s.explanation:
            segment.append(f"\n   {s.explanation}", style="explain")
        parts.append(segment)

    content = Text("\n\n").join(parts)
    console.print(Panel(content, title="[label]💡 命令建议[/label]", border_style="cyan", padding=(1, 2)))
    console.print()


def prompt_select(suggestions: list[CommandSuggestion]) -> Optional[str]:
    """
    交互式选择：方向键上下 + 回车确认，直接执行
    返回选中的命令字符串，None 表示用户取消
    """
    try:
        from InquirerPy import inquirer
        from InquirerPy.base.control import Choice
    except ImportError:
        console.print(
            "[err]缺少依赖: InquirerPy[/err]\n请运行: [cmd]pip install InquirerPy[/cmd]"
        )
        sys.exit(1)

    choices = [
        Choice(value=s.command, name=f"  {s.command}")
        for s in suggestions
    ]
    choices.append(Choice(value=None, name="  ✗ 取消"))

    result = inquirer.select(
        message="请选择要执行的命令（↑↓ 选择，回车确认）:",
        choices=choices,
        default=suggestions[0].command,
        qmark="▶",
        amark="▶",
        pointer="❯",
        instruction="",
    ).execute()

    return result


def prompt_confirm_single(command: str) -> bool:
    """单条结果的确认框"""
    try:
        from InquirerPy import inquirer
    except ImportError:
        # fallback: 用 input()
        ans = input("执行此命令？[Y/n] ").strip().lower()
        return ans in ("", "y", "yes")

    return inquirer.confirm(
        message=f"执行此命令？",
        default=True,
        qmark="▶",
        amark="▶",
    ).execute()


def show_executing(command: str):
    console.print()
    console.print(Text("▶ 执行:", style="ok"), Text(command, style="cmd"))
    console.print()


def show_copied(command: str):
    console.print(f"\n[ok]✓ 已复制到剪贴板[/ok]")


def show_cancelled():
    console.print("\n[hint]已取消[/hint]\n")


def show_loading(query: str):
    t = Text()
    t.append("\n正在为「", style="hint")
    t.append(query, style="label")
    t.append("」生成命令…\n", style="hint")
    console.print(t)


def display_and_select(
    suggestions: list[CommandSuggestion],
    show_explanation: bool,
    auto_confirm_single: bool,
) -> Optional[str]:
    """
    统一入口：展示建议 → 用户选择/确认 → 返回最终命令
    """
    if len(suggestions) == 1:
        _render_single(suggestions[0], show_explanation)
        if auto_confirm_single:
            confirmed = prompt_confirm_single(suggestions[0].command)
            return suggestions[0].command if confirmed else None
        else:
            return suggestions[0].command
    else:
        _render_multiple(suggestions, show_explanation)
        return prompt_select(suggestions)


# ── Placeholder 占位符检测与填充 ─────────────────────────────────────────────

# 匹配 {PLACEHOLDER} 格式的占位符，如 {FILE_PATH}、{PORT}、{N}
_PLACEHOLDER_RE = re.compile(r'\{([A-Z][A-Z0-9_]*)\}')


def find_placeholders(command: str) -> list[str]:
    """检测命令中 {PLACEHOLDER} 格式的占位符，去重并保持出现顺序。"""
    seen: set[str] = set()
    result: list[str] = []
    for m in _PLACEHOLDER_RE.finditer(command):
        name = m.group(1)
        if name not in seen:
            seen.add(name)
            result.append(name)
    return result


def fill_placeholders(command: str, placeholders: list[str]) -> Optional[str]:
    """
    交互式让用户依次输入每个占位符的值，返回填充后的完整命令。
    如果用户取消则返回 None。
    """
    try:
        from InquirerPy import inquirer
    except ImportError:
        console.print(
            "[err]缺少依赖: InquirerPy[/err]\n请运行: [cmd]pip install InquirerPy[/cmd]"
        )
        sys.exit(1)

    console.print()
    console.print(
        Text("📋 ", style=""),
        Text("检测到命令中含有占位符，请依次填写：", style="warn"),
    )
    console.print()

    values: dict[str, str] = {}
    for name in placeholders:
        console.print(
            Text(f"  占位符 ", style="hint"),
            Text(f"{{{name}}}", style="bold yellow"),
        )
        val = inquirer.text(
            message=f"  请输入 {name} 的值",
            qmark="▶",
        ).execute()

        if val is None:
            console.print("\n[hint]已取消[/hint]\n")
            return None

        if not val.strip():
            console.print(f"  [dim]（{name} 已留空，将原样保留）[/dim]\n")
        else:
            values[name] = val.strip()
            console.print()

    # 替换占位符（带花括号）
    filled = command
    for name, val in values.items():
        filled = filled.replace(f"{{{name}}}", val)

    # 显示填充后的完整命令
    console.print()
    syntax = Syntax(filled, "bash", theme="monokai", word_wrap=True)
    panel = Panel(
        syntax,
        title="[ok]✓ 完整命令[/ok]",
        border_style="green",
        padding=(0, 2),
    )
    console.print(panel)
    console.print()

    return filled


# ── 高风险命令警告与二次确认 ───────────────────────────────────────────

_RISK_LEVEL_STYLES = {
    5: ("bold white on red", "☠️  致命危险"),
    4: ("bold black on yellow", "🔴 高危"),
    3: ("bold white on magenta", "⚠️  中危"),
}


def _risk_level_style(level: int) -> tuple[str, str]:
    """根据风险等级返回样式和标签"""
    return _RISK_LEVEL_STYLES.get(level, (None, f"[{level}]"))


def show_risk_warning(command: str, risk_pattern) -> None:
    """
    以显著方式展示高风险命令警告。

    使用醒目的红色/黄色边框面板、闪烁效果（终端支持时），
    清晰告知用户风险类型和后果。
    """
    style, label = _risk_level_style(risk_pattern.risk_level)

    # 构建警告内容
    warning_text = Text()
    # 风险等级标签
    tag = Text(f"  {label}  ", style=style)
    warning_text.append(tag)
    warning_text.append("\n\n")

    # 命令预览
    warning_text.append("检测到高风险命令：\n", style="bold")
    cmd_preview = Text(f"  {command}", style="bold red underline")
    warning_text.append(cmd_preview)
    warning_text.append("\n\n")

    # 风险类型
    warning_text.append("风险类型：", style="bold yellow")
    warning_text.append(f" {risk_pattern.name}\n")

    # 详细说明
    if risk_pattern.detail:
        warning_text.append("\n风险说明：", style="bold yellow")
        warning_text.append(f"\n  {risk_pattern.detail}\n")

    # 确认提示
    warning_text.append("\n")
    warning_text.append("⚡ 此操作可能造成不可逆的后果！请仔细确认后再继续。", style="bold red")

    # 渲染警告面板
    border = "red" if risk_pattern.risk_level >= 4 else "yellow"
    panel = Panel(
        warning_text,
        title="[bold reverse red] ⛔ 安全警告 [/bold reverse red]",
        border_style=border,
        padding=(1, 3),
        width=console.width - 2,
    )
    console.print()
    console.print(panel)
    console.print()


def prompt_risk_confirmation(risk_pattern) -> bool:
    """
    高风险命令强制二次确认。

    用户必须完整输入 "yes" 才能通过确认，防止误操作。
    返回 True 表示用户确认执行，False 表示取消。
    """
    try:
        from InquirerPy import inquirer
    except ImportError:
        # fallback: 要求手动输入 yes
        console.print("[bold red]▶[/bold red] 如确定要执行，请输入 [bold]yes[/bold] 确认：", end=" ")
        ans = input().strip().lower()
        return ans == "yes"

    # 使用 inquirer 的 confirm + 额外文字确认
    first_confirm = inquirer.confirm(
        message="确定要执行此高风险命令？",
        default=False,
        qmark="⚠",
        amark="",
    ).execute()

    if not first_confirm:
        return False

    # 二次确认：要求输入 "yes"
    second_input = inquirer.text(
        message='为最终确认，请输入 "yes":',
        qmark="✋",
        validate=lambda result: result.lower() == "yes" or (
            (result is None or result.strip() == "")
            and False  # 不允许空值
        ) or True,
        invalid_message='[red]输入不匹配，请准确输入 "yes" 以确认（或 Ctrl+C 取消）[/red]',
        multiline=False,
    ).execute()

    return second_input and second_input.strip().lower() == "yes"


def check_and_warn_high_risk(
    command: str,
    enable_check: bool = True,
    custom_patterns: Optional[list] = None,
) -> bool:
    """
    检查命令是否为高风险命令，若是则显示警告并要求二次确认。

    Args:
        command: 待检查的 shell 命令
        enable_check: 是否启用安全检查（来自配置）
        custom_patterns: 用户自定义的风险模式列表（来自 safety config）

    Returns:
        True 表示可以继续执行，False 表示用户取消了操作。
    """
    if not enable_check:
        return True

    from .safety import detect_risk, load_custom_risk_patterns

    # 加载自定义模式
    custom_rp = load_custom_risk_patterns({"custom_patterns": custom_patterns}) if custom_patterns else []

    matched = detect_risk(command, custom_patterns=custom_rp if custom_rp else None)

    if matched is None:
        return True  # 无风险，直接放行

    # 显示醒目警告
    show_risk_warning(command, matched)

    # 强制二次确认
    confirmed = prompt_risk_confirmation(matched)

    if confirmed:
        console.print("[green]  ✓ 已确认，继续执行[/green]\n")
    else:
        console.print("\n[yellow]  ✗ 已取消执行[/yellow]\n")

    return confirmed
