# 2026-04-29

## 本版目标

本版围绕两件事收敛：

1. 把 SWE-EVO 改造成“可复用的自有 CLI 推理 + SWE-bench 评测”工作流。
2. 把原先不稳定的结果看板替换为可直接服务端渲染的 Next.js 版本，并补上 run 别名能力。

## 本版改动明细

### 0. 提交后续增量修正

在 `ff5a604` 之后，又继续补了这一批关键修正：

- 推理链路改成可配置并发，默认 `2`
- 评测链路改成“单题推理完成后立即增量评测”
- runner 增加对 `claude -p --dangerously-skip-permissions "Prompt"` 的兼容
- 运行中的 run 也能实时展示 resolved / F2P / P2P
- 看板新增 idle run 删除功能，并带确认和后端保护

### 1. 自有 CLI 接入与单题联调

新增 `custom_cli_case/` 单题链路，用于先验证 CLI 契约，再放大到 official48：

- 新增 `custom_cli_case/run_custom_cli_case.py`
  - 负责读取单题实例 JSON
  - 准备 workspace 并 checkout 到 `base_commit`
  - 通过 stdin 把 prompt 喂给 CLI
  - 从 `git diff` 生成 `patch.diff` 和 `preds.json`
  - 直接调用本地 SWE-bench harness 跑评测
- 新增 `custom_cli_case/run_requests_case.sh`
  - 提供一个固定单题的一键联调入口
- 新增 `custom_cli_case/README.md`
  - 记录单题链路的基本使用方式

当前 CLI runner 的默认约定：

- CLI 参数风格兼容 innerCC
- 非交互、stdin 输入 prompt、stdout 输出 JSON
- patch 来源不是 JSON 字段，而是 workspace 上的 `git diff`

### 2. official48 全量推理链路

新增 official48 批量推理主脚本：

- 新增 `run_innercc_infer_official48.py`
  - 批量遍历 `output_final/*.json`
  - 准备每题 workspace
  - 复用 `custom_cli_case/run_custom_cli_case.py` 的 `run_cli()` 和 `write_patch_outputs()`
  - 写出：
    - `cli_result.json`
    - `cli_stdout.log`
    - `cli_stderr.log`
    - `patch.diff`
    - `preds.json`
    - `router_trace_bundle.json`
  - 从 llm_router 的 SQLite + API 导出完整 trace bundle
  - 自动给 router session / run 打备注，便于在 router 看板追踪

新增 official48 顶层入口：

- 新增 `run_official48_pipeline.sh`
  - 生成 `run_id`
  - 切换 official48 输入数据
  - 清空 llm_router traces
  - 跑 full inference
  - 跑全量评测
  - 备份 router 数据快照

### 3. official48 增量评测与后台保活

新增评测 / 监控 / 自救链路：

- 新增 `run_official48_eval_worker.py`
  - 轮询 `infer/inference_summary.json`
  - 对已完成推理的 case 逐题调用 `SWE-bench/evaluate_instance.py`
  - 支持 `--retry-missing-report`
  - 输出 `eval_worker_status.json` 和 per-case eval log
- 新增 `monitor_official48_run.py`
  - 汇总推理完成数、trace bundle 数、评测报告数
  - 写入 `monitor_status.json`
- 新增 `record_official48_progress.py`
  - 按周期向 `progress.md` 追加快照
  - 记录 active case / last eval case / delta
- 新增 `watch_official48_supervisor.py`
  - 用 `tmux` 保活 full pipeline 所需 session
  - 检查 llm_router proxy / web / API 健康
  - 必要时拉起：
    - inference session
    - eval worker
    - monitor
    - progress recorder

### 4. SWE-bench 评测入口扩展

修改 `SWE-bench/evaluate_instance.py`：

- 新增 `--scaffold CustomCLI`
- `CustomCLI` 直接读取 `preds.json`
- 从 `preds.json[instance_id]["model_patch"]` 取 patch

这个改动使得本仓库不再依赖 OpenHands / SWE-agent 产物格式，能够直接消费自有 CLI 结果。

### 5. 结果汇总与分析产物

新增 `summarize_official48_run.py`：

- 汇总 CLI、trace、评测三类数据
- 产出 per-case 表和 summary
- 生成 `analysis/summary.json`
- 支持把 tool usage、token usage、resolved/F2P/P2P、异常标记统一汇总

这份 summary 现在是结果看板和后续分析的主要数据源。

### 6. 结果看板重写为 Next.js

本版把原先“Python 静态页 + 前端脚本拉数据”的看板重写为 Next.js SSR：

