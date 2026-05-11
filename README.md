# SWE-EVO Subset Run

自己手动使用时，只需要记住两种入口：

- 直接复制命令启动
- 改一份本地配置文件后一键后台启动

根目录主要看：

- `run_evaluation.py`: 统一入口
- `configs.json`: 默认参数
- `README.md`

运行脚本和看板代码在：

- `runtime/`
- `runtime/legacy/`
- `webui/`

## 1. 初始化

```bash
cd /path/to/SWE-EVO-subset-run
python3 run_evaluation.py bootstrap
source .venv/bin/activate
```

默认会：

1. 创建 `.venv`
2. 安装 `runtime/requirements.swe-evo.txt`
3. 在 `webui/` 下执行 `npm ci`

## 2. 最短路径：直接复制命令

### 后台启动看板

```bash
source .venv/bin/activate
python3 run_evaluation.py dashboard start --background --session-name subset-run-dashboard
```

打开：

- `http://127.0.0.1:18881`

查看后台会话：

```bash
tmux attach -t subset-run-dashboard
```

### 后台启动评测

跑默认 `project-coverage-7`：

```bash
source .venv/bin/activate
python3 run_evaluation.py run --cli innercc --background --session-name subset-innercc-run
```

跑 `claude`：

```bash
source .venv/bin/activate
python3 run_evaluation.py run --cli claude --background --session-name subset-claude-run
```

常用变体：

```bash
source .venv/bin/activate
python3 run_evaluation.py run \
  --cli innercc \
  --mode direct \
  --manifest config/subsets/project-coverage-7.txt \
  --infer-max-concurrency 3 \
  --eval-max-concurrency 3 \
  --cli-timeout-seconds 5400 \
  --background \
  --session-name subset-innercc-run
```

低成本 smoke：

```bash
source .venv/bin/activate
python3 run_evaluation.py run \
  --cli innercc \
  --limit 1 \
  --max-turns 1 \
  --background \
  --session-name subset-innercc-smoke
```

查看后台会话：

```bash
tmux attach -t subset-innercc-run
```

## 3. 推荐方式：改配置后一键启动

先复制模板：

```bash
cp config/local.launch.env.example config/local.launch.env
```

然后修改这几个最常用配置：

- `RUN_CLI=innercc` 或 `claude`
- `RUN_MODE=direct` 或 `router`
- `RUN_MANIFEST=config/subsets/project-coverage-7.txt`
- `RUN_INFER_MAX_CONCURRENCY=3`
- `RUN_EVAL_MAX_CONCURRENCY=3`
- `RUN_SESSION_NAME=subset-innercc-run`
- `DASHBOARD_SESSION_NAME=subset-run-dashboard`

一键同时启动看板和评测：

```bash
bash runtime/start_local_stack.sh --config config/local.launch.env all
```

只启动看板：

```bash
bash runtime/start_local_stack.sh --config config/local.launch.env dashboard
```

只启动评测：

```bash
bash runtime/start_local_stack.sh --config config/local.launch.env run
```

这个脚本会：

- 优先使用 `.venv/bin/python3`
- 自动打印实际执行的命令
- 用 `tmux` 后台启动你配置好的看板和实验

模板文件：

- `config/local.launch.env.example`

脚本：

- `runtime/start_local_stack.sh`

## 4. 查看配置

```bash
python3 run_evaluation.py show-config
```

主配置文件：

- [configs.json](/home/wt/sss_repos/sss_auto/SWE-EVO-subset-run/configs.json)

这里集中放了：

- 默认子集 manifest
- 默认模型名
- 推理 / 评测并发
- CLI 超时
- agent 的可配置项
- 默认凭证 env 路径

当前已经写入的机器默认值：

- `innercc` 路径：`/home/wt/sss_repos/sss_auto/SWE-EVO-subset-run/dist/innercc_0509_dcp`
- `claude` 路径：`/usr/bin/claude`
- 默认 env：`config/swe-evo.env`
- 默认推理并发：`3`
- 默认评测并发：`3`

说明：

- 当前默认 `innercc` 已固定到仓库内归档快照 `dist/innercc_0509_dcp`
- 如果手动传 `--cli-bin`，入口脚本会先转成绝对路径，再传给 case workspace

## 5. 启动看板

开发模式：

```bash
python3 run_evaluation.py dashboard dev
```

