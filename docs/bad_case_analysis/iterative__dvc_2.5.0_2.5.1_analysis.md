# iterative__dvc_2.5.0_2.5.1 Analysis

本文遵循 [bad_case_analysis_design.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/bad_case_analysis_design.md) 的统一结构。

## 1. Case Metadata

- `instance_id`: `iterative__dvc_2.5.0_2.5.1`
- `repo`: `iterative/dvc`
- `innercc_run`: `20260427-154634`
- `claude_code_run`: `20260429-114027`
- `comparison_category`: `both_failed_but_claude_closer`
- 一句话结论：
  两个 CLI 都被 `tests/dir_helpers.py` 的 Python 3.12 兼容噪声带偏，直接改了测试辅助，而不是去修官方 patch 所在的 `dvc/objects/tree.py`、`dvc/fs/http.py` 和 `dvc/info.py`。因此 `5/5 F2P` 全部没过；`claude-code` 至少没引入额外回归，而 `innercc` 还把两条 plots P2P 打坏了。
- 根因标签：
  - `task_understanding_error`
  - `validation_gap`
  - `tooling_or_harness_issue`

## 2. Task And Gold Spec

### 2.1 benchmark task

`problem_statement` 涉及：

- `diff summary` 输出
- recursive add/progress bar 清理
- staging info() 优化
- `objects: hash_file: retrieve size from hash_info`

`FAIL_TO_PASS`: `5` 条：

- `tests/unit/objects/test_tree.py::test_size[trie_dict1-21]`
- `tests/unit/remote/test_http.py::test_content_length[headers0-3]`
- `tests/unit/remote/test_http.py::test_content_length[headers1-None]`
- `tests/unit/test_info.py::test_fs_info_outside_of_repo`
- `tests/unit/test_info.py::test_info_outside_of_repo`

`PASS_TO_PASS`: `24` 条。

这 5 条目标分别指向：

- tree size 计算
- HTTP metadata/content-length
- info 输出

它们都不在 `tests/dir_helpers.py`。

### 2.2 runner-level user query

prompt 给的是完整 release note + 5 条 failing tests。这里 benchmark task 已经足够集中，理论上不难定位到 `objects/tree`、`remote/http`、`info`。

### 2.3 trace-level agent goals

- `innercc`
  - 很快把任务收缩成 `TmpDir.__new__` 的 Python 3.12 兼容问题
- `claude-code`
  - 也沿着同一条假路径走，只是写法不同

### 2.4 official golden answer

官方 patch 的 relevant files 包括：

- `dvc/objects/tree.py`
- `dvc/objects/file.py`
- `dvc/fs/http.py`
- `dvc/info.py`
- 以及少量 `fs/dvc.py` / `objects/stage.py`

当前两边完全没有触及这些主文件。

## 3. Outcome Comparison

| CLI | resolved | F2P | P2P | cli_duration_ms | cli_num_turns | tool_use_count | tool_error_count |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `innercc` | `false` | `0/5` | `22/24` | `337284` | `51` | `50` | `11` |
| `claude-code` | `false` | `0/5` | `24/24` | `1470231` | `43` | `42` | `4` |

## 4. Artifact Index

### innercc

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_2.5.0_2.5.1/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_2.5.0_2.5.1/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_2.5.0_2.5.1/cli_result.json)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_2.5.0_2.5.1/router_trace_bundle.json)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_2.5.0_2.5.1/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_2.5.0_2.5.1/test_output.txt)

### claude-code

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_2.5.0_2.5.1/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_2.5.0_2.5.1/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_2.5.0_2.5.1/cli_result.json)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_2.5.0_2.5.1/router_trace_bundle.json)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_2.5.0_2.5.1/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_2.5.0_2.5.1/test_output.txt)

## 5. Chronological Trace Reconstruction

### 5.1 innercc

#### Phase A: correct failing-test read, wrong causal jump (`step 1-12`)

