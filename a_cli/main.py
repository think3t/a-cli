"""
a-cli 主入口
用法:
  a <自然语言描述>          # 生成并执行命令
  a --copy <描述>           # 生成命令但只复制到剪贴板
  a config                  # 打开/查看配置文件
  a history                 # 查看历史记录
"""
import sys
import click
from pathlib import Path
from rich.console import Console

console = Console()


SUBCOMMANDS = ("config", "history")


@click.command(context_settings={"help_option_names": ["-h", "--help"], "ignore_unknown_options": True})
@click.argument("args", nargs=-1, required=False, type=click.UNPROCESSED)
@click.option("--copy", "-c", is_flag=True, help="只复制到剪贴板，不执行")
@click.option("--explain/--no-explain", default=None, help="显示/隐藏命令说明")
@click.option("--num", "-n", default=None, type=int, help="最多返回 N 个建议")
@click.version_option(package_name="a-cli", prog_name="a")
def cli(args, copy, explain, num):
    """
    \b
    ╔══════════════════════════════════╗
    ║   a — 自然语言 → Shell 命令      ║
    ╚══════════════════════════════════╝

    示例:
      a 查找当前目录下大于 100MB 的文件
      a 压缩 dist 目录为 dist.tar.gz
      a --copy 列出所有监听 8080 端口的进程

    子命令:
      a config              查看或编辑配置文件
      a config --edit       用 $EDITOR 打开配置
      a history             查看执行历史记录
      a history --clear     清空历史记录
    """
    # 手动路由子命令
    if args and args[0] in SUBCOMMANDS:
        sub_name = args[0]
        sub_args = args[1:]
        if sub_name == "config":
            _handle_config(sub_args)
        elif sub_name == "history":
            _handle_history(sub_args)
        return

    if not args:
        click.echo(cli.get_help(ctx=click.Context(cli)))
        return

    query_str = " ".join(args).strip()
    if not query_str:
        click.echo(cli.get_help(ctx=click.Context(cli)))
        return

    # ── 延迟导入，避免启动时加载慢 ──────────────────────────────────────────
    from .config import load_config, ensure_config_dir, detect_shell, update_shell_config
    from .llm import query_llm
    from .ui import display_and_select, show_loading, show_executing, show_cancelled, show_copied, find_placeholders, fill_placeholders, check_and_warn_high_risk
    from .executor import execute_command, copy_to_clipboard

    ensure_config_dir()
    config = load_config()

    # ── 首次运行：检测并确认 shell 类型 ──────────────────────────────────────
    if not config.behavior.shell_type:
        detected = detect_shell()
        console.print(f"\n[dim]检测到当前 shell: [/dim][bold cyan]{detected}[/bold cyan]")
        console.print("[dim]这将影响生成的命令语法（不同 shell 有差异）[/dim]\n")

        from InquirerPy import inquirer
        choices = ["bash", "zsh", "fish", "sh", "pwsh", "powershell", "cmd"]
        # 将检测到的放在首位
        if detected in choices:
            choices.remove(detected)
            choices.insert(0, f"{detected} (检测到)")

        selected = inquirer.select(
            message="请确认你的 shell 类型:",
            choices=choices,
            default=f"{detected} (检测到)",
        ).execute()

        # 提取实际的 shell 名称
        shell_type = selected.split(" ")[0] if " " in selected else selected
        update_shell_config(shell_type)
        config.behavior.shell_type = shell_type
        console.print(f"\n[green]✓[/green] 已设置 shell 类型为: [bold]{shell_type}[/bold]")
        console.print("[dim]可随时通过 'a config --edit' 修改[/dim]\n")

    # 命令行参数覆盖配置
    if num is not None:
        config.model.max_suggestions = max(1, min(num, 10))
    show_exp = config.behavior.show_explanation if explain is None else explain

    # 1. 调用大模型
    show_loading(query_str)
    with console.status("[dim]思考中…[/dim]", spinner="dots"):
        suggestions = query_llm(query_str, config)

    # 2. 展示 + 用户选择
    selected = display_and_select(
        suggestions,
        show_explanation=show_exp,
        auto_confirm_single=config.behavior.auto_execute_single,
    )

    if selected is None:
        show_cancelled()
        return

    # 2.5 检测并填充占位符
    placeholders = find_placeholders(selected)
    if placeholders:
        filled = fill_placeholders(selected, placeholders)
        if filled is None:
            return  # 用户取消
        selected = filled

    # 2.6 高风险命令安全检查
    if not check_and_warn_high_risk(
        selected,
        enable_check=config.safety.enable_safety_check,
        custom_patterns=config.safety.custom_patterns if config.safety.custom_patterns else None,
    ):
        return  # 用户取消执行

    # 3. 执行 or 复制
    if copy:
        ok = copy_to_clipboard(selected)
        if ok:
            show_copied(selected)
        else:
            console.print("[yellow]⚠ 剪贴板不可用，请手动复制：[/yellow]")
            console.print(f"  [bold cyan]{selected}[/bold cyan]\n")
    else:
        show_executing(selected)
        sys.exit(execute_command(selected))


