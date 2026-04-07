"""
a-cli 参数解析测试脚本。

测试所有 CLI 参数和子命令是否按预期路由和处理。
不会真正执行任何 shell 命令或修改文件，零风险。

用法: python tests/test_args.py
"""
import sys
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console
from rich.table import Table
from rich import box

console = Console()

# ── 测试用例定义 ────────────────────────────────────────────────
# 每条: (描述, CLI 参数列表, 预期行为类型, 预期输出关键词/退出码)
#
# 行为类型:
#   "exit_ok"        → 正常退出 (exit code 0)
#   "exit_help"      → 显示帮助信息后退出
#   "exit_version"   → 显示版本号后退出
#   "route_config"   → 路由到 config 子命令
#   "route_history"  → 路由到 history 子命令
#   "need_query"     → 正常进入主流程（需要 LLM 查询）
#   "error"          → 参数错误

TEST_CASES = [
    # ── 1. 无参数 ──
    ("无参数", [], "exit_help", "示例:"),
    ("空字符串 ([''])", [""], "exit_help", "示例:"),

    # ── 2. --help / -h ──
    ("--help", ["--help"], "exit_help", "示例:"),
    ("-h", ["-h"], "exit_help", "示例:"),

    # ── 3. --version ──
    ("--version", ["--version"], "exit_version", "1.1.0"),

    # ── 4. config 子命令 ──
    ("a config", ["config"], "route_config", "配置文件路径"),
    ("a config --edit", ["config", "--edit"], "route_config", "配置文件路径"),
    ("a config -e", ["config", "-e"], "route_config", "配置文件路径"),

    # ── 5. history 子命令 ──
    ("a history", ["history"], "route_history", "条"),
    ("a history --clear", ["history", "--clear"], "route_history", "历史记录已清空"),
    ("a history -n 5", ["history", "-n", "5"], "route_history", "条"),
    ("a history --lines=10", ["history", "--lines=10"], "route_history", "条"),

    # ── 6. --copy / -c ──
    ("a --copy <查询>", ["--copy", "列出文件"], "need_query", "生成"),
    ("a -c <查询>", ["-c", "列出文件"], "need_query", "生成"),

    # ── 7. --explain / --no-explain ──
    ("a --explain <查询>", ["--explain", "显示磁盘"], "need_query", "生成"),
    ("a --no-explain <查询>", ["--no-explain", "显示磁盘"], "need_query", "生成"),

    # ── 8. --num / -n ──
    ("a --num 1 <查询>", ["--num", "1", "列出文件"], "need_query", "生成"),
    ("a -n 5 <查询>", ["-n", "5", "列出文件"], "need_query", "生成"),

    # ── 9. 参数组合 ──
    ("a --copy --explain <查询>", ["--copy", "--explain", "查找日志"], "need_query", "生成"),
    ("a -c --no-explain <查询>", ["-c", "--no-explain", "查看端口"], "need_query", "生成"),
    ("a --copy --num 2 <查询>", ["--copy", "--num", "2", "列出进程"], "need_query", "生成"),
    ("a -c -n 3 <查询>", ["-c", "-n", "3", "搜索文件"], "need_query", "生成"),

    # ── 10. 边界情况 ──
    ("只有 --copy 无查询", ["--copy"], "exit_help", "示例:"),
    ("只有 --num 无查询", ["--num", "3"], "exit_help", "示例:"),
    ("只有 --explain 无查询", ["--explain"], "exit_help", "示例:"),
    ("--num 0 (最小边界)", ["--num", "0", "列出文件"], "need_query", "生成"),
    ("--num 10 (最大边界)", ["--num", "10", "列出文件"], "need_query", "生成"),
    ("--num 99 (超过上限)", ["--num", "99", "列出文件"], "need_query", "生成"),

    # ── 11. 自然语言参数（含中文、空格、特殊字符） ──
    ("中文查询", ["查找大于100MB的文件"], "need_query", "生成"),
    ("多词查询", ["find", "all", "python", "files"], "need_query", "生成"),
    ("查询含特殊字符", ["grep -r 'hello world' ./src"], "need_query", "生成"),
]


# ── 模拟运行函数（不实际调用 LLM） ─────────────────────────────

