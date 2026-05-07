# SWE-EVO 自有 CLI 复用手册

本文只保留当前仓库真正还在使用的流程：

- 如何把自己的 CLI 对接到 SWE-EVO
- 如何跑单题验证
- 如何跑 official48 全量推理
- 如何做增量评测与监控
- 如何启动 llm_router 和结果看板
- 如何用 `tmux` 在后台长期运行

与论文、原始 benchmark 背景、OpenHands / SWE-agent 通用说明无关的内容都已移除。

## 0. 换环境先看这里

当前仓库已经支持“仓库相对路径 + 环境变量覆盖”的运行方式，不再要求你把仓库放在 `/home/wt/...`。

推荐最短启动流程：

```bash
cd /path/to/SWE-EVO
bash ./bootstrap_env.sh
cp config/claude.settings.example.json config/claude.settings.json
cp config/swe-evo.example.env config/swe-evo.env
source .venv/bin/activate
```

然后按需修改：

- `config/claude.settings.json`
- `config/swe-evo.env`
- `INNERCC_CLI_BIN`
- `LLM_ROUTER_ROOT`

完整说明见：

- [docs/environment.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/environment.md)

## 1. 当前链路总览

当前链路分成 5 层：

1. `custom_cli_case/run_custom_cli_case.py`
   用来验证“你的 CLI 能不能在单题上跑通”。
2. `run_innercc_infer_official48.py`
   official48 批量推理主循环；逐题准备 workspace，调用 CLI，导出 patch、preds、router trace。
3. `run_official48_eval_worker.py`
   增量评测 worker；一旦某题推理完成，就对该题单独跑 `SWE-bench/evaluate_instance.py`。
4. `monitor_official48_run.py` + `record_official48_progress.py`
   分别负责状态汇总和进度快照。
5. `watch_official48_supervisor.py`
   自救 supervisor；负责保活 llm_router、推理、评测、监控和进度记录。

另外新增了“整轮复现实验”后台编排链路：

6. `run_official48_experiment_suite.py`
   顺序执行 `smoke-innercc -> smoke-claude-code -> full-innercc -> full-claude-code`，并把 suite 状态持续写到 `official48_suite_runs/<suite_id>/suite_state.json`。
7. `start_official48_experiment_suite.sh`
   用 `tmux` 启动上述 suite，确保 SSH 断开或 Codex 会话结束后任务仍继续。
8. `show_official48_experiment_suite_status.py`
   直接读取 `official48_suite_runs/latest/suite_state.json` 和对应 `run_root/monitor_status.json`，快速查看当前 suite 进度。

前端看板已经改为 Next.js：

- llm_router 看板：`http://127.0.0.1:18781`
- official48 结果看板：`http://127.0.0.1:18881`

对应启动命令：

```bash
# 1) 启动 llm_router 看板（18781/18782/18783）
export LLM_ROUTER_ROOT="${LLM_ROUTER_ROOT:-$(cd .. && pwd)/llm_router}"
SESSION_PREFIX=sss-auto-llm-router \
ANTHROPIC_UPSTREAM_URL=https://api.minimaxi.com/anthropic \
OPENAI_UPSTREAM_URL=https://api.minimaxi.com/v1 \
bash "$LLM_ROUTER_ROOT/scripts/start-prod.sh"

# 2) 启动 official48 Next.js 看板（18881）
cd /path/to/SWE-EVO
npm ci
npm run build
npm run dashboard:start
```

如果只是本地联调 official48 看板，也可以直接用开发模式：

```bash
cd /path/to/SWE-EVO
npm run dashboard:dev
```

## 1.1 后台整轮实验

启动一轮“先 smoke 再 full”的后台实验：

```bash
cd /path/to/SWE-EVO
./start_official48_experiment_suite.sh
```

它会在后台 `tmux` 里按顺序运行：

1. `smoke-innercc`
2. `smoke-claude-code`
3. `full-innercc-round01`
4. `full-claude-code-round01`

