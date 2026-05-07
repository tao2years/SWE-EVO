# conan-io__conan_2.0.14_2.0.15 Analysis

本文遵循 [bad_case_analysis_design.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/bad_case_analysis_design.md) 的统一结构。

## 1. Case Metadata

- `instance_id`: `conan-io__conan_2.0.14_2.0.15`
- `repo`: `conan-io/conan`
- `innercc_run`: `20260427-154634`
- `claude_code_run`: `20260429-114027`
- `comparison_category`: `both_failed_but_claude_closer`
- 一句话结论：
  这是一个超大 release-note 打包 case。`innercc` 试图一次性覆盖大量 `platform_requires` / `replace_requires` / output / deploy 相关改动，修改面很大却没有形成稳定闭环，导致 `0/72` F2P、`161/649` P2P。`claude-code` 同样失败，但至少命中了 `platform_requires` 家族中的 `11` 条目标测试，回归也少得多，说明它比 `innercc` 更接近任务主轴。
- 根因标签：
  - `task_understanding_error`
  - `validation_gap`
  - `hypothesis_lock_in`

## 2. Task And Gold Spec

### 2.1 benchmark task

`problem_statement` 是一整批 `2.0.15` 功能与行为更新的聚合，其中包含：

- `conan lock remove`
- `CMake.ctest()`
- `<host_version>` tracking syntax
- `tools.microsoft:winsdk_version`
- `pkglist formatter`
- `CONAN_LOG_LEVEL`
- `platform_requires`
- `replace_requires`
- `replace_tool_requires`
- warning handling / treat warnings as errors
- deploy / install / list / output 等多条链路

`FAIL_TO_PASS`: `72` 条。

代表性样例：

- `conans/test/integration/build_requires/test_build_requires_source_method.py::TestBuildEnvSource::test_source_buildenv`
- `conans/test/integration/command_v2/test_graph_find_binaries.py::TestDistance::test_multiple_distance_ordering`
- `conans/test/integration/graph/test_platform_requires.py::...`
- `conans/test/integration/graph/test_replace_requires.py::...`

`PASS_TO_PASS`: `649` 条。

这个 case 的关键特征是：

- release note 很大
- F2P 横跨多个子系统
- 不可能通过只改 1-2 个函数就解决

### 2.2 runner-level user query

两个 CLI 实际收到的是同一条 prompt：要求基于上述 release note 做最小 code-only fix，并通过 `72` 条 F2P。

这条 prompt 的危险点是：

- release note 非常长，但没有替 agent 明确切分子任务
- 如果不先按 failing tests 聚类，agent 很容易只抓住自己最熟悉的一部分

### 2.3 trace-level agent goals

- `innercc`
  - trace 中反复强调：
    - `platform_requires`
    - `replace_requires`
    - `replace_tool_requires`
    - warning-as-error
    - deploy / install / list / output 行为
  - 最终总结里声称自己“实现了 31 个非测试文件改动”

- `claude-code`
  - trace 中也抓到了：
    - `platform_requires`
    - `platform_tool_requires`
    - profile / graph resolution 相关行为
  - 但修改面明显比 `innercc` 小很多

### 2.4 official golden answer

官方 patch 很大，但从 F2P 分布看，核心修复至少包括：

- graph / profile / platform requires 解析与优先级
- output warning / error 处理
- install / deploy 行为
- output / formatter / profile serialization

`innercc` 和 `claude-code` 都命中了其中一部分，但都没有形成对完整任务面的有效覆盖。

## 3. Outcome Comparison

| CLI | resolved | F2P | P2P | cli_duration_ms | cli_num_turns | tool_use_count | tool_error_count |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `innercc` | `false` | `0/72` | `161/649` | `869964` | `209` | `208` | `2` |
| `claude-code` | `false` | `11/72` | `625/649` | `814365` | `87` | `93` | `6` |

最关键的对比不是两边都失败，而是失败形态：

- `innercc`：
  - 一个都没修到
  - 回归面巨大
- `claude-code`：
  - 修到了 `11` 条 `platform_requires` / `replace_requires` 相关 F2P
  - 只引入 `24` 条 P2P 回归

说明：

- `innercc` 的问题是“大范围改动但缺少稳定验证”
- `claude-code` 的问题是“任务覆盖率不够，但局部收敛更稳”

## 4. Artifact Index

### innercc

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/conan-io__conan_2.0.14_2.0.15/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/conan-io__conan_2.0.14_2.0.15/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/conan-io__conan_2.0.14_2.0.15/cli_result.json)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/conan-io__conan_2.0.14_2.0.15/router_trace_bundle.json)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/conan-io__conan_2.0.14_2.0.15/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/conan-io__conan_2.0.14_2.0.15/test_output.txt)