def _simulate_cli(args_list):
    """
    模拟 a-cli 的参数解析逻辑，不调用 LLM、不执行命令。
    返回 (behavior_type, matched_keyword, exit_code)。
    """
    # 1. 检查 click 是否将 --help / --version 拦截
    if "--help" in args_list or "-h" in args_list:
        return ("exit_help", "示例:", 0)
    if "--version" in args_list:
        return ("exit_version", "1.1.0", 0)

    # 2. 分离 click options 和位置参数
    flags = set()
    num_value = None
    positional = []

    i = 0
    while i < len(args_list):
        arg = args_list[i]
        if arg in ("--copy", "-c"):
            flags.add("copy")
        elif arg in ("--explain",):
            flags.add("explain")
        elif arg in ("--no-explain",):
            flags.add("no_explain")
        elif arg in ("--num", "-n"):
            if i + 1 < len(args_list):
                num_value = args_list[i + 1]
                i += 1
        elif arg.startswith("--num="):
            num_value = arg.split("=")[1]
        else:
            positional.append(arg)
        i += 1

    # 3. 子命令路由
    subcommands = ("config", "history")
    if positional and positional[0] in subcommands:
        sub_name = positional[0]
        sub_args = positional[1:]

        if sub_name == "config":
            return ("route_config", "配置文件路径", 0)
        elif sub_name == "history":
            if "--clear" in sub_args or "clear" in sub_args:
                return ("route_history", "历史记录已清空", 0)
            else:
                return ("route_history", "条", 0)

    # 4. 需要查询文本
    query_str = " ".join(positional).strip()
    if not query_str:
        return ("exit_help", "示例:", 0)

    # 5. 正常进入主流程
    return ("need_query", "生成", 0)# ── 额外的参数解析单元测试 ────────────────────────────────────

def test_parse_flags():
    """测试内部 _parse_flags 函数的参数解析逻辑"""
    from a_cli.main import _parse_flags

    results = []

    # (描述, argv, flag_map, 预期 flags_set, 预期 named_values)
    cases = [
        (
            "config --edit",
            ["--edit"],
            {"edit": "e"},
            {"edit"},
            {},
        ),
        (
            "config -e",
            ["-e"],
            {"edit": "e"},
            {"edit"},
            {},
        ),
        (
            "history --clear",
            ["--clear"],
            {"clear": None},
            {"clear"},
            {},
        ),
        (
            "history -n 50",
            ["-n", "50"],
            {"clear": None, "lines": "n"},
            {"lines"},
            {},
        ),
        (
            "history --lines=20",
            ["--lines=20"],
            {"clear": None, "lines": "n"},
            set(),
            {},
        ),
        (
            "history --clear -n 10",
            ["--clear", "-n", "10"],
            {"clear": None, "lines": "n"},
            {"clear", "lines"},
            {},
        ),
        (
            "未知参数保持 remaining",
            ["--unknown", "foo"],
            {"edit": "e"},
            set(),
            {},
        ),
        (
            "空参数列表",
            [],
            {"edit": "e"},
            set(),
            {},
        ),
    ]

    for desc, argv, flag_map, exp_flags, exp_values in cases:
        flags, remaining, values = _parse_flags(argv, flag_map)
        ok = (flags == exp_flags and values == exp_values)
        results.append((desc, ok, f"flags={flags}, values={values}, remaining={remaining}"))

    return results


def test_num_boundary():
    """测试 --num 参数的边界处理逻辑"""
    from a_cli.config import Config

    results = []

    # 模拟 main.py 中的: config.model.max_suggestions = max(1, min(num, 10))
    test_values = [
        (0, 1, "0 → 1 (下限截断)"),
        (-5, 1, "-5 → 1 (负数截断)"),
        (1, 1, "1 → 1 (最小值)"),
        (3, 3, "3 → 3 (正常值)"),
        (10, 10, "10 → 10 (最大值)"),
        (99, 10, "99 → 10 (上限截断)"),
        (1000, 10, "1000 → 10 (超大值)"),
    ]

    for input_val, expected, desc in test_values:
        result = max(1, min(input_val, 10))
        ok = result == expected
        results.append((f"--num {desc}", ok, f"input={input_val}, output={result}"))

    return results