默认 smoke 子集是两个已知稳定样例：

- `psf__requests_v2.27.0_v2.27.1`
- `iterative__dvc_1.11.12_1.11.13`

查看 suite 进度：

```bash
cd /path/to/SWE-EVO
python3 ./show_official48_experiment_suite_status.py
```

查看后台 tmux：

```bash
tmux ls
tmux attach -t swe-evo-official48-suite-<suite_id>
```

当前 suite 过程会用到的持久化文件：

- `official48_suite_runs/<suite_id>/suite_state.json`
- `official48_suite_runs/<suite_id>/logs/suite.log`
- `official48_suite_runs/<suite_id>/logs/<step>.log`

llm router 仍由独立 tmux sessions 保活：

- `sss-auto-llm-router-proxy`
- `sss-auto-llm-router-web`

## 2. 固定路径与可变项

当前脚本现在会优先读取环境变量和仓库内 `config/`，只有没找到时才回退到历史机器上的默认路径。

历史机器上的默认路径如下：

```bash
REPO_ROOT=/home/wt/sss_repos/sss_auto/SWE-EVO
CLI_BIN=/home/wt/repo/innerCC/cli
SETTINGS_FILE=/home/wt/.claude/settings.json
ENV_FILE=/home/wt/.config/swe-evo/minimax.env
ROUTER_ROOT=/home/wt/sss_repos/sss_auto/llm_router
```

后续复用时，最常改的是这些项：

| 项目 | 当前默认值 | 改哪里 |
| --- | --- | --- |
| 仓库根目录 | `/home/wt/sss_repos/sss_auto/SWE-EVO` | `run_official48_pipeline.sh`、`watch_official48_supervisor.py`、启动命令 |
| CLI 二进制 | `/home/wt/repo/innerCC/cli` | `--cli-bin`，或 `custom_cli_case/run_custom_cli_case.py` 默认值 |
| settings 文件 | `/home/wt/.claude/settings.json` | `--settings-file`，或 `custom_cli_case/run_custom_cli_case.py` 默认值 |
| 凭证 env 文件 | `/home/wt/.config/swe-evo/minimax.env` | `--env-file`，或 `custom_cli_case/run_custom_cli_case.py` 默认值 |
| 模型名 | `MiniMax-M2.5-highspeed` | `--model`，或 `INNERCC_MODEL` |
| official48 输入目录 | `official48_source/output_final` | `run_official48_pipeline.sh` 中复制逻辑，或 `--instances-dir` |
| llm_router DB | `.../llm_router/proxy/data/traces.db` | `run_innercc_infer_official48.py` 的 `--router-db-path` |
| llm_router API | `http://127.0.0.1:18783` | `run_innercc_infer_official48.py` 的 `--router-api-base` |
| CLI 超时 | `5400` 秒 | `--cli-timeout-seconds` |
| 增量评测并发 | `3` | `run_official48_eval_worker.py <run_root> <max_concurrency>` |

重要：

- `run_innercc_infer_official48.py` 批量推理使用 SSH clone：`git@github.com:<repo>.git`
  所以 full official48 需要本机已经配置 GitHub SSH key。
- `custom_cli_case/run_custom_cli_case.py` 单题 runner 使用 HTTPS clone，
  单题联调不依赖 GitHub SSH。

说明：

- 下文仍保留了一些历史绝对路径示例，便于回看老命令。
- 新环境优先使用本节和 [docs/environment.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/environment.md) 里的仓库相对方式。

## 3. CLI 接入契约

当前接入契约由 [custom_cli_case/run_custom_cli_case.py](/home/wt/sss_repos/sss_auto/SWE-EVO/custom_cli_case/run_custom_cli_case.py) 定义，full official48 也复用它：

- `run_innercc_infer_official48.py` 通过 `load_runner()` 动态导入这个文件
- 然后调用里面的 `run_cli()` 和 `write_patch_outputs()`

这意味着：