### claude-code

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/conan-io__conan_2.0.14_2.0.15/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/conan-io__conan_2.0.14_2.0.15/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/conan-io__conan_2.0.14_2.0.15/cli_result.json)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/conan-io__conan_2.0.14_2.0.15/router_trace_bundle.json)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/conan-io__conan_2.0.14_2.0.15/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/conan-io__conan_2.0.14_2.0.15/test_output.txt)

## 5. Chronological Trace Reconstruction

### 5.1 innercc

#### Phase A: broad feature expansion

- 工具分布：`Bash 77 / Edit 74 / Read 57`
- 关键迹象：
  - 最终总结明确说自己修改了 `31` 个非测试文件
  - 这说明它没有先聚焦 F2P，而是按 release notes 做了大面积实现

#### Phase B: hypothesis

- 核心内部假设：
  - 这题的主轴是 `platform_requires` / `replace_requires` / output warning / deploy 相关的一整批新能力
- 这个假设并非全错，但任务面太宽，导致每个子点验证都不够深

#### Phase C: termination

- 它在大量修改后直接结束，缺乏“72 条 F2P 覆盖率”级别的闭环

### 5.2 claude-code

#### Phase A: narrower focus

- 工具分布：`Bash 29 / Grep 24 / Read 21 / Edit 11`
- 关键迹象：
  - 它比 `innercc` 更聚焦 graph/profile resolution
  - trace 中明确回头补看 `platform_tool_requires`

#### Phase B: hypothesis

- 核心内部假设：
  - `platform_requires` / `platform_tool_requires` 是 release 中最关键、最能解释 F2P 的一块

#### Phase C: termination

- 虽然也提前收工，但至少其 patch 与已修成的 `11` 条 F2P 是对齐的

## 6. Hypothesis Iteration Log

### 6.1 innercc

| step_range | hypothesis | evidence_used | why_it_seemed_plausible | why_it_was_correct_or_wrong |
| --- | --- | --- | --- | --- |
| early | 必须一次性覆盖整批 release features | 超长 release note | release notes 的确非常大 | 方向过宽，验证跟不上 |
| late | 大面积改动后任务已完成 | git diff +局部实现完成感 | 改了很多文件，看似覆盖很全 | 错，因为 `72` 条 F2P 一条都没通过 |

### 6.2 claude-code

| step_range | hypothesis | evidence_used | why_it_seemed_plausible | why_it_was_correct_or_wrong |
| --- | --- | --- | --- | --- |
| early | `platform_requires` 是关键主轴 | failing tests 中确有大量 `platform_requires` 相关测试 | 这解释了部分 F2P | 只覆盖了局部，不足以 resolve 全案 |

## 7. Patch And Code-Level Analysis

### 7.1 innercc patch

patch 很大，涉及：

- `conan/api/model.py`
- `conan/api/output.py`
- `conan/api/subapi/install.py`
- `conans/client/graph/graph_builder.py`
- `conans/client/profile_loader.py`
- `conans/model/conan_file.py`

问题不是“改错一个函数”，而是：

- 修改面过大
- 和 F2P 分布没有形成逐条映射
- 最后 evaluator 上表现为大规模回归

### 7.2 claude-code patch

patch 更集中在：

- `graph_builder.py`
- `profile_loader.py`
- profile / replace / platform requires 家族

这解释了为什么它至少修到了 `11` 条相近 F2P。

## 8. Evaluation And Failure Evidence

### 8.1 innercc

关键结果：

- `F2P success = []`
- `P2P failure = 488`

这说明它不是“差一点”，而是 patch 面虽然大，但没有形成稳定行为。

### 8.2 claude-code

关键结果：

- `F2P success sample` 中全是 `platform_requires` / `replace_requires` 家族
- `F2P failure sample` 里仍残留：
  - `build_requires source method`
  - `graph find binaries`
  - profile / distance / option 相关测试

这说明它成功修到了一个子簇，但漏掉了其它子簇。

## 9. Root Cause

### 9.1 direct root cause

- `innercc`
  - `task_understanding_error`: 把 case 当成“整包实现任务”，但没有对应的整包验证能力
- `claude-code`
  - `task_understanding_error`: 把 case收缩成 `platform_requires` 主轴，导致只修到一个测试簇

### 9.2 contributing factors

- `validation_gap`
  - 两边都没有按 `72` 条 F2P 做子簇覆盖率验证
- `hypothesis_lock_in`
  - `innercc` 锁在“大面积实现”
  - `claude-code` 锁在“platform requires 是主问题”

## 10. CLI Optimization Opportunities

1. 对大 release-note case，先做 F2P 聚类，不允许直接按 release notes 顺序实现。
2. 结束前必须回答：
   - patch 覆盖了哪些 failing-test 子簇
   - 还没覆盖哪些
3. 如果 patch 很大但 F2P success 仍是 `0`，要触发“实现面与任务面脱节”告警。
