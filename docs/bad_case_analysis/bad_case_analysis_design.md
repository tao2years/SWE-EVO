# Bad Case Analysis Design

本文档定义 SWE-EVO official48 中 `innercc` 与 `claude-code` bad case 分析的统一方法论。目标不是只汇报结果，而是把每个 bad case 变成可复盘、可归因、可迁移、可转化为 CLI 优化动作的证据包。

## 1. 设计目标

每篇 bad case 文档都必须完整回答下面 6 个问题：

1. benchmark 真实任务是什么，runner 实际发给 CLI 的用户 query 是什么。
2. 官方 golden answer 是什么，它到底修了哪个行为。
3. 两个 CLI 的推理轨迹按时间顺序做了什么，每个阶段的工作目标是什么。
4. CLI 的核心假设是如何形成、迭代、锁定、或者被证伪的。
5. 失败根因具体落在哪一层：任务理解、故障定位、代码编辑、验证闭环、结束策略，还是工具/框架层面。
6. 从 CLI 设计角度，哪些策略可以缓解这一类 bad case。

如果某篇文档读完后，仍然需要读者自己去猜：

- “用户到底让它修什么”
- “官方参考答案是什么”
- “为什么它会在这一步偏航”

那这篇文档就不合格。

## 2. 证据源与术语

### 2.1 任务定义

每个 case 要明确区分 3 层任务定义：

1. `benchmark_task`
   - 来源：`official48_source/output_final/<instance_id>.json`
   - 字段：`problem_statement` + `FAIL_TO_PASS`
   - 作用：定义 benchmark 官方希望修复的行为

2. `runner_query`
   - 来源：`custom_cli_case/run_custom_cli_case.py` 的 `build_prompt()`
   - 作用：定义 CLI 实际收到的用户 query
   - 这是文档里必须原样还原的 prompt

3. `agent_derived_goal`
   - 来源：`router_trace_bundle.json` 中 agent 在推理过程中自己形成的子目标、todo、阶段性结论
   - 作用：分析 CLI 如何把原任务重写成自己的内部计划

### 2.2 官方 golden answer

默认把 benchmark JSON 中的下列字段视作官方 golden answer：

- `patch`
- `test_patch`

分析时需要明确区分：

- `official_golden_patch`
- `official_golden_test_patch`
- `innercc_patch`
- `claude_code_patch`

注意：

- 不把某个 CLI 的成功 patch 当作 golden answer。
- 如果 `patch` 中含有文档、版本号、workflow 等非行为必要改动，分析时要单独指出“核心代码修复 hunk”。

### 2.3 推理轨迹证据

trace 相关证据默认来自：

- `official48_runs/<run_id>/infer/runs/<instance_id>/router_trace_bundle.json`
- `cli_result.json`
- `cli_stdout.log`
- `cli_stderr.log`

其中 `router_trace_bundle.json` 是主证据，负责回答：

- 每一步用了什么工具
- 读了哪些关键文件
- 跑了哪些关键命令
- 哪一步开始形成/锁定错误假设

### 2.4 评测证据

评测相关证据默认来自：

- `official48_runs/<run_id>/eval_worker_logs/<instance_id>.log`
- `logs/run_evaluation/eval_input_<run_id>/eval_input_<run_id>/<instance_id>/report.json`
- `logs/run_evaluation/eval_input_<run_id>/eval_input_<run_id>/<instance_id>/test_output.txt`
- `logs/run_evaluation/eval_input_<run_id>/eval_input_<run_id>/<instance_id>/run_instance.log`

其中：

- `report.json` 给出最终 resolved、F2P、P2P 结论
- `test_output.txt` 给出真实 traceback、失败断言和 import/syntax/runtime 证据
- `run_instance.log` 给出 patch 应用与 evaluator 包装层信息

## 3. 单 Case 文档模板

每篇 `docs/bad_case_analysis/<instance_id>_analysis.md` 固定包含以下 10 节，顺序不变。

### 3.1 Case Metadata

必须包含：

- `instance_id`
- `repo`
- `run_id`
- `cli_a` / `cli_b`
- 一句话结论
- 根因标签

### 3.2 Task And Gold Spec

必须回答：

- benchmark 任务是什么
- runner 实际 query 是什么
- 官方 golden patch 核心修复是什么
- 官方 golden test patch 在验证什么

这一节必须包含：

- `problem_statement`
- 渲染后的 `runner_query`
- `FAIL_TO_PASS`
- `PASS_TO_PASS` 规模或样例
- golden patch 关键 hunk

### 3.3 Outcome Comparison

至少对比：

- `resolved`
- `FAIL_TO_PASS` 通过率
- `PASS_TO_PASS` 通过率/回归数
- `cli_duration_ms`
- `cli_num_turns`
- `tool_use_count`
- `tool_error_count`
- `patch_successfully_applied`
- `anomaly_flags`

### 3.4 Artifact Index

只做索引，不做解释。必须列出两个 CLI 的：

- `patch.diff`
- `preds.json`
- `cli_result.json`
- `cli_stdout.log`
- `cli_stderr.log`
- `router_trace_bundle.json`
- `eval_worker_log`
- `report.json`
- `test_output.txt`
- `run_instance.log`

### 3.5 Chronological Trace Reconstruction

这是文档的核心部分。

必须把推理过程按阶段重建，阶段标签固定为：

- `bootstrap`
- `repo_exploration`
- `task_planning`
- `fault_localization`
- `hypothesis_testing`
- `code_editing`
- `validation`
- `termination`

每个阶段必须写：

- `step_range`
- 关键工具
- 关键文件
- 关键命令
- 当前阶段目标
- 阶段产出