- 新增 `package.json`
- 新增 `package-lock.json`
- 新增 `next.config.mjs`
- 新增 `jsconfig.json`
- 新增 `app/`
- 新增 `components/`
- 新增 `lib/dashboard-data.js`

新的看板结构：

- `app/page.js`
- `app/dashboard/page.js`
- `components/dashboard-page.jsx`
- `components/dashboard-client.jsx`
- `app/globals.css`

新的数据 API：

- `GET /api/health`
- `GET /api/runs`
- `GET /api/run/[runId]`
- `GET /api/run/[runId]/case/[instanceId]/trace`
- `GET /artifact?path=...`

关键收益：

- 首屏直接 SSR run / summary / case 数据，不再依赖客户端先点 Refresh 才能看到内容
- root 和 `/dashboard` 两个入口统一
- case 详情支持 trace 时间线
- artifact 下载、run comparison、排序筛选统一迁入 Next

### 7. Trace 人类可读化

无论是旧 Python 看板中间版本，还是最终 Next 版，trace 解析逻辑都完成了重构：

- 过滤 `system` prompt 和 tools definition
- 过滤 Anthropic 风格的 `<system-reminder>`
- 使用消息前缀去重恢复真正的增量轮次
- 把 trace 转换成：
  - User
  - Tool Results
  - Assistant

最终这套逻辑沉淀在：

- `lib/dashboard-data.js`

### 8. 推理并发与增量评测重构

后续把 full official48 执行链路从“串行推理后统一评测”重构为：

- inference 支持并发执行
- eval worker 长驻轮询
- 某题一旦写入 `inference_summary.json`
- 对应评测立即开始

核心变动：

- `run_innercc_infer_official48.py`
  - 新增 `--max-concurrency`，默认 `2`
  - 新增 `inference_status.json`
  - 引入线程池并发推理
  - 引入 router 就绪等待与导出超时配置
  - 结果落盘改为线程安全原子写
- `run_official48_eval_worker.py`
  - 轮询 `inference_summary.json` + `inference_status.json`
  - 不再假设要等全部 48 题推理结束后再评测
- `monitor_official48_run.py`
  - 读取实时 `active_instances`
  - 能正确展示并发中的活跃 case 数
- `record_official48_progress.py`
  - 支持并发 active case 展示
- `run_official48_pipeline.sh`
  - 先启动增量评测 worker
  - 再启动并发 inference
  - 等评测追平后再收尾
- `watch_official48_supervisor.py`
  - 暴露：
    - `--inference-concurrency`
    - `--eval-max-concurrency`
    - `--cli-timeout-seconds`
    - `--router-ready-timeout-seconds`

### 9. Claude Code 兼容

runner 新增对 Claude Code 的非交互协议兼容：

- `custom_cli_case/run_custom_cli_case.py`
  - 识别 `--cli-bin /usr/bin/claude`
  - 自动改用：
    - `claude -p --output-format json --dangerously-skip-permissions --settings <settings> "Prompt"`
  - 不再对 Claude 使用 stdin 喂 prompt
  - 兼容 Claude 的整段 JSON stdout 输出

这使得 full official48 可以直接跑在 Claude Code 上，同时仍通过 llm_router 代理模型请求。

### 10. Run 别名 display_name

新增 run 级可编辑别名：

- 后端持久化文件：
  - `official48_runs/<run_id>/metadata.json`
- API：
  - `PATCH /api/run/[runId]`
- 前端：
  - `Selected Run` 面板支持输入、保存、清空
- 展示位置：
  - run card
  - comparison 表头
  - selected run 标题

清空 `display_name` 时：

- 会删除空的 `metadata.json`
- 内部仍继续用 `run_id` 做路径和主键

### 11. 看板运行中实时汇总

原先看板只在 `analysis/summary.json` 存在时显示 resolved / F2P / P2P。

后续补丁改成：

- 运行中的 run 也会按 `inference_summary.json`、`eval_worker_status.json`、已落盘 `report.json` 实时刷新 summary
- 不需要等整轮完成后再看统计

核心变动：

- `lib/dashboard-data.js`
  - `ensureSummary()` 改成运行中增量刷新
  - summary 是否重算取决于 inference / eval / report 的最新 mtime

### 12. 看板删除功能

新增 run 删除能力：

- 前端：
  - `components/dashboard-client.jsx`
  - 在 `Selected Run` 面板新增 `Delete Run`
  - 点击后弹确认框
