---
name: eval-run-rootcause-synthesis
description: 深度对比多个 benchmark 或评测 run 的结果、成本、token、patch 与 evaluator 产物，并把 run 级指标拆回 case 级差异，定位真正的根因。用于比较不同模型、CLI 版本、prompt 版本、功能开关或构建版本时，解释为什么 resolved/F2P/P2P/cost/cache hit 发生变化，尤其适用于 official48_runs、analysis/summary.json、analysis/cases.csv、cli_result.json、patch.diff、report.json、test_output.txt、eval_worker_logs 的证据化复盘。默认输出一份中文深度分析文档，并明确区分模型能力变化、任务理解偏差、接口契约问题与环境/安装噪音。
---

# Eval Run Rootcause Synthesis

按下面流程做多 run 对比，默认产出一份中文深度分析文档。

## 1. 先建 run 映射

先为每个待比较 run 收集：

- `official48_runs/<run_id>/metadata.json`
- `official48_runs/<run_id>/analysis/summary.json`
- `official48_runs/<run_id>/analysis/cases.csv`

先回答三个基础问题：

1. 比较的是哪些 run，版本名分别是什么。
2. 这些 run 的 `resolved`、`f2p micro`、`p2p micro`、`cost`、`turns`、`input tok`、`cache hit` 分别是多少。
3. 哪些 run-level 指标真的发生了变化，哪些只是看板四舍五入后相同。

如果用户给了看板数字，也必须回到 `summary.json` 复核。

## 2. 明确统计口径

如果出现 `f2p micro` / `p2p micro`，必须先解释口径。

优先回看：

- `runtime/summarize_official48_run.py`

默认要说明：

- `micro` 是“把所有测试条目先汇总，再算总通过率”
- 不是“按 case 百分比做平均”

如果多个 run 的看板数字一样，必须把分子分母拆出来，看是否只是四舍五入撞值。

## 3. 先做 case 级 delta matrix

对每个 case，至少拉出下面这些字段：

- `resolved`
- `f2p_success / f2p_total`
- `p2p_success / p2p_total`
- `p2p_failure`
- `cli_num_turns`
- `cli_total_cost_usd`
- `cli_model_input_tokens`

优先回答：

1. 哪些 case 完全不变。
2. 哪些 case 决定了 `resolved` 的变化。
3. 哪些 case 决定了 `f2p micro` 的变化。
4. 哪些 case 主导了 `p2p micro` 的变化。
5. 哪些 case 在“质量不变”的前提下，成本明显飙升。

不要把 run-level 变化平均摊到所有 case 上。

## 4. 只深挖 driver cases

优先深挖对 run-level 结论贡献最大的 case。常见 driver case：

- 让 `resolved` 发生变化的 case
- 贡献了大部分 `p2p_failure` 的 case
- 让成本大幅上升但结果没变的 case

每个 driver case 至少取：

- `infer/runs/<instance_id>/cli_result.json`
- `infer/runs/<instance_id>/cli_stdout.log`
- `infer/runs/<instance_id>/patch.diff`
- `eval_worker_logs/<instance_id>.log`
- `logs/run_evaluation/eval_input_<run_id>/.../<instance_id>/report.json`
- `logs/run_evaluation/eval_input_<run_id>/.../<instance_id>/test_output.txt`

如果 `router_trace_bundle.json` 是空的，直接在文档里说明，然后退回 `cli_stdout.log` 与 evaluator 产物，不要假装有逐轮 trace。

## 5. 根因归因时必须区分四类原因

### A. 模型能力变化

适用信号：

- 新版 patch 落点更接近真实故障层
- 新版把接口契约补齐了
- 新版能命中同一 case 的正确 hunk，而旧版不能

典型标签：

- `localization_improved`
- `contract_alignment_improved`
- `validation_better_targeted`

### B. 任务理解偏差

适用信号：

- agent 的 `cli_stdout.log` 最终总结就已经把问题说偏了
- patch 只覆盖了局部表象，没有覆盖 evaluator 真正报错点

典型标签：

- `task_understanding_error`
- `hypothesis_lock_in`
- `self_report_optimism`

### C. 环境 / 安装噪音

适用信号：

- `pdm add` / `make install` / `pip install` / lockfile resolve 出现 `ReadTimeout`
- `PdmException`
- `ImportError`
- 依赖版本有没有被真正更新，和 patch 表面是否相同一起看

必须特别注意：

- “同样的 patch + 不同的 install 结果 = 不能只归因给模型”
- 如果一个 case 的大量 P2P 回归来自 collection/import 阶段崩溃，要明确写成环境兼容问题扩散，不要写成几千个独立语义点都错了

典型标签：

- `evaluation_setup_noise`
- `dependency_resolution_nondeterminism`
- `environment_compatibility_break`

### D. 验证没收口

适用信号：

- agent 自称“all tests pass”或“fix complete”，但 evaluator 不认
- 只验证了局部 smoke，没有验证目标测试或关键邻近路径

典型标签：

- `validation_gap`
- `termination_error`

## 6. 特别规则

### 同 patch 不同结果

如果两个 run 的 `patch.diff` 看起来一样，但 evaluator 结果完全不同，优先检查：

1. `test_output.txt` 里的安装阶段日志
2. `make install` 是否成功
3. 依赖是否真的更新
4. collection 阶段是否发生 import 错误

这种情况默认不要直接写“context 更强”“模型更好”，先确认是否是环境变量。

### 自报成功不可信

`cli_stdout.log` 和 `cli_result.json` 的“all tests pass”只算 agent 自报，不算最终证据。

最终判定必须以：

- `report.json`
- `tests_status`
- `test_output.txt`
- `eval_worker_logs`

为准。

### 大 case 主导 P2P

如果一个 case 占据绝大多数 `p2p_failure`，必须明确写：

- `p2p micro` 主要由该 case 决定
- 其他 case 只解释尾数差异

不要把 run-level `p2p` 的变化误写成“全面稳定性提升”。

## 7. 输出要求

默认输出一份中文深度文档，使用 [references/report-outline.md](references/report-outline.md) 的结构。

最低要求：

- 只保留一份主文档作为这轮分析的主产物
- 文档里要显式说明数据源与限制
- 要有 run 级表、case 级矩阵、driver case 深挖、根因排序、能力变化 vs 环境噪音的区分
- 结论必须能回指到具体文件、具体数字或具体失败文本

如果仓库里已经有更窄的临时报告，可以保留，但新的主文档必须在正文中明确自己是本轮最终汇总。