- 如果你的 CLI 和 innerCC 命令行兼容，只需要改路径、settings、env、model
- 如果你的 CLI 参数格式、stdin / stdout 协议不同，只需要改 `custom_cli_case/run_custom_cli_case.py`
- 单题联调跑通后，批量 official48 会自动复用相同的接入逻辑

当前 runner 假定 CLI 满足这些条件：

1. 非交互式，从 stdin 读完整 prompt
2. 支持这些 flag

```bash
--bare
-p
--output-format json
--dangerously-skip-permissions
--settings <settings_file>
--model <model_name>
```

3. stdout 最后一条 JSON 行是可解析结果
4. 实际 patch 不从 JSON 里取，而是直接对 workspace 跑 `git diff`

当前已经验证过两种模式：

- innerCC 风格：

```bash
<cli> --bare -p --output-format json --dangerously-skip-permissions ...
```

- Claude Code 风格：

```bash
claude -p --output-format json --dangerously-skip-permissions --settings <settings.json> "Prompt"
```

如果 `--cli-bin /usr/bin/claude`，runner 会自动切换到 Claude Code 的命令行协议，不再从 stdin 喂 prompt，而是把 prompt 作为最后一个位置参数传入。

如果你的 CLI 不符合上述约定，优先改这里：

- `build_prompt()`
- `run_cli()`
- `extract_last_json_line()`
- `write_patch_outputs()`

## 4. 配置文件

### 4.1 Claude settings

位置：

```bash
/home/wt/.claude/settings.json
```

当前脚本实际会读取：

- 顶层键：`$schema`、`autoUpdatesChannel`、`env`、`skipDangerousModePermissionPrompt`
- `env` 内部键：`ANTHROPIC_AUTH_TOKEN`、`ANTHROPIC_BASE_URL`、`ANTHROPIC_MODEL`

最小可复用示例：

```json
{
  "skipDangerousModePermissionPrompt": true,
  "env": {
    "ANTHROPIC_BASE_URL": "http://127.0.0.1:18782",
    "ANTHROPIC_MODEL": "MiniMax-M2.5-highspeed",
    "ANTHROPIC_AUTH_TOKEN": "placeholder-or-real-token"
  }
}
```

这里最关键的是：

- `ANTHROPIC_BASE_URL` 必须指向 llm_router 代理端口 `18782`

### 4.2 凭证 env 文件

位置：

```bash
/home/wt/.config/swe-evo/minimax.env
```

当前文件里出现的键名有：

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`
- `SWE_AGENT_MODEL`
- `ANTHROPIC_BASE_URL`

建议模板：

```bash
OPENAI_API_KEY=your_provider_key
OPENAI_BASE_URL=https://api.minimaxi.com/v1
SWE_AGENT_MODEL=MiniMax-M2.5-highspeed
ANTHROPIC_BASE_URL=http://127.0.0.1:18782
```

当前 runner 有一个兼容逻辑：

- 如果 `OPENAI_API_KEY` 存在，但 `ANTHROPIC_API_KEY` 不存在
- 会自动把 `ANTHROPIC_API_KEY` 设成 `OPENAI_API_KEY`

### 4.3 Python 依赖目录

当前评测相关脚本默认依赖：

```bash
PYTHONPATH="$REPO_ROOT/.deps"
```

也就是说：

- 当前仓库假定 `.deps/` 已经存在并可用
- 如果你改成自己的虚拟环境，需要同步改这些命令中的 `PYTHONPATH`

涉及脚本：

- `run_official48_pipeline.sh`
- `run_official48_eval_worker.py`
- `watch_official48_supervisor.py`

## 5. 先做单题联调

建议先用单题 runner 验证 CLI 契约，再跑 full official48。

### 5.1 一键示例

```bash
cd /home/wt/sss_repos/sss_auto/SWE-EVO
bash custom_cli_case/run_requests_case.sh
```

它会跑固定 case：

- `psf__requests_v2.27.0_v2.27.1`

### 5.2 通用单题命令

```bash
cd /home/wt/sss_repos/sss_auto/SWE-EVO
python3 custom_cli_case/run_custom_cli_case.py \
  --instance-id psf__requests_v2.27.0_v2.27.1 \
  --case-root "$REPO_ROOT/custom_cli_case" \
  --cli-bin "$CLI_BIN" \
  --settings-file "$SETTINGS_FILE" \
  --env-file "$ENV_FILE" \
  --model MiniMax-M2.5-highspeed \
  --agent-name innercc-cli \
  --eval-run-id psf__requests_v2.27.0_v2.27.1-innercc-$(date +%Y%m%d-%H%M%S) \
  --force-workspace \
  --max-workers 1
