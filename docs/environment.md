# 跨环境启动

这套仓库现在支持两种配置来源：

1. 环境变量覆盖
2. 仓库内 `config/` 本地文件

推荐顺序：

```bash
cd /path/to/SWE-EVO
bash ./bootstrap_env.sh
cp config/claude.settings.example.json config/claude.settings.json
cp config/swe-evo.example.env config/swe-evo.env
source .venv/bin/activate
```

## 关键环境变量

- `INNERCC_CLI_BIN`: 你的 CLI 可执行文件路径，或 PATH 上的命令名
- `INNERCC_SETTINGS_PATH`: Claude-style settings 文件路径
- `INNERCC_ENV_FILE`: 凭证 env 文件路径
- `INNERCC_MODEL`: 默认模型名
- `SWE_EVO_DEPS_PATH`: 额外 Python 依赖目录；不设也可以，脚本会优先使用当前 venv
- `OFFICIAL48_SOURCE_ROOT`: official48 输入数据目录，默认是仓库内的 `official48_source/`
- `LLM_ROUTER_ROOT`: llm_router 仓库路径
- `SWE_EVO_ROUTER_API_BASE`: llm_router API 地址，默认 `http://127.0.0.1:18783`
- `SWE_EVO_ROUTER_DB_PATH`: llm_router trace DB 路径

## 脚本默认查找顺序

- CLI: `INNERCC_CLI_BIN` -> 仓库同级 `../innerCC/cli` -> `$HOME/repo/innerCC/cli` -> PATH 里的 `innercc` / `claude`
- settings: `INNERCC_SETTINGS_PATH` -> `config/claude.settings.json` -> `~/.claude/settings.json`
- env: `INNERCC_ENV_FILE` -> `config/swe-evo.env` -> `~/.config/swe-evo/minimax.env`

## 必需输入数据

这些目录需要跟仓库一起同步：

- `official48_source/output_final/`
- `official48_source/hf_out/`
- `custom_cli_case/output_final/`
- `custom_cli_case/hf_dataset/`

这些目录是运行产物，不应该再提交：

- `official48_runs/`
- `logs/run_evaluation/`
- `output_final/`
- `hf_out/`
- `custom_cli_case/workspace/`
- `custom_cli_case/run/`
