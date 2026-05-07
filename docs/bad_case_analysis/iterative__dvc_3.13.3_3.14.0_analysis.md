# iterative__dvc_3.13.3_3.14.0 Analysis

本文遵循 [bad_case_analysis_design.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/bad_case_analysis_design.md) 的统一结构。

## 1. Case Metadata

- `instance_id`: `iterative__dvc_3.13.3_3.14.0`
- `repo`: `iterative/dvc`
- `innercc_run`: `20260427-154634`
- `claude_code_run`: `20260429-114027`
- `comparison_category`: `both_failed_same_misread`
- 一句话结论：
  两个 CLI 都把这个 config case 缩成了“处理 `~` home dir”这一小点。`innercc` 至少在 `dvc/config.py` 里补了 `expanduser`，但没引入官方的 `_resolve()` / `ExpPath` / `local_dvc_dir` / `merge()` 这一整套路径解析与 config 合并逻辑；`claude-code` 更差，连有效 patch 都没有留下，最终 `patch.diff` 为空，`13/13` 全挂。
- 根因标签：
  - `task_understanding_error`
  - `validation_gap`
  - `termination_error`

## 2. Task And Gold Spec

### 2.1 benchmark task

`problem_statement`:

```text
## What's Changed
### 🐛 Bug Fixes
* config: resolve: handle ~ home dir by @efiop in https://github.com/iterative/dvc/pull/9825
* config: use local config from local_dvc_dir by @efiop in https://github.com/iterative/dvc/pull/9827
* fetch: merge config instead of updating by @efiop in https://github.com/iterative/dvc/pull/9828
```

`FAIL_TO_PASS`: `13` 条，分两簇：

- `tests/func/test_config.py::test_load_relative_paths[*]`
- `tests/unit/test_config.py::test_resolve[*]` 与 `test_resolve_homedir`

`PASS_TO_PASS`: `36` 条。

所以这题并不只是 `~/cache` 处理，而是 config path resolution + config merge 的组合修复。

### 2.2 runner-level user query

完整 prompt 就是这三条 release note + `13` 条 config tests。关键在于它同时给出了：

- `resolve: handle ~ home dir`
- `use local config from local_dvc_dir`
- `fetch: merge config instead of updating`

这本来已经在提示“不是单一 `expanduser` hotfix”。

### 2.3 trace-level agent goals

- `innercc`
  - 很快把任务重写成：
    - `_load_paths` 里要处理 `~`
  - 没继续覆盖 `Config._resolve()`、`local_dvc_dir`、`repo.config.merge()`
- `claude-code`
  - 更糟，最后没有形成有效 patch artifact
  - `cli_result.json` 只留下了一段不完整的 tool-call 结果

### 2.4 official golden answer

官方 patch 的核心其实是 4 组联动变更：

1. `dvc/config.py`
   - 引入 `Config._resolve(conf_dir, path)`
   - 在 `_resolve()` 中同时处理：
     - URL
     - absolute path
     - `~` home dir
     - relative path
2. `dvc/config_schema.py`
   - 新增 `ExpPath`
3. `dvc/repo/__init__.py`
   - `Config(..., local_dvc_dir=self.local_dvc_dir, ...)`
4. `dvc/repo/fetch.py`
   - `repo.config.update(config)` -> `repo.config.merge(config)`

而 `innercc` 只命中了其中最表面的第一条里的一个分支。

## 3. Outcome Comparison

| CLI | resolved | F2P | P2P | cli_duration_ms | cli_num_turns | tool_use_count | tool_error_count |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `innercc` | `false` | `0/13` | `36/36` | `192153` | `32` | `31` | `0` |
| `claude-code` | `false` | `0/13` | `36/36` | `318841` | `52` | `93` | `18` |

## 4. Artifact Index

### innercc

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_3.13.3_3.14.0/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_3.13.3_3.14.0/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_3.13.3_3.14.0/cli_result.json)
- [cli_stdout.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_3.13.3_3.14.0/cli_stdout.log)
- [cli_stderr.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_3.13.3_3.14.0/cli_stderr.log)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_3.13.3_3.14.0/router_trace_bundle.json)
- [eval_worker_log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/eval_worker_logs/iterative__dvc_3.13.3_3.14.0.log)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_3.13.3_3.14.0/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_3.13.3_3.14.0/test_output.txt)
- [run_instance.log](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_3.13.3_3.14.0/run_instance.log)

### claude-code

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_3.13.3_3.14.0/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_3.13.3_3.14.0/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_3.13.3_3.14.0/cli_result.json)
- [cli_stdout.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_3.13.3_3.14.0/cli_stdout.log)
- [cli_stderr.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_3.13.3_3.14.0/cli_stderr.log)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_3.13.3_3.14.0/router_trace_bundle.json)
- [eval_worker_log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/eval_worker_logs/iterative__dvc_3.13.3_3.14.0.log)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_3.13.3_3.14.0/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_3.13.3_3.14.0/test_output.txt)
- [run_instance.log](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_3.13.3_3.14.0/run_instance.log)

