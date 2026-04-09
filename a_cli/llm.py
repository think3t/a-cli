"""
大模型调用模块
- 支持 OpenAI 兼容接口（OpenAI、Azure、本地 Ollama 等）
- 返回结构化的命令建议列表
"""
import json
import os
import platform
import subprocess
import sys
from dataclasses import dataclass
from typing import Optional

from .config import Config


@dataclass
class CommandSuggestion:
    command: str          # 完整可执行的命令
    explanation: str      # 简短说明（一句话）
    confidence: float     # 置信度 0-1（模型自评）


SYSTEM_PROMPT = """\
You are a precise shell command assistant. The user will describe what they want to do in natural language.
Your job: return a JSON array of shell command suggestions (1 to {max_suggestions}).

Output ONLY valid JSON. No markdown fences, no extra text.
Schema (array of objects):
[
  {{
    "command": "<full executable command with all flags>",
    "explanation": "<one-sentence Chinese description of what this command does>",
    "confidence": <float 0.0-1.0>
  }}
]

Rules:
- Commands must be correct, complete, and ready to run — no placeholders unless unavoidable.
- Sort by confidence descending.
- If unavoidable placeholders exist, use {{UPPERCASE}} format like {{FILE_PATH}} or {{PORT}}.
- Target shell: {shell} — CRITICAL: all commands MUST use syntax valid for this specific shell.
  For fish: NO bash brace expansion ({{1..10}}), NO $((expr)), use `seq` instead. NO `[[ ]]`, use `test` or `begin/end`. NO `&&`/`||` in conditionals, use `; and`/`; or`.
  For zsh/bash: brace expansion ({{1..10}}), [[ ]], &&, || are all valid.
  When in doubt, use portable POSIX syntax or simple pipe chains.
- Target OS: {os_info}
  CRITICAL: Commands MUST be fully compatible with the exact OS distribution and version shown above.
  Different distros/versions have different package managers, flag syntax, and tool availability:
  - Debian/Ubuntu use `apt` (not `dnf`/`yum`/`pacman`); Alpine uses `apk`.
  - macOS (Darwin) requires Homebrew (`brew`) for most packages; flags often differ from GNU versions (e.g. `sed -i ''` vs `sed -i`).
  - Consider version-specific differences: older distros may lack certain flags or tools.
  - When multiple tools exist (e.g. `ip` vs `ifconfig`), prefer the one appropriate for this OS version.
  If you are unsure about tool/flag availability on this specific OS, say so in the explanation.
- Respond in JSON only.
"""

USER_PROMPT_TEMPLATE = "I want to: {query}"