```

可变参数：

- `--instance-id`：要验证的 case
- `--cli-bin`
- `--settings-file`
- `--env-file`
- `--model`
- `--agent-name`
- `--eval-run-id`
- `--max-turns`
- `--max-workers`
- `--force-workspace`

### 5.3 单题输出

单题输出目录：

```bash
custom_cli_case/run/<instance_id>/
```

重要文件：

- `cli_result.json`
- `cli_stdout.log`
- `cli_stderr.log`
- `cli_exit_code.txt`
- `patch.diff`
- `preds.json`
- `summary.json`

单题评测输出目录：

```bash
logs/run_evaluation/<eval_run_id>/<agent_name>/<instance_id>/
```

重要文件：

- `report.json`
- `test_output.txt`
- `run_instance.log`

## 6. llm_router

### 6.1 端口

- Web：`http://127.0.0.1:18781`
- Proxy：`http://127.0.0.1:18782`
- API：`http://127.0.0.1:18783`

### 6.2 查看状态

```bash
bash /home/wt/sss_repos/sss_auto/llm_router/scripts/status.sh
```

### 6.3 启动 / 重启

```bash
SESSION_PREFIX=sss-auto-llm-router \
ANTHROPIC_UPSTREAM_URL=https://api.minimaxi.com/anthropic \
OPENAI_UPSTREAM_URL=https://api.minimaxi.com/v1 \
bash /home/wt/sss_repos/sss_auto/llm_router/scripts/start-prod.sh
```

如果你换上游供应商，重点改的是：

- `ANTHROPIC_UPSTREAM_URL`
- `OPENAI_UPSTREAM_URL`

### 6.4 清空历史 trace

```bash
curl -X DELETE http://127.0.0.1:18783/api/data/all
```

## 7. official48 推理与评测流程

### 7.1 一次性入口

[run_official48_pipeline.sh](/home/wt/sss_repos/sss_auto/SWE-EVO/run_official48_pipeline.sh) 做这几件事：

1. 生成 `run_id=YYYYMMDD-HHMMSS`
2. 创建 `official48_runs/<run_id>/`
3. 清空 llm_router traces
4. 把 `official48_source/output_final` 和 `official48_source/hf_out` 复制到仓库根目录
5. 后台启动 `run_official48_eval_worker.py`
6. 调 `run_innercc_infer_official48.py` 并发跑 48 题推理
7. 每题一完成就把结果追加到 `inference_summary.json`，增量评测 worker 立即接手
8. 等待增量评测追平
9. 备份 llm_router `proxy/data`

前台直接执行：

```bash
cd /home/wt/sss_repos/sss_auto/SWE-EVO
bash run_official48_pipeline.sh
```

这个入口简单，但不适合长任务值守。实际长期运行建议看第 8 节的后台模式。

### 7.2 批量推理主脚本

核心脚本：

```bash
python3 run_innercc_infer_official48.py \
  --output-dir <run_root>/infer \
  --instances-dir <instances_dir> \
  --cli-bin <cli_bin> \
  --settings-file <settings_file> \
  --env-file <env_file> \
  --model <model_name> \
  --agent-name innercc-cli \
  --force-workspace \
  --resume \
  --max-concurrency 2 \
  --cli-timeout-seconds 5400 \
  --router-ready-timeout-seconds 120 \
  --router-db-path <router_db_path> \
  --router-api-base http://127.0.0.1:18783
```