# ── 子命令处理函数 ────────────────────────────────────────────────────────────


def _parse_flags(argv, flag_map):
    """简易参数解析：从 argv 列表中提取标志位和参数值。

    Args:
        argv: 参数列表，如 ['--edit', '-n', '50']
        flag_map: {长标志: 短标志} 或 {长标志: None} 的映射

    Returns:
        (flags_set, remaining, named_values)
        - flags_set: 被设置的标志名集合
        - remaining: 未识别的剩余参数
        - named_values: {标志名: 值}（如 -n 后面跟的数字）
    """
    flags_set = set()
    remaining = []
    named_values = {}
    short_to_long = {v: k for k, v in flag_map.items() if v is not None}
    all_short = set(short_to_long.keys())

    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg.startswith("--") and arg[2:] in flag_map:
            flags_set.add(arg[2:])
        elif arg.startswith("-") and len(arg) == 2 and arg[1] in all_short:
            long_name = short_to_long[arg[1]]
            flags_set.add(long_name)
        elif arg.startswith("-") and len(arg) == 2 and arg[1] not in all_short:
            # 带值的短选项（如 -n 50）
            long_name = _short_option_with_value(arg[1])
            if long_name and i + 1 < len(argv):
                named_values[long_name] = argv[i + 1]
                i += 2
                continue
            else:
                remaining.append(arg)
        elif arg.startswith("--") and arg.endswith("=val"):
            # --lines=20 格式
            key = arg[2:].split("=", 1)[0]
            named_values[key] = arg[2:].split("=", 1)[1]
        else:
            remaining.append(arg)
        i += 1

    return flags_set, remaining, named_values


def _short_option_with_value(short_char):
    """已知带值的短选项映射"""
    mapping = {
        "n": "lines",
        "e": "edit",
    }
    return mapping.get(short_char)


def _handle_config(sub_args):
    """处理 config 子命令"""
    from .config import get_config_path, ensure_config_dir
    import os

    flags, _, _ = _parse_flags(list(sub_args), {"edit": "e"})
    ensure_config_dir()
    cfg_path = get_config_path()
    console.print(f"[dim]配置文件路径：[/dim][bold]{cfg_path}[/bold]")

    if "edit" in flags:
        editor = os.environ.get("EDITOR", "nano")
        import subprocess
        subprocess.run([editor, str(cfg_path)])
    else:
        if cfg_path.exists():
            console.print(cfg_path.read_text())
        else:
            console.print("[dim]配置文件不存在，将使用默认值[/dim]")


def _handle_history(sub_args):
    """处理 history 子命令"""
    from .config import load_config
    flags, _, values = _parse_flags(list(sub_args), {"clear": None, "lines": "n"})
    history_path = Path(load_config().behavior.history_file)

    if "clear" in flags:
        if history_path.exists():
            history_path.write_text("")
            console.print("[ok]历史记录已清空[/ok]")
        return

    lines = int(values.get("lines", 20))

    if not history_path.exists() or history_path.stat().st_size == 0:
        console.print("[dim]暂无历史记录[/dim]")
        return

    all_lines = history_path.read_text(encoding="utf-8").splitlines()
    recent = all_lines[-lines:]
    for line in recent:
        console.print(f"  {line}")
    console.print(f"\n[dim]共 {len(all_lines)} 条，显示最近 {len(recent)} 条[/dim]")


def main():
    cli()


if __name__ == "__main__":
    main()
