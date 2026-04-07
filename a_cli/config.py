"""
配置管理模块
优先级: 环境变量 > ~/.config/a-cli/config.toml > 默认值
"""
import os
import sys
import tomllib
import tomli_w
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

CONFIG_DIR = Path.home() / ".config" / "a-cli"
CONFIG_FILE = CONFIG_DIR / "config.toml"

DEFAULT_CONFIG = {
    "model": {
        "provider": "openai",
        "api_base": "https://api.openai.com/v1",
        "api_key": "",
        "model_name": "gpt-4o-mini",
        "max_suggestions": 3,
        "temperature": 0.2,
        "max_tokens": 0,               # 0=自动（默认8192），推理模型建议 16384+
        "thinking_mode": "auto",          # 深度思考: "enabled"/"disabled"/"auto"
        "reasoning_effort": "",           # 思考强度: "minimal"/"low"/"medium"/"high"，空=不指定
    },
    "behavior": {
        "auto_execute_single": True,
        "show_explanation": True,
        "history_file": str(Path.home() / ".local" / "share" / "a-cli" / "history.log"),
        "shell_type": "",
    },
    "safety": {
        "enable_safety_check": True,
        "custom_patterns": [],
    },
}


@dataclass
class ModelConfig:
    provider: str = "openai"
    api_base: str = "https://api.openai.com/v1"
    api_key: str = ""
    model_name: str = "gpt-4o-mini"
    max_suggestions: int = 3
    temperature: float = 0.2
    max_tokens: int = 0                 # 0=自动（默认8192），推理模型建议 16384+
    thinking_mode: str = "auto"         # 深度思考: "enabled"/"disabled"/"auto"
    reasoning_effort: str = ""          # 思考强度: "minimal"/"low"/"medium"/"high"


@dataclass
class BehaviorConfig:
    auto_execute_single: bool = True
    show_explanation: bool = True
    history_file: str = str(Path.home() / ".local" / "share" / "a-cli" / "history.log")
    shell_type: str = ""  # bash/zsh/fish/pwsh 等


@dataclass
class SafetyConfig:
    enable_safety_check: bool = True
    custom_patterns: list[dict] = field(default_factory=list)  # 用户自定义风险模式


@dataclass
class Config:
    model: ModelConfig = field(default_factory=ModelConfig)
    behavior: BehaviorConfig = field(default_factory=BehaviorConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)


def _deep_merge(base: dict, override: dict) -> dict:
    """递归合并配置字典"""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config() -> Config:
    """加载并合并所有来源的配置"""
    merged = dict(DEFAULT_CONFIG)

    # 1. 读取配置文件
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "rb") as f:
                file_config = tomllib.load(f)
            merged = _deep_merge(merged, file_config)
        except Exception as e:
            print(f"[警告] 配置文件解析失败: {e}", file=sys.stderr)

    # 2. 环境变量覆盖（优先级最高）
    env_overrides = {
        "A_API_KEY": ("model", "api_key"),
        "A_API_BASE": ("model", "api_base"),
        "A_MODEL": ("model", "model_name"),
        "A_PROVIDER": ("model", "provider"),
        "OPENAI_API_KEY": ("model", "api_key"),  # 兼容标准 OpenAI 环境变量
    }
    for env_var, (section, key) in env_overrides.items():
        val = os.environ.get(env_var)
        if val:
            merged[section][key] = val

    model_cfg = ModelConfig(**merged["model"])
    behavior_cfg = BehaviorConfig(**{k: v for k, v in merged["behavior"].items() if k in BehaviorConfig.__dataclass_fields__})
    # safety 段中的 custom_patterns 保持为 list[dict] 传给 SafetyConfig
    safety_raw = merged.get("safety", {})
    safety_cfg = SafetyConfig(
        enable_safety_check=safety_raw.get("enable_safety_check", True),
        custom_patterns=safety_raw.get("custom_patterns", []),
    )
    return Config(model=model_cfg, behavior=behavior_cfg, safety=safety_cfg)


def ensure_config_dir():
    """确保配置目录存在，首次运行时创建示例配置"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    if not CONFIG_FILE.exists():
        _write_example_config()


def _write_example_config():
    """写入示例配置文件"""
    example = '''\
# a-cli 配置文件
# 文档: https://github.com/your-org/a-cli

[model]
# 服务商: openai | anthropic | 任何 OpenAI 兼容接口
provider = "openai"
api_base = "https://api.openai.com/v1"
api_key  = ""          # 或设置环境变量 A_API_KEY / OPENAI_API_KEY
model_name = "gpt-4o-mini"
max_suggestions = 3    # 最多返回几个建议命令
temperature = 0.2      # 越低越确定性
max_tokens = 0         # 0=自动（默认8192），推理模型(stepfun/deepseek-r1等)建议设为 16384+

# 深度思考配置（适用于豆包等支持思考模式的模型）
# thinking_mode = "auto"        # "enabled"(强制开启) / "disabled"(强制关闭) / "auto"(模型自行判断)
# reasoning_effort = "medium"   # "minimal"(关闭思考) / "low" / "medium" / "high"

[behavior]
auto_execute_single = true   # 只有一个结果时直接进入确认
show_explanation    = true   # 显示命令含义说明
shell_type = ""              # bash/zsh/fish/pwsh，留空自动检测

[safety]
# 高风险命令安全检查：内置 13 种危险模式，执行前强制二次确认
enable_safety_check = true   # 设为 false 可关闭安全检查

# 自定义高风险命令（可选）
# 每条规则包含 pattern(正则)、name、risk_level(1~5)、detail
# [[safety.custom_patterns]]
# pattern     = "my-dangerous-cmd\\s+.*"
# name        = "我的危险指令"
# risk_level  = 4
# detail      = "这条命令会做一些危险的事情"
'''
    CONFIG_FILE.write_text(example, encoding="utf-8")


def get_config_path() -> Path:
    return CONFIG_FILE


# ── Shell 类型检测与配置 ─────────────────────────────────────────────────────

SUPPORTED_SHELLS = ("bash", "zsh", "fish", "sh", "pwsh", "powershell", "cmd")


def detect_shell() -> str:
    """检测当前 shell 类型"""
    # 优先从 $SHELL 环境变量获取
    shell_path = os.environ.get("SHELL", "")
    if shell_path:
        shell_name = Path(shell_path).name.lower()
        # 处理常见变体
        if shell_name in SUPPORTED_SHELLS:
            return shell_name
        if "bash" in shell_name:
            return "bash"
        if "zsh" in shell_name:
            return "zsh"
        if "fish" in shell_name:
            return "fish"

    # Windows 环境
    if sys.platform == "win32":
        ps_module = os.environ.get("PSModulePath", "")
        if ps_module:
            return "pwsh"
        return "cmd"

    # 默认
    return "bash"


def update_shell_config(shell_type: str) -> None:
    """更新配置文件中的 shell_type"""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # 读取现有配置（如果存在）
    config_data = dict(DEFAULT_CONFIG)
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "rb") as f:
                file_config = tomllib.load(f)
            config_data = _deep_merge(config_data, file_config)
        except Exception:
            pass

    # 更新 shell_type
    if "behavior" not in config_data:
        config_data["behavior"] = {}
    config_data["behavior"]["shell_type"] = shell_type

    # 写回文件
    with open(CONFIG_FILE, "wb") as f:
        tomli_w.dump(config_data, f)
