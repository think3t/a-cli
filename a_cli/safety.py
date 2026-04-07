"""
高风险命令安全检查模块

功能：
- 内置 13 种高风险命令模式（正则匹配）
- 支持用户在配置文件 [safety.custom_patterns] 中自定义高风险指令
- 提供命令风险检测与分级
"""
import re
from dataclasses import dataclass
from typing import Optional


# ═══════════════════════════════════════════════════════════
#  内置高风险命令（按危险程度排序）
# ═══════════════════════════════════════════════════════════

@dataclass
class RiskPattern:
    """单个风险模式定义"""
    pattern: str           # 正则表达式
    name: str              # 风险名称/描述
    risk_level: int        # 风险等级 1-5，5 为最高
    detail: str            # 详细说明


BUILTIN_RISK_PATTERNS: list[RiskPattern] = [
    # ── 等级 5：毁灭性操作（不可逆）─────────────────────────────
    RiskPattern(
        pattern=r"rm\s+-rf\s+(?:--no-preserve-root\s+)?/(?!\w)",
        name="根目录删除",
        risk_level=5,
        detail="将递归强制删除整个根目录或关键系统目录，导致系统完全不可用！",
    ),
    RiskPattern(
        pattern=r"rm\s+-(?:[a-zA-Z]*r[a-zA-Z]*f|[a-zA-Z]*f[a-zA-Z]*r)\s+.*/(?:etc|usr|var|bin|sbin|lib|boot|sys|proc|dev)",
        name="系统目录删除",
        risk_level=5,
        detail="正在删除系统核心目录，可能导致操作系统无法启动！",
    ),
    RiskPattern(
        pattern=r"dd\s+.*of=/dev/(?:sd|hd|nvme|vd|mmcblk|xvd|fd)",
        name="磁盘覆写",
        risk_level=5,
        detail="dd 写入物理磁盘设备，将直接销毁整个磁盘数据和分区表！此操作不可逆！",
    ),
    RiskPattern(
        pattern=r":\s*\(\s*\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;|fork\s+bomb",
        name="Fork 炸弹",
        risk_level=5,
        detail='Fork 炸弹会耗尽所有系统进程资源，导致系统死锁需硬重启！（如 ":(){ :|:& };:"）',
    ),
    RiskPattern(
        pattern=r"mkfs(\.\w+)?\s+.*(/dev/(?:sd|hd|nvme|vd|mmcblk|xvd))",
        name="格式化磁盘",
        risk_level=5,
        detail="格式化物理磁盘设备，该操作将清除磁盘上所有数据且不可恢复！",
    ),

    # ── 等级 4：数据丢失风险（不可逆）─────────────────────────────
    RiskPattern(
        pattern=r"rm\s+-(?:[a-zA-Z]*r[a-zA-Z]*f|[a-zA-Z]*f[a-zA-Z]*r)\b",
        name="递归强制删除",
        risk_level=4,
        detail="'rm -rf' 将递归强制删除文件和目录，且不经过回收站，数据无法恢复！",
    ),
    RiskPattern(
        pattern=r"shred\s+.*(-[a-zA-Z]*z|-z)",
        name="安全擦除文件",
        risk_level=4,
        detail="shred -z 会多次覆写并清零文件，被擦除的数据几乎不可能恢复！",
    ),
    RiskPattern(
        pattern=r"chmod\s+-R\s+777\s+/|chown\s+-R\s+\S+\s+/",
        name="全局权限修改",
        risk_level=4,
        detail="对根目录递归设置 777 权限或更改所有者，将破坏系统安全模型！",
    ),
    RiskPattern(
        pattern=r"mv\s+.*?(/\S+)\s*/dev/null",
        name="移入黑洞",
        risk_level=4,
        detail="将文件移动到 /dev/null 相当于永久销毁该文件，数据不可恢复！",
    ),
    RiskPattern(
        pattern=r"DROP\s+(DATABASE|TABLE|SCHEMA)\s+(IF\s+EXISTS\s+)?[`'\"]?\w+[`'\"]?",
        name="数据库结构删除",
        risk_level=4,
        detail="DROP DATABASE/TABLE 将永久删除数据库或表及其所有数据！",
    ),

    # ── 扩展：覆盖更多危险模式 ──────────────────────────────────
    RiskPattern(
        pattern=r"curl\s+.*\|\s*(ba)?sh\b|wget\s+.*\|\s*(ba)?sh\b",
        name="远程脚本执行",
        risk_level=3,
        detail="从网络下载并直接执行 Shell 脚本，存在代码注入与供应链攻击风险！",
    ),
    RiskPattern(
        pattern=r">\s*\/dev\/sd|>\s*\/dev\/hd|>\s*\/dev\/nvme",
        name="磁盘截断写入",
        risk_level=5,
        detail="重定向输出到磁盘设备节点将破坏分区表和文件系统！",
    ),
    RiskPattern(
        pattern=r"iptables\s+-F|ufw\s+(disable|reset)|firewall-cmd\s+--permanent\s+--zone=.*--add-port=.*\b",
        name="防火墙规则修改",
        risk_level=3,
        detail="清空防火墙规则或开放端口可能暴露服务于公网攻击面之下！",
    ),
]


def _build_pattern_cache(builtin: list[RiskPattern], custom: list[RiskPattern]) -> list[tuple[re.Pattern, RiskPattern]]:
    """预编译所有正则表达式"""
    return [(re.compile(p.pattern), p) for p in (builtin + custom)]


def detect_risk(command: str, custom_patterns: Optional[list[RiskPattern]] = None) -> Optional[RiskPattern]:
    """
    检测命令是否匹配任何高风险模式。

    Args:
        command: 待检测的 shell 命令字符串
        custom_patterns: 用户自定义的额外风险模式列表

    Returns:
        匹配到的最高级别 RiskPattern，未匹配则返回 None
    """
    custom = custom_patterns or []
    all_patterns = _build_pattern_cache(BUILTIN_RISK_PATTERNS, custom)

    best_match: Optional[RiskPattern] = None
    for regex, rp in all_patterns:
        if regex.search(command):
            if best_match is None or rp.risk_level > best_match.risk_level:
                best_match = rp

    return best_match


def load_custom_risk_patterns(safety_config: Optional[dict] = None) -> list[RiskPattern]:
    """
    从配置中的 [safety.custom_patterns] 段加载用户自定义的高风险命令。

    配置示例：
        [safety]
        enable_safety_check = true

        [[safety.custom_patterns]]
        pattern = "my-dangerous-command"
        name   = "我的危险指令"
        risk_level = 4
        detail = "这是一条自定义的危险指令"

    Args:
        safety_config: 从 config.toml 中解析出的 [safety] 字段字典

    Returns:
        用户自定义的 RiskPattern 列表
    """
    if not safety_config:
        return []

    patterns_raw = safety_config.get("custom_patterns", [])
    if not isinstance(patterns_raw, list):
        return []

    result: list[RiskPattern] = []
    for item in patterns_raw:
        if not isinstance(item, dict):
            continue
        pat_str = item.get("pattern", "")
        if not pat_str:
            continue

        # 校验正则合法性
        try:
            re.compile(pat_str)
        except re.error as e:
            import warnings
            warnings.warn(f"[safety] 自定义风险模式正则无效 '{pat_str}': {e}")
            continue

        result.append(RiskPattern(
            pattern=pat_str,
            name=item.get("name", "自定义风险"),
            risk_level=int(item.get("risk_level", 3)),
            detail=item.get("detail", "用户自定义的高风险命令"),
        ))

    return result