生产模式：

```bash
python3 run_evaluation.py dashboard start
```

后台启动：

```bash
python3 run_evaluation.py dashboard start --background --session-name subset-run-dashboard
```

地址：

- `http://127.0.0.1:18881`

说明：

- 前端工程现在在 `webui/`
- 看板仍然读取仓库根下的 `official48_runs/` 和 `logs/run_evaluation/`

## 6. 跑子集

默认入口：

```bash
python3 run_evaluation.py run --cli innercc
python3 run_evaluation.py run --cli claude
```

常用参数：

```bash
python3 run_evaluation.py run \
  --cli innercc \
  --manifest config/subsets/project-coverage-7.txt \
  --limit 1 \
  --max-turns 1 \
  --infer-max-concurrency 3 \
  --eval-max-concurrency 3 \
  --cli-timeout-seconds 5400
```

当前最常用子集：

- `config/subsets/project-coverage-7.txt`
- `config/subsets/quick-smoke-5.txt`

`run_evaluation.py run` 会调用 `runtime/run_project_coverage_7_pipeline.sh`，自动完成：

1. 生成直连 API 的 Claude settings
2. 物化子集
3. 运行推理
4. 启动增量评测
5. 生成汇总

### 模式切换

支持两种模式：

1. `direct`
   - 默认模式
   - 直连 API
   - 调用 `runtime/run_project_coverage_7_pipeline.sh`
2. `router`
   - 走 `llm_router`
   - 调用 `runtime/run_project_coverage_7_pipeline_router.sh`
   - 默认读取 `config/claude.settings.json`

示例：

```bash
python3 run_evaluation.py run --cli innercc --mode direct
python3 run_evaluation.py run --cli innercc --mode router
```

只看最终会执行什么：

```bash
python3 run_evaluation.py run --cli innercc --mode direct --dry-run
python3 run_evaluation.py run --cli innercc --mode router --dry-run
```

## 7. 跑单题

当前单题 runner 仍保留在：

- `custom_cli_case/`

直接运行：

```bash
bash ./custom_cli_case/run_requests_case.sh
```

## 8. 结果位置

每次子集 run 输出到：

```bash
official48_runs/<run_id>/
```

重点文件：

- `infer/inference_status.json`
- `infer/inference_summary.json`
- `analysis/summary.json`
- `analysis/report.md`
- `eval_worker_status.json`
- `eval_worker_logs/*.log`

评测原始报告：

```bash
logs/run_evaluation/eval_input_<run_id>/
```

## 9. 常用维护命令

刷新 summary：

```bash
python3 run_evaluation.py summarize \
  --run-root official48_runs/<run_id> \
  --instances-dir official48_runs/<run_id>/input/output_final
```

手动物化子集：

```bash
python3 runtime/materialize_subset_instances.py \
  --manifest config/subsets/project-coverage-7.txt \
  --source-dir official48_source/output_final \
  --dest-dir /tmp/project-coverage-7
```

手动生成直连 settings：

```bash
python3 runtime/build_claude_direct_settings.py \
  --env-file config/swe-evo.env \
  --output /tmp/claude.direct.settings.json \
  --overwrite
```

自动补跑：

```bash
python3 runtime/watch_subset_run_until_complete.py \
  --run-root official48_runs/<run_id>
```

净化 patch 中的 test/docs 改动：

```bash
python3 runtime/sanitize_model_patch.py \
  --runs-root official48_runs/<run_id>/infer/runs
```

## 10. 目录约定

- `runtime/`: 当前仍在使用的运行脚本
- `runtime/legacy/`: 保留但非主线入口的旧脚本
- `webui/`: Next.js 看板

## 11. 当前建议

如果只是测通链路：

```bash
python3 run_evaluation.py run --cli innercc --limit 1 --max-turns 1
python3 run_evaluation.py run --cli claude --limit 1 --max-turns 1
```

如果要正式比较：

```bash
python3 run_evaluation.py run --cli innercc
python3 run_evaluation.py run --cli claude
```

后台启动实验：

```bash
python3 run_evaluation.py run --cli innercc --background --session-name innercc-run
python3 run_evaluation.py run --cli innercc --mode router --background --session-name innercc-router-run
```

看板里优先看本轮 `-clean` run，不要混用旧的 `-stale` run。