def _get_os_info() -> str:
    """获取详细的操作系统信息（发行版 + 版本号）"""
    system = platform.system()

    if system == "Linux":
        # 优先解析 /etc/os-release 获取发行版详情
        os_release_path = "/etc/os-release"
        pretty_name = ""
        if os.path.isfile(os_release_path):
            try:
                with open(os_release_path, encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("PRETTY_NAME="):
                            # 去除引号：PRETTY_NAME="Alpine Linux v3.23"
                            pretty_name = line.split("=", 1)[1].strip('"')
                            break
            except OSError:
                pass

        if pretty_name:
            return f"{system} ({pretty_name})"

        # 回退：尝试 lsb_release
        try:
            result = subprocess.run(
                ["lsb_release", "-ds"],
                capture_output=True, text=True, timeout=3,
            )
            if result.returncode == 0:
                distro = result.stdout.strip()
                return f"{system} ({distro})"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # 再回退：尝试 /etc/redhat-release 等
        for fallback_file in (
            "/etc/redhat-release",
            "/etc/fedora-release",
            "/etc/centos-release",
            "/etc/alpine-release",
        ):
            if os.path.isfile(fallback_file):
                try:
                    with open(fallback_file, encoding="utf-8") as f:
                        content = f.read().strip()
                        return f"{system} ({content})"
                except OSError:
                    pass

        return system

    elif system == "Darwin":
        # macOS: 通过 sw_vers 获取版本
        try:
            result = subprocess.run(
                ["sw_vers"],
                capture_output=True, text=True, timeout=3,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().splitlines()
                parts = [l.split(":", 1)[1].strip() for l in lines if ":" in l]
                if len(parts) >= 3:
                    return f"{system} ({parts[0]} {parts[1]} {parts[2]})"
                elif parts:
                    return f"{system} ({parts[0]})"
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # 回退到 platform.mac_ver()
        mac_ver = platform.mac_ver()[0]
        if mac_ver:
            return f"{system} (macOS {mac_ver})"
        return system

    elif system == "Windows":
        ver = platform.win32_ver()
        # ver = (release, version, csd, ptype)
        release, version, csd, ptype = ver
        parts = []
        if release:
            parts.append(release)
        if version:
            parts.append(f"Build {version}")
        if csd:
            parts.append(csd)
        if ptype:
            parts.append(ptype)
        if parts:
            return f"{system} ({' '.join(parts)})"
        return system

    return system


def _build_messages(query: str, max_suggestions: int, shell: str) -> list[dict]:
    os_info = _get_os_info()
    system = SYSTEM_PROMPT.format(
        max_suggestions=max_suggestions,
        shell=shell,
        os_info=os_info,
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": USER_PROMPT_TEMPLATE.format(query=query)},
    ]


def _parse_suggestions(raw: str) -> list[CommandSuggestion]:
    """解析模型返回的 JSON，容错处理"""
    # 去除可能的 markdown 代码块包裹
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

    data = json.loads(text)
    if not isinstance(data, list):
        raise ValueError(f"期望 JSON 数组，得到: {type(data)}")

    suggestions = []
    for item in data:
        if not isinstance(item, dict):
            continue
        cmd = str(item.get("command", "")).strip()
        if not cmd:
            continue
        suggestions.append(
            CommandSuggestion(
                command=cmd,
                explanation=str(item.get("explanation", "")).strip(),
                confidence=float(item.get("confidence", 0.8)),
            )
        )
    return suggestions


def _build_create_kwargs(cfg) -> dict:
    """根据模型配置构建 chat.completions.create 的额外参数。

    不同提供商的深度思考参数各不相同，这里做统一适配：
    - 火山方舟（豆包）：
      · extra_body.thinking = {"type": "enabled"|"disabled"|"auto"}
      · reasoning_effort = "minimal"|"low"|"medium"|"high"（顶层参数）
    - OpenAI o1/o3 系列：reasoning_effort = "low"|"medium"|"high"
    - DeepSeek-R1 等自回归思考模型：通常只需设置 temperature=0.6
    - Anthropic：通过 provider 预留扩展
    """
    kwargs = {
        "temperature": cfg.temperature,
        # 默认 8192：推理模型（如 stepfun/DeepSeek-R1）需要大量 token 用于内部思考，
        # 若 max_tokens 过小会导致思考耗尽预算、content 为空（finish_reason=length）
        "max_tokens": cfg.max_tokens if cfg.max_tokens > 0 else 8192,
    }

    # thinking_mode: "enabled" / "disabled" / "auto"
    # 仅在非默认值("auto")时通过 extra_body 传递
    if cfg.thinking_mode and cfg.thinking_mode != "auto":
        kwargs["extra_body"] = {"thinking": {"type": cfg.thinking_mode}}

    # reasoning_effort: "minimal" / "low" / "medium" / "high"
    # 火山方舟和 OpenAI 都作为顶层参数传递
    # 注意：当 thinking_mode="disabled" 时，reasoning_effort 只能是 "minimal"
    valid_efforts = ("minimal", "low", "medium", "high")
    if cfg.reasoning_effort and cfg.reasoning_effort in valid_efforts:
        if cfg.thinking_mode == "disabled" and cfg.reasoning_effort != "minimal":
            # thinking disabled + 非 minimal effort 会触发 API 400 错误
            # 自动降级为 minimal 或直接不传 reasoning_effort
            pass
        else:
            kwargs["reasoning_effort"] = cfg.reasoning_effort

    return kwargs


def query_llm(query: str, config: Config) -> list[CommandSuggestion]:
    """
    调用大模型，返回命令建议列表。
    使用 openai 库，支持任何 OpenAI 兼容接口。
    """
    try:
        from openai import OpenAI
    except ImportError:
        print(
            "[错误] 缺少依赖: openai\n请运行: pip install openai",
            file=sys.stderr,
        )
        sys.exit(1)

    cfg = config.model
    if not cfg.api_key:
        print(
            "[错误] 未配置 API Key\n"
            "请设置环境变量: export A_API_KEY=your_key\n"
            f"或编辑配置文件: ~/.config/a-cli/config.toml",
            file=sys.stderr,
        )
        sys.exit(1)

    client = OpenAI(api_key=cfg.api_key, base_url=cfg.api_base)

    # 确定 shell 类型
    shell = config.behavior.shell_type
    if not shell:
        from .config import detect_shell
        shell = detect_shell()

    messages = _build_messages(query, cfg.max_suggestions, shell)

    # 构建请求参数（含深度思考适配）
    create_kwargs = _build_create_kwargs(cfg)

    try:
        response = client.chat.completions.create(
            model=cfg.model_name,
            messages=messages,
            **create_kwargs,
        )
    except Exception as e:
        print(f"[错误] 模型调用失败: {e}", file=sys.stderr)
        sys.exit(1)

    # 提取模型响应内容（兼容不同模型的响应格式）
    choice = response.choices[0]
    message = choice.message
    raw = (message.content or "").strip()

    # 兼容 OpenRouter 部分免费模型：content 为空时尝试从 reasoning_content 获取
    if not raw and hasattr(message, "reasoning_content") and message.reasoning_content:
        raw = message.reasoning_content.strip()

    if not raw:
        # 调试信息：输出完整响应结构，方便排查问题
        print(
            f"[错误] 模型返回空响应\n"
            f"  model={cfg.model_name}\n"
            f"  finish_reason={choice.finish_reason}\n"
            f"  message keys={list(message.__dict__.keys()) if hasattr(message, '__dict__') else 'N/A'}\n"
            f"  usage={response.usage}",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        suggestions = _parse_suggestions(raw)
    except Exception as e:
        print(f"[错误] 解析模型响应失败: {e}\n原始内容: {raw[:300]}", file=sys.stderr)
        sys.exit(1)

    if not suggestions:
        print("[错误] 模型未返回任何有效命令建议", file=sys.stderr)
        sys.exit(1)

    return suggestions
