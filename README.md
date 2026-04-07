<div align="center">

# a-cli

**自然语言 → Shell 命令**

忘了参数？不用查文档，直接说人话。

[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

</div>

```bash
a 查找当前目录下大于 100MB 的文件
a 压缩 dist 目录为 dist.tar.gz，排除 node_modules
a 杀掉占用 8080 端口的所有进程
```

## ✨ 特性

- 🗣️ **自然语言输入** — 用中文/英文描述你想做的事，自动生成对应 Shell 命令
- 🎯 **多条建议 + 智能排序** — 按置信度排序，交互式选择最合适的命令
- 🐚 **多 Shell 支持** — 自动检测或手动指定 bash / zsh / fish / PowerShell，生成语法正确的命令
- 🔌 **兼容任意 OpenAI 接口** — OpenAI、DeepSeek、豆包、通义千问、本地 Ollama 等均可使用
- 🧠 **深度思考模式** — 支持豆包等推理模型的 thinking 配置
- 📝 **占位符交互填充** — 命令含占位符时，自动引导用户逐项填写后执行
- 📋 **一键复制** — 生成后可直接复制到剪贴板或立即执行
- 📜 **本地历史记录** — 自动保存执行历史，随时回顾
- 🖥️ **跨平台** — macOS / Linux / Windows 均可使用
- ⛔ **安全防护** — 内置 13 种高风险命令检测，执行前醒目警告 + 强制二次确认，支持自定义危险规则

## 安装

### 方式一：uv 安装（推荐）

```bash
# 直接从 Git 仓库安装
uv tool install git+https://github.com/think3t/a-cli.git
```

或将源码下载到本地再安装：

```bash
git clone https://github.com/think3t/a-cli.git
cd a-cli
uv tool install .
```

### 方式二：从源码安装（开发模式）

```bash
git clone https://github.com/think3t/a-cli.git
cd a-cli
pip install -e .
```

## 快速开始

安装后只需一步——设置 API Key：

```bash
export OPENAI_API_KEY=sk-xxx    # 或 A_API_KEY
```

然后直接使用：

```bash
a 列出当前目录下所有 .log 文件并按大小排序
```

首次运行时会自动创建配置文件 `~/.config/a-cli/config.toml`，并检测你的 Shell 类型。

## 配置

### 完整配置文件示例

配置文件路径：`~/.config/a-cli/config.toml`

```toml
[model]
# 服务商名称（仅供参考）
provider      = "openai"
api_base      = "https://api.openai.com/v1"   # 任何 OpenAI 兼容接口
api_key       = ""                             # 建议用环境变量
model_name    = "gpt-4o-mini"
max_suggestions = 3      # 最多返回几个建议
temperature   = 0.2      # 越低越确定性

# 深度思考配置（适用于豆包等支持思考模式的模型）
# thinking_mode    = "auto"       # "enabled"(强制开启) / "disabled"(强制关闭) / "auto"(模型自行判断)
# reasoning_effort = "medium"     # "minimal"(关闭思考) / "low" / "medium" / "high"

[behavior]
auto_execute_single = true   # 只有一个结果时直接进入确认
show_explanation    = true   # 显示命令含义说明
shell_type          = ""     # bash/zsh/fish/pwsh，留空则首次运行时自动检测

[safety]
# 高风险命令安全检查（内置 13 种危险模式）
enable_safety_check = true

# 自定义高风险命令规则（可选）
# [[safety.custom_patterns]]
# pattern    = "drop\\s+database"
# name       = "数据库删除"
# risk_level = 4
# detail     = "将永久删除整个数据库！"
```

### 环境变量

| 环境变量 | 对应配置项 | 说明 |
|---------|-----------|------|
| `A_API_KEY` | `model.api_key` | API 密钥 |
| `A_API_BASE` | `model.api_base` | API 地址 |
| `A_MODEL` | `model.model_name` | 模型名称 |
| `A_PROVIDER` | `model.provider` | 服务商名称 |
| `OPENAI_API_KEY` | `model.api_key` | 兼容标准 OpenAI 环境变量 |

环境变量优先级高于配置文件。

### 使用国内/自建 API

```toml
[model]
api_base   = "https://api.deepseek.com/v1"
api_key    = "your-deepseek-key"
model_name = "deepseek-chat"
```

使用火山方舟（豆包）深度思考：

```toml
[model]
api_base         = "https://ark.cn-beijing.volces.com/api/v3"
api_key          = "your-volcengine-key"
model_name       = "your-endpoint-id"
thinking_mode    = "enabled"
reasoning_effort = "medium"
```

本地 Ollama：

```toml
[model]
api_base   = "http://localhost:11434/v1"
api_key    = "ollama"
model_name = "qwen2.5-coder:7b"
```

## 用法

```bash
# 基本用法 — 生成并执行
a <自然语言描述>

# 只复制到剪贴板，不执行
a --copy <描述>
a -c <描述>

# 控制/隐藏命令说明
a --explain <描述>
a --no-explain <描述>

# 控制返回建议数量
a -n 5 <描述>

# 查看版本
a --version
a -v

# 查看/编辑配置
a config              # 查看配置文件内容和路径
a config --edit       # 用 $EDITOR 打开编辑

# 历史记录
a history             # 查看最近 20 条执行历史
a history -n 50       # 查看最近 50 条
a history --clear     # 清空历史记录
```

## 示例演示

**基本用法** — 输入自然语言，生成命令并执行：

![基本用法](assets/basic-usage.gif)

**多条建议选择** — 生成多个候选命令，交互式选择：

![多条建议选择](assets/multi-select.gif)

**占位符填充** — 命令含占位符时，自动引导逐项填写：

![占位符填充](assets/placeholder.gif)

**高风险命令拦截** — 检测到危险命令时，醒目警告 + 强制二次确认：

![高风险命令拦截](assets/safety-check.gif)

## 技术架构

```
a-cli/
├── a_cli/
│   ├── main.py       # CLI 入口（Click）+ 子命令路由
│   ├── config.py     # 配置管理（TOML + 环境变量）+ Shell 类型检测
│   ├── llm.py        # 大模型调用（OpenAI 兼容）+ 深度思考适配
│   ├── ui.py         # 终端 UI（Rich + InquirerPy）+ 高风险命令警告
│   ├── executor.py   # 命令执行 + 剪贴板 + 历史记录
│   └── safety.py     # 高风险命令检测 + 内置 13 种危险模式 + 自定义规则
├── tests/            # 测试脚本
└── pyproject.toml
```

**技术栈：** Click · Rich · InquirerPy · OpenAI SDK

## 常见问题

**Q: `cd` 命令执行后当前目录没有改变？**

受限于进程隔离，子进程无法改变父 shell 的工作目录。对于需要改变 shell 状态的命令（`cd`、`export`、`alias` 等），工具会自动提示。如需影响当前 shell，可手动运行或使用 `eval $(a ...)` 模式。

**Q: 支持哪些大模型？**

任何兼容 OpenAI Chat Completions API 的服务均可使用，包括：
- OpenAI（GPT-4o、GPT-4o-mini、o1、o3 等）
- DeepSeek（含 DeepSeek-R1 深度思考）
- 火山方舟（豆包，支持 thinking 深度思考）
- 通义千问（Qwen）
- 本地 Ollama
- Azure OpenAI
- 其他兼容接口

**Q: 生成的命令语法不对？**

工具会根据你使用的 Shell 类型（bash/zsh/fish/PowerShell）自动调整命令语法。如果首次运行时检测不准确，可以通过 `a config --edit` 手动修改 `shell_type`。

**Q: 高风险命令安全检查如何工作？**

当生成的命令匹配到内置的 13 种危险模式时（如 `rm -rf /`、`dd 写盘`、`fork 炸弹`、`格式化磁盘`、`DROP DATABASE` 等），程序会：
1. 显示醒目的红色警告面板，标明风险等级和详细后果
2. **强制二次确认**：用户必须先确认，再手动输入 `yes` 才能继续执行

你可以通过 `[safety]` 配置段：
- 设置 `enable_safety_check = false` 关闭检查（不推荐）
- 在 `[[safety.custom_patterns]]` 中添加自定义的危险命令正则规则

**Q: 内置了哪些高风险命令检测？**

内置 13 种高危模式，按风险等级排列：

| 等级 | 命令模式 | 风险说明 |
|------|---------|---------|
| ☠️ 5 | `rm -rf /`、系统目录删除 | 毁灭性操作，系统不可用 |
| ☠️ 5 | `dd of=/dev/...` | 物理磁盘覆写 |
| ☠️ 5 | Fork 炸弹 (`:(){ :|:& };:`) | 耗尽所有进程资源 |
| ☠️ 5 | `mkfs` 格式化 | 清除整个磁盘数据 |
| ☠️ 5 | 重定向写入 `/dev/sd...` | 破坏分区表 |
| 🔴 4 | `rm -rf`（递归强制删除） | 数据不可恢复 |
| 🔴 4 | `shred -z` 安全擦除 | 数据几乎无法恢复 |
| 🔴 4 | `chmod -R 777 /` 全局权限修改 | 破坏安全模型 |
| 🔴 4 | 文件移入 `/dev/null` | 永久销毁文件 |
| 🔴 4 | `DROP DATABASE/TABLE` | 删除数据库结构 |
| ⚠️ 3 | `curl ... \| bash` 远程脚本执行 | 代码注入风险 |
| ⚠️ 3 | 防火墙规则清空/端口开放 | 暴露攻击面 |

## License

[MIT](LICENSE)