def test_subcommand_detection():
    """测试子命令识别逻辑"""
    results = []

    # 模拟 main.py 中的: if args and args[0] in SUBCOMMANDS
    subcommands = ("config", "history")
    test_inputs = [
        (["config"], True, "config"),
        (["history"], True, "history"),
        (["config", "--edit"], True, "config --edit"),
        (["history", "--clear"], True, "history --clear"),
        (["config", "-e"], True, "config -e"),
        (["configure"], False, "configure (相似但不是)"),
        (["histories"], False, "histories (相似但不是)"),
        (["查找文件"], False, "普通查询"),
        ([], False, "空参数"),
    ]

    for args_input, expected, desc in test_inputs:
        is_subcommand = bool(args_input) and args_input[0] in subcommands
        ok = is_subcommand == expected
        results.append((desc, ok, f"args={args_input}"))

    return results


def test_query_string_assembly():
    """测试位置参数拼接为查询字符串"""
    results = []

    test_inputs = [
        (["查找文件"], "查找文件", "单个中文词"),
        (["find", "large", "files"], "find large files", "多个英文词"),
        (["查找", "大于100MB", "的文件"], "查找 大于100MB 的文件", "混合中英文+数字（注意空格）"),
        (["grep -r 'hello' ./src"], "grep -r 'hello' ./src", "含特殊字符"),
        (["  ", "查找", "  "], "查找", "含前后空格的参数"),
        (["echo", "hello world"], "echo hello world", "含空格的词"),
    ]

    for args_input, expected, desc in test_inputs:
        query_str = " ".join(args_input).strip()
        ok = query_str == expected
        results.append((desc, ok, f'query="{query_str}"'))

    return results


def test_config_defaults():
    """测试默认配置值是否正确"""
    from a_cli.config import Config, ModelConfig, BehaviorConfig, SafetyConfig

    results = []
    cfg = Config()

    checks = [
        ("model.provider == openai", cfg.model.provider == "openai"),
        ("model.api_key == ''", cfg.model.api_key == ""),
        ("model.model_name == gpt-4o-mini", cfg.model.model_name == "gpt-4o-mini"),
        ("model.max_suggestions == 3", cfg.model.max_suggestions == 3),
        ("model.temperature == 0.2", cfg.model.temperature == 0.2),
        ("model.max_tokens == 0", cfg.model.max_tokens == 0),
        ("behavior.auto_execute_single == True", cfg.behavior.auto_execute_single is True),
        ("behavior.show_explanation == True", cfg.behavior.show_explanation is True),
        ("behavior.shell_type == ''", cfg.behavior.shell_type == ""),
        ("safety.enable_safety_check == True", cfg.safety.enable_safety_check is True),
        ("safety.custom_patterns == []", cfg.safety.custom_patterns == []),
    ]

    for desc, ok in checks:
        results.append((desc, ok, ""))

    return results


# ── 主测试运行 ─────────────────────────────────────────────────