### 3.6 Hypothesis Iteration Log

必须用表记录关键假设的变化，列固定为：

- `step_range`
- `hypothesis`
- `evidence_used`
- `why_it_seemed_plausible`
- `why_it_was_correct_or_wrong`

如果 CLI 一直围绕错误假设反复实验，要明确标为 `hypothesis_lock_in`。

### 3.7 Patch And Code-Level Analysis

必须回答：

- patch 改了哪些文件/函数
- 是否命中真实故障点
- 是否过宽或过窄
- 是否引入语法错误、非法字符、错误 API、错误条件分支
- 与 golden patch 的核心差异是什么

### 3.8 Evaluation And Failure Evidence

必须基于 `report.json` 和 `test_output.txt` 回答：

- 是“没修到”还是“修坏了”
- 最深项目内 traceback 在哪里
- 失败断言是什么
- F2P 哪些测例过/没过
- P2P 是否有大面积回归

### 3.9 Root Cause

必须分成 3 层：

1. `direct_root_cause`
2. `contributing_factors`
3. `non_root_but_misleading_signals`

统一标签集合：

- `task_understanding_error`
- `localization_error`
- `hypothesis_lock_in`
- `edit_safety_error`
- `validation_gap`
- `termination_error`
- `tooling_or_harness_issue`

### 3.10 CLI Optimization Opportunities

必须拆成两类：

1. `case_specific_actions`
2. `generalizable_actions`

每条建议至少包含：

- 优化点
- 为什么能缓解这个问题
- 适用于哪类 case
- 如何验证它是否有效

## 4. Trace 重建规则

### 4.1 Step 定义

默认把 `router_trace_bundle.json` 中按时间顺序出现的 assistant 响应块编号为 `step 1, step 2, ...`。

一个 step 可以包含：

- 一段 assistant 文本
- 一个或多个工具调用
- 两者同时存在

### 4.2 Phase 切分规则

phase 切分不是按工具类型，而是按意图：

- `bootstrap`
  - 读取当前目录、仓库结构、版本、基本环境信息

- `repo_exploration`
  - 读代码、grep 测试、找相关文件与函数

- `task_planning`
  - 明确说出“问题有几部分”“需要先看什么再改什么”

- `fault_localization`
  - 把问题定位到某个函数、某个层级、某个调用链

- `hypothesis_testing`
  - 构造局部 Python 脚本、pytest 子集、最小复现去验证假设

- `code_editing`
  - 发生 `Edit` / `Write`

- `validation`
  - 修改后执行验证命令、读 diff、做 smoke test

- `termination`
  - 输出“fix complete”或停止继续验证

### 4.3 每阶段的最小记录粒度

每个 phase 不能只写一句抽象总结，必须至少写到：

- 读了哪个文件
- 搜了哪个关键字
- 跑了哪类命令
- 是否跑了 exact failing test
- 是否用了可能吞退出码的 pipeline
- 这一阶段结束时，CLI 认为问题是什么

## 5. 分析流程

每个 case 必须按下面顺序分析：

1. 读 `summary.json` / `report.json`
   - 先判断属于“没修到”还是“修坏了”

2. 读 `test_output.txt`
   - 找最深项目内 traceback
   - 找失败断言
   - 找 import / syntax / runtime 级证据

3. 对照 `patch.diff`
   - 判断补丁是否命中真实故障帧
   - 判断补丁是否过宽

4. 读 `router_trace_bundle.json`
   - 重建时间线
   - 识别阶段
   - 记录关键假设变化

5. 再回到代码与评测结果
   - 证明 patch 为什么成功 / 为什么失败

6. 最后写 root cause 和 CLI 优化建议

## 6. 根因判定标准

### 6.1 `task_understanding_error`

适用条件：

- 没理解 release note 真正要求
- 把修复目标理解成更宽或更窄的问题

### 6.2 `localization_error`

适用条件：

- traceback 指向 A，补丁落在 B
- 修了错误层级、错误函数、错误调用阶段

### 6.3 `hypothesis_lock_in`

适用条件：

- 早期假设形成后，后续实验全围绕它展开
- 即便 evaluator / traceback 有反证，CLI 仍未回头修正定位

### 6.4 `edit_safety_error`

适用条件：

- 非 ASCII 标点进入源码
- 语法损坏
- patch 引入明显额外回归

### 6.5 `validation_gap`

适用条件：

- 没跑 exact failing test
- 验证命令吞退出码或截断错误
- 没做 import / py_compile / smoke test

### 6.6 `termination_error`

适用条件：

- 还没验证关键断言就结束
- 明显失败后仍宣布完成

### 6.7 `tooling_or_harness_issue`

适用条件：

- CLI 根本没成功启动
- runner / router / evaluator 造成非任务本身的阻断

## 7. 质量门槛

一篇 case 文档只有满足下面条件才算合格：

1. 能单独阅读，不需要读者先手工翻 trace 文件。
2. 明确写出 benchmark task、runner query、golden patch。
3. 明确写出 chronological trace reconstruction，而不是只给工具计数。
4. 根因判断必须同时有：
   - patch 证据
   - trace 证据
   - evaluator 证据
5. CLI 优化建议不能停留在口号，必须可验证。

## 8. 当前执行顺序建议

首批先做 4 篇：

1. `psf__requests_v2.12.2_v2.12.3`
2. `dask__dask_2024.3.1_2024.4.0`
3. `iterative__dvc_1.0.0b6_1.0.0`
4. `dask__dask_2023.9.2_2023.9.3`

这 4 篇能覆盖：

- 编辑安全错误
- 错层定位
- 部分修复
- 假设锁定
- 验证闭环缺失