当前脚本实际行为：

1. 遍历 `output_final/*.json`
2. 用 `--max-concurrency` 控制推理并发，默认 `2`
3. 为每题准备独立 git workspace
4. 每个任务在真正调用 CLI 之前都会等待 llm_router 就绪
5. 通过 `custom_cli_case/run_custom_cli_case.py` 里的 `run_cli()` 调你的 CLI
6. 每题完成后立刻记录：
   - `cli_result.json`
   - `cli_stdout.log`
   - `cli_stderr.log`
   - `patch.diff`
   - `preds.json`
   - 根目录 `preds.json`
   - 根目录 `inference_summary.json`
   - 根目录 `inference_status.json`
7. 从 llm_router 导出 `router_trace_bundle.json`
8. 给 router session / run 写备注：
   - `innercc | <instance_id> | <YYYY-MM-DD HH:MM:SS>`

注意：

- 只要某题写入 `inference_summary.json`，增量评测 worker 就会立刻开始该题评测
- 整体流程已经不是“48 题全部推理结束后再统一评测”

关键新增配置：

- `--max-concurrency`：推理并发数，默认 `2`
- `--cli-timeout-seconds`：单题 CLI 超时，默认 `5400`
- `--router-ready-timeout-seconds`：每题启动前等待 router 的最大秒数，默认 `120`

### 7.3 增量评测 worker

命令：

```bash
python3 -u run_official48_eval_worker.py <run_root> 3 --retry-missing-report --poll-interval-seconds 15
```

参数：

- 第 1 个位置参数：`run_root`
- 第 2 个位置参数：最大并发数，当前默认 `3`
- `--retry-missing-report`：重试已有状态但缺 report 的 case
- `--poll-interval-seconds`：轮询增量结果的间隔秒数，默认 `15`

它会：

1. 创建软链：
   - `<run_root>/eval_input_<run_id> -> <run_root>/infer`
2. 轮询 `infer/inference_summary.json` 和 `infer/inference_status.json`
3. 对每个已完成推理的 case 立即执行：

```bash
python3 SWE-bench/evaluate_instance.py \
  --trajectories_path <run_root>/eval_input_<run_id> \
  --instance <instance_id> \
  --max_workers 1 \
  --scaffold CustomCLI
```

4. 把状态写入：
   - `eval_worker_status.json`
   - `eval_worker.log`
   - `eval_worker_logs/<instance_id>.log`

### 7.4 监控与进度

监控：

```bash
python3 -u monitor_official48_run.py <run_root>
```

输出：

- `monitor_status.json`
- `monitor.log`

进度快照：

```bash
python3 -u record_official48_progress.py <run_root> <progress_md> --interval-seconds 1800
```

输出：

- `progress.md`
- `<run_root>/progress_state.json`

### 7.5 结果目录

每次 run 的根目录：

```bash
official48_runs/<run_id>/
```

重要文件：

- `official48_runs/current_router.log`
- `official48_runs/<run_id>/infer/preds.json`
- `official48_runs/<run_id>/infer/inference_summary.json`
- `official48_runs/<run_id>/infer/inference_status.json`
- `official48_runs/<run_id>/infer/runs/<instance_id>/cli_result.json`
- `official48_runs/<run_id>/infer/runs/<instance_id>/cli_stdout.log`
- `official48_runs/<run_id>/infer/runs/<instance_id>/cli_stderr.log`
- `official48_runs/<run_id>/infer/runs/<instance_id>/patch.diff`
- `official48_runs/<run_id>/infer/runs/<instance_id>/preds.json`
- `official48_runs/<run_id>/infer/runs/<instance_id>/router_trace_bundle.json`
- `official48_runs/<run_id>/eval_worker_status.json`
- `official48_runs/<run_id>/eval_worker.log`
- `official48_runs/<run_id>/eval_worker_logs/<instance_id>.log`
- `official48_runs/<run_id>/monitor_status.json`
- `official48_runs/<run_id>/monitor.log`
- `official48_runs/<run_id>/supervisor.log`
- `logs/run_evaluation/eval_input_<run_id>/.../report.json`