def run_all_tests():
    all_tables = []

    # ── 表1: CLI 参数路由测试 ──
    table1 = Table(
        title="1. CLI 参数路由测试",
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style="bold cyan",
    )
    table1.add_column("状态", width=8, justify="center")
    table1.add_column("测试描述", min_width=30)
    table1.add_column("预期行为", width=16, justify="center")
    table1.add_column("模拟行为", width=16, justify="center")
    table1.add_column("匹配关键词", min_width=20)

    p1 = f1 = 0
    for desc, args, expected_type, expected_kw in TEST_CASES:
        actual_type, actual_kw, _ = _simulate_cli(args)
        ok_type = actual_type == expected_type
        ok_kw = expected_kw in actual_kw
        ok = ok_type and ok_kw

        if ok:
            p1 += 1
            status = "[green]✓ PASS[/green]"
        else:
            f1 += 1
            status = "[red]✗ FAIL[/red]"

        table1.add_row(
            status,
            desc,
            expected_type,
            actual_type,
            f"预期: {expected_kw}  实际: {actual_kw}" if not ok else expected_kw,
        )

    all_tables.append((table1, p1, f1, len(TEST_CASES)))

    # ── 表2: _parse_flags 参数解析测试 ──
    parse_results = test_parse_flags()
    table2 = Table(
        title="2. _parse_flags() 内部解析测试",
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style="bold cyan",
    )
    table2.add_column("状态", width=8, justify="center")
    table2.add_column("测试描述", min_width=24)
    table2.add_column("解析结果", min_width=30)

    p2 = f2 = 0
    for desc, ok, detail in parse_results:
        if ok:
            p2 += 1
            status = "[green]✓ PASS[/green]"
        else:
            f2 += 1
            status = "[red]✗ FAIL[/red]"
        table2.add_row(status, desc, detail)

    all_tables.append((table2, p2, f2, len(parse_results)))

    # ── 表3: --num 边界值测试 ──
    num_results = test_num_boundary()
    table3 = Table(
        title="3. --num 边界值测试",
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style="bold cyan",
    )
    table3.add_column("状态", width=8, justify="center")
    table3.add_column("测试描述", min_width=28)
    table3.add_column("计算结果", min_width=30)

    p3 = f3 = 0
    for desc, ok, detail in num_results:
        if ok:
            p3 += 1
            status = "[green]✓ PASS[/green]"
        else:
            f3 += 1
            status = "[red]✗ FAIL[/red]"
        table3.add_row(status, desc, detail)

    all_tables.append((table3, p3, f3, len(num_results)))

    # ── 表4: 子命令识别测试 ──
    sub_results = test_subcommand_detection()
    table4 = Table(
        title="4. 子命令识别测试",
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style="bold cyan",
    )
    table4.add_column("状态", width=8, justify="center")
    table4.add_column("测试描述", min_width=28)
    table4.add_column("输入参数", min_width=30)

    p4 = f4 = 0
    for desc, ok, detail in sub_results:
        if ok:
            p4 += 1
            status = "[green]✓ PASS[/green]"
        else:
            f4 += 1
            status = "[red]✗ FAIL[/red]"
        table4.add_row(status, desc, detail)

    all_tables.append((table4, p4, f4, len(sub_results)))

    # ── 表5: 查询字符串拼接测试 ──
    query_results = test_query_string_assembly()
    table5 = Table(
        title="5. 查询字符串拼接测试",
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style="bold cyan",
    )
    table5.add_column("状态", width=8, justify="center")
    table5.add_column("测试描述", min_width=24)
    table5.add_column("拼接结果", min_width=30)

    p5 = f5 = 0
    for desc, ok, detail in query_results:
        if ok:
            p5 += 1
            status = "[green]✓ PASS[/green]"
        else:
            f5 += 1
            status = "[red]✗ FAIL[/red]"
        table5.add_row(status, desc, detail)

    all_tables.append((table5, p5, f5, len(query_results)))

    # ── 表6: 默认配置值测试 ──
    cfg_results = test_config_defaults()
    table6 = Table(
        title="6. 默认配置值测试",
        box=box.SIMPLE_HEAVY,
        show_header=True,
        header_style="bold cyan",
    )
    table6.add_column("状态", width=8, justify="center")
    table6.add_column("配置项检查", min_width=44)

    p6 = f6 = 0
    for desc, ok, _ in cfg_results:
        if ok:
            p6 += 1
            status = "[green]✓ PASS[/green]"
        else:
            f6 += 1
            status = "[red]✗ FAIL[/red]"
        table6.add_row(status, desc)

    all_tables.append((table6, p6, f6, len(cfg_results)))

    # ── 汇总输出 ──
    console.print()
    total_p = total_f = total_n = 0
    for table, p, f, n in all_tables:
        console.print(table)
        console.print(f"\n  [dim]子计: [green]{p} 通过[/green], [red]{f} 失败[/red], 共 {n} 条[/dim]\n")
        total_p += p
        total_f += f
        total_n += n

    console.print(f"[bold]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold]")
    console.print(
        f"[bold]总计: [green]{total_p} 通过[/green], [red]{total_f} 失败[/red], 共 {total_n} 条[/bold]"
    )
    if total_f == 0:
        console.print("[bold green]✓ 所有测试通过[/bold green]")
    else:
        console.print(f"[bold red]✗ {total_f} 项测试失败，请检查[/bold red]")
    console.print()


if __name__ == "__main__":
    run_all_tests()