## 5. Chronological Trace Reconstruction

### 5.1 innercc

#### Phase A: config-only narrowing (`step 1-10`)

- 关键动作：
  - 读 `dvc/config.py`
  - 读 `tests/func/test_config.py`
  - 读 `tests/unit/test_config.py`
- 阶段结论：
  - 很快把问题压成 `_load_paths()` 的 resolve 行为

#### Phase B: `~` fixation (`step 21-28`)

- 关键文本：
  - 明确写出 “bug is clear ... `~/cache` would be joined as `/conf_dir/~/some/path`”
- 问题：
  - 这只覆盖了 `test_resolve_homedir` 的一个子情形
  - 没覆盖官方 patch 的 `_resolve()` 统一抽象和 fetch config merge

#### Phase C: single-file patch (`step 23`)

- 修改文件：
  - `dvc/config.py`
- 修改内容：
  - 给 `_load_paths` 里的局部 `resolve` 增加 `expanduser` 分支

### 5.2 claude-code

#### Phase A: similar narrowing, weaker execution (`step 2-20`)

- 关键动作：
  - 读 config tests
  - 跑 exact tests
- 阶段结论：
  - 也把任务压成了 path resolution

#### Phase B: no effective artifact (`step 20-52`)

- 关键现象：
  - `patch.diff` 为空
  - `cli_result.json` 最终 `result` 几乎只是一段未完成的 tool-call 输出
- 阶段结论：
  - 即使它可能在会话中形成过局部想法，也没有落成有效 patch artifact

## 6. Hypothesis Iteration Log

| CLI | step_range | hypothesis | evidence_used | why_it_seemed_plausible | why_it_was_correct_or_wrong |
| --- | --- | --- | --- | --- | --- |
| `innercc` | `1-28` | 问题主要是 `_load_paths` 不会展开 `~` | unit/func config tests、`dvc/config.py` | release note 第一条非常显眼 | 只对了一小部分，漏掉 `_resolve()` / `local_dvc_dir` / `merge()` 主体 |
| `claude-code` | `2-52` | 也是 path resolution 小修 | 同上 | 看起来像最小修复 | 错，而且最终没有形成 patch |

## 7. Patch And Code-Level Analysis

### 7.1 innercc

- patch：

```diff
+            if path.startswith("~"):
+                path = os.path.expanduser(path)
+                if os.path.isabs(path):
+                    return path
```

- 命中：
  - `~` 展开这一小点
- 漏掉：
  - `Config._resolve()`
  - `ExpPath`
  - `local_dvc_dir`
  - `repo.config.merge()`

### 7.2 claude-code

- 关键事实：
  - [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_3.13.3_3.14.0/patch.diff) 大小为 `0`
- 这意味着：
  - 评测时几乎等同于没有有效修复提交

## 8. Evaluation And Failure Evidence

来自 [innercc test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_3.13.3_3.14.0/test_output.txt) 的直接证据：

```text
E       AssertionError: assert '/tmp/.../.dvc/../file.txt' == '/tmp/.../file.txt'
```

以及：

```text
FAILED tests/unit/test_config.py::test_resolve[cache-/testbed/conf_dir/cache]
FAILED tests/unit/test_config.py::test_resolve_homedir
```

这说明它不只是 `~` 没全修，而是根本没有引入官方的 `_resolve()` 抽象。

对 `claude-code` 来说，决定性证据更简单：

- `13/13` F2P 全挂
- `patch.diff` 为空

## 9. Root Cause

- `direct_root_cause`
  - 两边都把三条 release-note 组合任务缩成了单点 `~` 展开问题。
  - `claude-code` 甚至没有把想法落成 patch artifact。
- `contributing_factors`
  - 没有用官方 patch 文件分布来对冲任务理解偏差。
  - 没有对 `test_load_relative_paths` 与 `test_resolve` 的整体簇做语义归纳。
- `non_root_but_misleading_signals`
  - `~/cache` 是最容易肉眼看见的问题，但不是全部。

## 10. CLI Optimization Opportunities

1. release note 同时出现多个 config 层修复时，必须先对照官方 patch 的文件集合，而不是只抓最容易描述的那一条。验证方式是 trace 中必须出现“为什么只改 `config.py` 足够/不够”的显式论证。
2. 空 patch artifact 必须作为高优先级异常信号记录，不应被“会话里似乎想到了什么”掩盖。验证方式是结束前检查 `git diff` 是否非空且覆盖目标文件。
3. 对路径解析类 case，应优先提炼一个统一 resolver，而不是在旧局部 helper 里打补丁。官方 `_resolve()` 正是这类抽象升级的典型。