## 8. 推荐后台运行方式

### 8.1 先启动 llm_router

```bash
SESSION_PREFIX=sss-auto-llm-router \
ANTHROPIC_UPSTREAM_URL=https://api.minimaxi.com/anthropic \
OPENAI_UPSTREAM_URL=https://api.minimaxi.com/v1 \
bash /home/wt/sss_repos/sss_auto/llm_router/scripts/start-prod.sh
```

### 8.2 启动结果看板

首次或代码变更后先构建：

```bash
cd /home/wt/sss_repos/sss_auto/SWE-EVO
npm install
npm run build
```

前台启动：

```bash
cd /home/wt/sss_repos/sss_auto/SWE-EVO
npm run dashboard:start
```

后台启动：

```bash
tmux new-session -d -s swe-evo-dashboard \
  "bash -lc 'cd /home/wt/sss_repos/sss_auto/SWE-EVO && npm run dashboard:start'"
```

### 8.3 启动 official48 主任务

后台 router session：

```bash
cd /home/wt/sss_repos/sss_auto/SWE-EVO
tmux new-session -d -s swe-evo-official48-router \
  "bash -lc './run_official48_pipeline.sh 2>&1 | tee -a /home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/current_router.log'"
```

如需修改本轮并发与超时，可直接覆写环境变量：

```bash
INFER_MAX_CONCURRENCY=2 \
EVAL_MAX_CONCURRENCY=3 \
CLI_TIMEOUT_SECONDS=5400 \
ROUTER_READY_TIMEOUT_SECONDS=120 \
MODEL_NAME=MiniMax-M2.5-highspeed \
bash run_official48_pipeline.sh
```

### 8.4 启动 supervisor

假设当前 run 根目录是：

```bash
/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/<run_id>
```

启动命令：

```bash
cd /home/wt/sss_repos/sss_auto/SWE-EVO
tmux new-session -d -s swe-evo-official48-supervisor \
  "bash -lc 'python3 -u /home/wt/sss_repos/sss_auto/SWE-EVO/watch_official48_supervisor.py /home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/<run_id>'"
```

如需显式指定并发：

```bash
python3 watch_official48_supervisor.py /home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/<run_id> \
  --inference-concurrency 2 \
  --eval-max-concurrency 3 \
  --cli-timeout-seconds 5400 \
  --router-ready-timeout-seconds 120
```

supervisor 会自动保活这些 session：

- `swe-evo-official48-router`
- `swe-evo-official48-eval`
- `swe-evo-official48-monitor`
- `swe-evo-official48-progress`
- `swe-evo-official48-supervisor`

同时还会检查并必要时重启：

- `sss-auto-llm-router-proxy`
- `sss-auto-llm-router-web`

### 8.5 手动单独启动评测 / 监控 / 进度

如果你不想用 supervisor，也可以手动起：

```bash
tmux new-session -d -s swe-evo-official48-eval \
  "bash -lc 'cd /home/wt/sss_repos/sss_auto/SWE-EVO && python3 -u run_official48_eval_worker.py /home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/<run_id> 3 --retry-missing-report 2>&1 | tee -a /home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/<run_id>/eval_worker.log'"

tmux new-session -d -s swe-evo-official48-monitor \
  "bash -lc 'cd /home/wt/sss_repos/sss_auto/SWE-EVO && python3 -u monitor_official48_run.py /home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/<run_id> 2>&1 | tee -a /home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/<run_id>/monitor.log'"

tmux new-session -d -s swe-evo-official48-progress \
  "bash -lc 'cd /home/wt/sss_repos/sss_auto/SWE-EVO && python3 -u record_official48_progress.py /home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/<run_id> /home/wt/sss_repos/sss_auto/SWE-EVO/progress.md --interval-seconds 1800'"
```

## 9. 状态查看与停止