- 关键动作：
  - 读 `test_size`、`test_content_length`、`test_info_outside_of_repo`
  - 运行相关 tests
- 问题：
  - 很快从失败结果跳到 `TmpDir.__new__` 的 Python 3.12 兼容修复

#### Phase B: test-helper patch (`step 40-46`)

- 修改文件：
  - `tests/dir_helpers.py`
- 阶段结论：
  - 它相信只要测试 fixture 恢复，目标测试就会过

### 5.2 claude-code

#### Phase A: same fixture fixation (`step 2-15`)

- 关键动作：
  - 跑 5 条 target tests
  - 读 `tests/dir_helpers.py`
  - 看 `pathlib` internals
- 阶段结论：
  - 也把根因归到 `_from_parts` / `pathlib` 测试辅助兼容

#### Phase B: alternate helper patch (`step 38-45`)

- 修改文件：
  - `tests/dir_helpers.py`
- 写法：
  - `super().__new__(cls, *args, **kwargs)`

## 6. Hypothesis Iteration Log

| CLI | step_range | hypothesis | evidence_used | why_it_seemed_plausible | why_it_was_correct_or_wrong |
| --- | --- | --- | --- | --- | --- |
| `innercc` | `1-12` | 目标测试失败的主因是 `TmpDir` 在 Python 3.12 下坏了 | fixture/pathlib 噪声 | 当前环境确实有 `AttributeError` | 错，官方 patch 完全不在 tests/dir_helpers.py |
| `claude-code` | `2-15` | 一旦 `TmpDir.__new__` 修好，这 5 条就会恢复 | 同上 | 多条测试都先碰到 fixture | 错，真实修复点在 objects/tree/http/info |

## 7. Patch And Code-Level Analysis

### 7.1 innercc

- patch 只改：
  - `tests/dir_helpers.py`
- 结果：
  - `5/5 F2P` 继续失败
  - 还把两条 plots P2P 打坏

### 7.2 claude-code

- patch 也只改：
  - `tests/dir_helpers.py`
- 结果：
  - 同样 `5/5 F2P` 全失败
  - 但至少没引入新的 P2P 回归

## 8. Evaluation And Failure Evidence

来自 [innercc test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_2.5.0_2.5.1/test_output.txt) 的直接证据：

```text
FAILED tests/unit/objects/test_tree.py::test_size[trie_dict1-21]
FAILED tests/unit/remote/test_http.py::test_content_length[headers0-3]
FAILED tests/unit/remote/test_http.py::test_content_length[headers1-None]
FAILED tests/unit/test_info.py::test_info_outside_of_repo
FAILED tests/unit/test_info.py::test_fs_info_outside_of_repo
```

以及具体断言：

```text
E       AssertionError: assert {'etag': None, 'size': 3} == {'etag': None, ..., 'type': 'file'}
```

```text
E       AssertionError: assert []
```

这说明即使 fixture 噪声存在，真实失败仍落在 HTTP metadata 与 info 输出语义上。

## 9. Root Cause

- `direct_root_cause`
  - 两边都错误地把环境/fixture 兼容噪声当成 benchmark 主因。
- `contributing_factors`
  - 当前环境里的 `pathlib` 噪声先于真正业务断言出现，容易误导。
  - 没有对照官方 patch 文件集合。
- `non_root_but_misleading_signals`
  - `tests/dir_helpers.py` 的确存在兼容问题，但不是这题的官方修复主体。

## 10. CLI Optimization Opportunities

1. 即使测试先撞上 fixture/infra 噪声，也要继续追到首个业务断言。这个 case 里业务断言其实已经很明确地落在 tree size / HTTP metadata / info 输出。验证方式是分析报告必须区分 “首个环境噪声” 和 “首个业务失败断言”。
2. benchmark 要求 “只改非测试源码” 时，直接改 test helper 应视为高风险偏航信号，除非官方 patch 本身改 tests。
