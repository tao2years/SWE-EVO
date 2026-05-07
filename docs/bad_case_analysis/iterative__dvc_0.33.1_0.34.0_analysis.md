# iterative__dvc_0.33.1_0.34.0 Analysis

本文遵循 [bad_case_analysis_design.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/bad_case_analysis_design.md) 的统一结构。

## 1. Case Metadata

- `instance_id`: `iterative__dvc_0.33.1_0.34.0`
- `repo`: `iterative/dvc`
- `innercc_run`: `20260427-154634`
- `claude_code_run`: `20260429-114027`
- `comparison_category`: `both_failed_different_wrong_focus`
- 一句话结论：
  这是一个 release-note 长列表 case，但 benchmark 只关心 `tests/test_tag.py::TestTag::test` 这 1 条 F2P。`innercc` 锁定成 CLI subparser 冲突（`add` 重复注册），`claude-code` 锁定成 `remote add` 覆盖现有 section 的问题。两边都修了 release note 中的某一条真实 feature/bug，但都没对准 benchmark 实际目标测试，因此双双失败。
- 根因标签：
  - `task_understanding_error`
  - `hypothesis_lock_in`

## 2. Task And Gold Spec

### 2.1 benchmark task

`problem_statement` 是多条 release-item 列表：

- `metrics show` multiline formatting
- `remote add` overwrite existing sections
- `status` cache not present bug
- `pull` progress bar
- metrics file type by extension
...

但 benchmark 实际 `FAIL_TO_PASS` 只有：

- `tests/test_tag.py::TestTag::test`

`PASS_TO_PASS`: `77` 条。

这说明：

- release note 内容不能直接当作主问题
- 必须先用真实 failing test 倒推任务

### 2.2 runner-level user query

CLI 收到的是长 release-note prompt，但其中和 `test_tag.py::TestTag::test` 的关联并不显眼。

### 2.3 trace-level agent goals

- `innercc`
  - 锁定成 `dvc/cli.py` 里 `add` command 重复注册导致 argparse subparser 冲突

- `claude-code`
  - 锁定成 `CmdRemoteAdd` 没有阻止覆盖已有 remote section

两边都在“release note 中某条真实改动”上收敛，但都不是 benchmark 真正 target。

### 2.4 official golden answer

由于 benchmark target 是 `tests/test_tag.py::TestTag::test`，官方 gold spec 应该围绕 tag 功能或其依赖路径，而不是这两个 CLI/remote 话题。

也就是说，两个 agent 都先验地相信了 release note，而没有让 F2P 倒推真正故障。

## 3. Outcome Comparison

| CLI | resolved | F2P | P2P |
| --- | --- | --- | --- |
| `innercc` | `false` | `0/1` | `57/77` |
| `claude-code` | `false` | `0/1` | `57/77` |

两边连 P2P 结果都一样，说明：

- patch 落点都和 benchmark 实际目标关系很弱

## 4. Artifact Index

- [innercc patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_0.33.1_0.34.0/patch.diff)
- [claude patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_0.33.1_0.34.0/patch.diff)
- [innercc report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_0.33.1_0.34.0/report.json)
- [claude report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_0.33.1_0.34.0/report.json)

## 5. Chronological Trace Reconstruction

### 5.1 innercc

- 工具分布：`Bash 42 / Read 11 / Edit 1`
- 关键轨迹：
  - 快速发现 `dvc/cli.py` 中 `add` command 重复注册
  - 认为 argparse subparser 冲突就是问题核心

### 5.2 claude-code

- 工具分布：`Bash 27 / Grep 21 / Read 9 / Edit 3`
- 关键轨迹：
  - 快速发现 `CmdRemoteAdd` 没检查 remote section 已存在
  - 认为 `remote add` 覆盖是主要 bug

## 6. Hypothesis Iteration Log

| CLI | 核心假设 | 结果 |
| --- | --- | --- |
| `innercc` | benchmark target 来源于 CLI subparser 冲突 | 错 |
| `claude-code` | benchmark target 来源于 `remote add` overwrite | 也错 |

## 7. Patch And Code-Level Analysis

### 7.1 innercc

只改：

- `dvc/cli.py`

删除重复 `add` command 注册。

### 7.2 claude-code

只改：

- `dvc/command/remote.py`

给 `remote add` 增加已存在 section 检查。

两边 patch 本身都合理，但不是 benchmark 所需 patch。

## 8. Evaluation And Failure Evidence

决定性证据不在 patch 细节，而在任务错靶：

- benchmark F2P 只有 `test_tag.py::TestTag::test`
- 两边 patch 都没覆盖 tag 功能或其依赖链

## 9. Root Cause

- `task_understanding_error`
  - 完全按 release note 热点词汇走，而没按 F2P 真实目标定位
- `hypothesis_lock_in`
  - 一旦找到一个“看起来像 bug 的 release item”，就直接收工

## 10. CLI Optimization Opportunities

1. 对 `FAIL_TO_PASS` 极少而 release note 极长的 case，必须优先按测试名反查模块。
2. 如果 patch 没碰 failing test 所在模块附近，禁止结束。