### 9.1 状态查看

llm_router：

```bash
bash /home/wt/sss_repos/sss_auto/llm_router/scripts/status.sh
```

查看全部 tmux：

```bash
tmux list-sessions
```

看主日志：

```bash
tail -f /home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/current_router.log
```

看 monitor 状态：

```bash
cat /home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/<run_id>/monitor_status.json
tail -f /home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/<run_id>/monitor.log
```

看增量评测状态：

```bash
cat /home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/<run_id>/eval_worker_status.json
tail -f /home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/<run_id>/eval_worker.log
```

看 llm_router sessions：

```bash
curl http://127.0.0.1:18783/api/sessions
```

### 9.2 停止后台任务

```bash
tmux kill-session -t swe-evo-dashboard || true
tmux kill-session -t swe-evo-official48-router || true
tmux kill-session -t swe-evo-official48-eval || true
tmux kill-session -t swe-evo-official48-monitor || true
tmux kill-session -t swe-evo-official48-progress || true
tmux kill-session -t swe-evo-official48-supervisor || true
tmux kill-session -t sss-auto-llm-router-proxy || true
tmux kill-session -t sss-auto-llm-router-web || true
pkill -f 'run_official48_pipeline.sh|run_innercc_infer_official48.py|/home/wt/repo/innerCC/cli' || true
```

## 10. 结果看板

结果看板地址：

```bash
http://127.0.0.1:18881
http://127.0.0.1:18881/dashboard
```

当前看板支持：

- run 列表
- run comparison
- case 级别排序、筛选
- 运行中的 resolved / F2P / P2P 实时汇总
- 点击 case 查看完整 router trace
- 编辑 run 的 `display_name`
- 删除 idle / 非运行 run（带确认）

`display_name` 会持久化到：

```bash
official48_runs/<run_id>/metadata.json
```

内部仍然继续用 `run_id` 做目录、artifact、评测和 API 主键。

删除 run 的规则：

- 只能删除非运行中的 run
- 删除前会弹确认框
- 删除时会同时清理：
  - `official48_runs/<run_id>`
  - `logs/run_evaluation/eval_input_<run_id>`

## 11. 迁移到另一台机器时，最少检查这些地方

1. 绝对路径是否都改了：
   - `run_official48_pipeline.sh`
   - `run_innercc_infer_official48.py`
   - `run_official48_eval_worker.py`
   - `watch_official48_supervisor.py`
2. `settings.json` 里的 `ANTHROPIC_BASE_URL` 是否仍指向本机 `18782`
3. `minimax.env` 是否换成你的 provider key / base url
4. GitHub SSH 是否已配好
5. `.deps/` 是否可用，或者 `PYTHONPATH` 是否已改成你的环境
6. 你的 CLI 是否仍满足第 3 节的接入契约
7. Next 看板代码改完后是否重新执行：

```bash
npm run build
tmux kill-session -t swe-evo-dashboard || true
tmux new-session -d -s swe-evo-dashboard \
  "bash -lc 'cd /home/wt/sss_repos/sss_auto/SWE-EVO && npm run dashboard:start'"
```

## 12. 最小复用建议

如果你只是想把“自己的 CLI + SWE-EVO / SWE-bench 评测”搬到另一台机器，按这个顺序做就够了：

1. 先改好：
   - `CLI_BIN`
   - `SETTINGS_FILE`
   - `ENV_FILE`
   - llm_router 上游地址
2. 跑一题：
   - `python3 custom_cli_case/run_custom_cli_case.py ...`
3. 确认单题输出里有：
   - `patch.diff`
   - `preds.json`
   - `report.json`
4. 再跑 official48：
   - `tmux new-session -d -s swe-evo-official48-router ...`
   - `tmux new-session -d -s swe-evo-official48-supervisor ...`
5. 打开：
   - `http://127.0.0.1:18781`
   - `http://127.0.0.1:18881`

这样基本就能完整复用当前仓库的推理、路由、评测和可视化链路。
