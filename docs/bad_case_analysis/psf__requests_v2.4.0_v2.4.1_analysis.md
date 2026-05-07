# psf__requests_v2.4.0_v2.4.1 Analysis

本文遵循 [bad_case_analysis_design.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/bad_case_analysis_design.md) 的统一结构。

## 1. Case Metadata

- `instance_id`: `psf__requests_v2.4.0_v2.4.1`
- `repo`: `psf/requests`
- `innercc_run`: `20260427-154634`
- `claude_code_run`: `20260429-114027`
- `comparison_category`: `inner_closer_but_both_failed`
- 一句话结论：
  这题是个“小而尖”的 requests bugfix case：目标包括 `ProtocolError` 重抛和“自重定向死循环”处理。`innercc` 同时做了 release-note 指向的两个修复，因此 `F2P = 2/2`，但它混入了大量 Python 3.12 `collections.abc` 兼容改动，导致 `P2P` 回归 1 条，最终未 resolved。`claude-code` 则几乎只修了自重定向这一半，所以只过了 `1/2`。
- 根因标签：
  - `validation_gap`
  - `task_understanding_error`

## 2. Task And Gold Spec

### 2.1 benchmark task

`problem_statement`:

- Capture and re-raise urllib3 `ProtocolError`
- Bugfix for responses that attempt to redirect to themselves forever

`FAIL_TO_PASS`: `2` 条。

这是一个真正的小型双子任务 case。

### 2.2 runner-level user query

CLI 收到的 prompt 明确列出了上述两个行为点，因此这里的任务定义相对清晰。

### 2.3 trace-level agent goals

- `innercc`
  - 明确说要同时做：
    - `ProtocolError` fix
    - redirect-to-itself fix
    - 外加 Python 3.12 compatibility

- `claude-code`
  - trace 中几乎只围绕：
    - infinite redirect loop
  - 基本没展开 `ProtocolError` 这条线

### 2.4 official golden answer

从 patch 对照看，和任务直接相关的核心应该至少包括：

- `requests/adapters.py` 中 `ProtocolError -> ConnectionError`
- `requests/sessions.py` 中 redirect-to-self 检测

Python 3.12 `collections.abc` 兼容并不是本 benchmark 主体要求。

## 3. Outcome Comparison

| CLI | resolved | F2P | P2P | cli_duration_ms | cli_num_turns | tool_use_count | tool_error_count |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `innercc` | `false` | `2/2` | `135/136` | `427785` | `85` | `84` | `?` |
| `claude-code` | `false` | `1/2` | `134/136` | `689945` | `38` | `35` | `?` |

`innercc` 更接近完成，但因为混入额外兼容改动仍然打出了 1 条 P2P 回归。

## 4. Artifact Index

- [innercc patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/psf__requests_v2.4.0_v2.4.1/patch.diff)
- [claude patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/psf__requests_v2.4.0_v2.4.1/patch.diff)
- [innercc report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/psf__requests_v2.4.0_v2.4.1/report.json)
- [claude report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/psf__requests_v2.4.0_v2.4.1/report.json)

## 5. Chronological Trace Reconstruction

### 5.1 innercc

- 工具分布：`Read 36 / Bash 34 / Edit 14`
- 核心假设：
  - 同时修 `ProtocolError` 与 redirect loop
  - 再顺手解决 Python 3.12 `collections` 兼容问题

### 5.2 claude-code

- 工具分布：`Grep 17 / Read 13 / Bash 4 / Edit 4`
- 核心假设：
  - 主问题是 redirect-to-itself infinite loop

## 6. Hypothesis Iteration Log

| CLI | 核心假设 | 结果 |
| --- | --- | --- |
| `innercc` | 两条 release-note bugfix 都要修，再补兼容噪声 | F2P 全过，但引入 1 条 P2P 回归 |
| `claude-code` | redirect loop 是主问题 | 只修到 `1/2` |

## 7. Patch And Code-Level Analysis

### 7.1 innercc

核心业务修复：

- `requests/adapters.py`
  - `ProtocolError -> ConnectionError`
- `requests/sessions.py`
  - self-redirect break

额外兼容改动：

- `cookies.py`
- `models.py`
- `_collections.py`
- `structures.py`
- `utils.py`

问题在于：

- benchmark 主体很小
- 额外兼容补丁增加了无关回归面

### 7.2 claude-code

核心 patch 只落在：

- `requests/sessions.py`

几乎没碰 `ProtocolError` 这条线。

## 8. Evaluation And Failure Evidence

`innercc`：

- `F2P = 2/2`
- `P2P = 135/136`

说明主 bug 已修到，但额外兼容改动带来了非目标回归。

`claude-code`：

- `F2P = 1/2`
- 说明只完成了一半 release-note 目标

## 9. Root Cause

- `innercc`
  - 主要问题不是定位，而是过度修复
- `claude-code`
  - 主要问题是任务覆盖不足，只抓住了一条 bugfix

## 10. CLI Optimization Opportunities

1. 对小型双子任务 case，必须显式检查两条 release-note bugfix 是否都已覆盖。
2. 如果 benchmark 主体很小，不应额外混入大面积兼容补丁，除非这些补丁已被验证不会带来回归。