- 后端：
  - `DELETE /api/run/[runId]`
  - `running` 状态返回 `409`
  - 非运行 run 删除：
    - `official48_runs/<run_id>`
    - `logs/run_evaluation/eval_input_<run_id>`
- 样式：
  - `app/globals.css` 新增危险按钮样式

### 13. README 重写与后续补充

原 README 的论文/benchmark 宣传内容已整体移除，改为中文运维手册：

- 保留当前仓库真正还在使用的内容
- 写清：
  - CLI 接入契约
  - 单题联调
  - official48 全量流程
  - llm_router 启停
  - Next 看板启停
  - `tmux` 后台模式
  - 关键参数、配置文件路径和可变项

### 14. `.gitignore` 调整

修改 `.gitignore` 以适配当前仓库结构：

- 忽略：
  - `.next/`
  - `node_modules/`
- 重新放行：
  - `package.json`
  - `package-lock.json`
  - `jsconfig.json`
  - `lib/dashboard-data.js`

这一步是为了让 Next 项目和新的数据层可以正常进版本控制。

## 建议纳入本次提交的内容

建议提交这些“代码 / 配置 / 文档”：

- `.gitignore`
- `README.md`
- `changelog.md`
- `SWE-bench/evaluate_instance.py`
- `package.json`
- `package-lock.json`
- `next.config.mjs`
- `jsconfig.json`
- `app/`
- `components/`
- `lib/`
- `custom_cli_case/run_custom_cli_case.py`
- `custom_cli_case/run_requests_case.sh`
- `custom_cli_case/README.md`
- `run_innercc_infer_official48.py`
- `run_official48_pipeline.sh`
- `run_official48_eval_worker.py`
- `monitor_official48_run.py`
- `record_official48_progress.py`
- `summarize_official48_run.py`
- `watch_official48_supervisor.py`

视你是否还要保留旧版实现，再决定是否提交这些“可疑/待确认”文件：

- `serve_official48_dashboard.py`
  - 当前 `18881` 已切到 Next.js，这个 Python dashboard 已不再是主入口
  - 如果要保留历史 fallback，可以提交
  - 如果不准备再用，建议直接删除，不要提交死代码
- `dashboard/`
  - 这是旧静态看板资源
  - 当前主入口已是 `app/` + Next
  - 建议删除而不是提交
- `instruction.md`
  - 这更像本机运维备忘，不一定适合作为仓库正式文档
- `run_innercc_batch.py`
  - 是本地 batch 修复 / 批跑辅助脚本，不在 README 主流程里
  - 如果后续还会用，可以提交；否则先不进主版本

## 不建议提交的内容

这些更像运行产物、缓存、数据快照或本机实验目录，建议不要提交：

- `.deps/`
- `node_modules/`
- `.next/`
- `official48_runs/`
- `official48_source/`
- `progress.md`
- `run_innercc_batch.out`
- `innercc_batch_case/`
- `single_case/`
- `custom_cli_case/workspace/`
- `custom_cli_case/run/`
- `custom_cli_case/hf_dataset/`
- `dashboard/`（如果决定完全迁移到 Next）

## 本版提交前建议再做的清理

1. 明确是否保留旧 Python dashboard：
   - `serve_official48_dashboard.py`
   - `dashboard/`
2. 明确是否提交本地实验辅助脚本：
   - `run_innercc_batch.py`
   - `instruction.md`
3. 确认不把任何运行数据目录放进 commit：
   - `official48_runs/`
   - `official48_source/`
   - `custom_cli_case/workspace/`
   - `custom_cli_case/hf_dataset/`
4. 提交前建议执行：

```bash
git status --short
npm run build
python3 -m py_compile run_innercc_infer_official48.py run_official48_eval_worker.py monitor_official48_run.py record_official48_progress.py summarize_official48_run.py watch_official48_supervisor.py
```

## 当前建议的 stage 范围

如果按“只提交主版本需要的内容”收口，建议最终 stage：

```bash
git add \
  .gitignore \
  README.md \
  changelog.md \
  SWE-bench/evaluate_instance.py \
  package.json \
  package-lock.json \
  next.config.mjs \
  jsconfig.json \
  app \
  components \
  lib \
  custom_cli_case/run_custom_cli_case.py \
  custom_cli_case/run_requests_case.sh \
  custom_cli_case/README.md \
  run_innercc_infer_official48.py \
  run_official48_pipeline.sh \
  run_official48_eval_worker.py \
  monitor_official48_run.py \
  record_official48_progress.py \
  summarize_official48_run.py \
  watch_official48_supervisor.py
```

如果你确认还要保留旧 Python 看板或其它辅助脚本，再额外补 stage。
