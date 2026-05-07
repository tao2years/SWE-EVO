# iterative__dvc_3.12.0_3.13.0 Analysis

本文遵循 [bad_case_analysis_design.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/bad_case_analysis_design.md) 的统一结构。

## 1. Case Metadata

- `instance_id`: `iterative__dvc_3.12.0_3.13.0`
- `repo`: `iterative/dvc`
- `innercc_run`: `20260427-154634`
- `claude_code_run`: `20260429-114027`
- `comparison_category`: `inner_only`
- 一句话结论：
  这题表面上是 release note bundle，实际上 benchmark 只关心两簇能力：Hydra `config_module` / `compose_and_dump()` 新签名，以及 experiments utils 里的 `gen_random_name()` 抽取。`innercc` 很快通过 git diff 把这两簇一起命中，`33/33` 全过；`claude-code` 则把 experiments 线误缩成 `check_ref_format()`，把 hydra 线误改成 `OmegaConf.resolve()` 的缩进位置，结果两簇都完全没修到，`0/33`。
- 根因标签：
  - `task_understanding_error`
  - `hypothesis_lock_in`
  - `validation_gap`

## 2. Task And Gold Spec

### 2.1 benchmark task

`problem_statement`:

```text
## What's Changed
### 🚀 New Features and Enhancements
* Feature/hydra config modules by @d-miketa in https://github.com/iterative/dvc/pull/9783
* fetch: add basic onerror by @efiop in https://github.com/iterative/dvc/pull/9810
### Other Changes
* exp: abstract random name gen from repo by @dberenbaum in https://github.com/iterative/dvc/pull/9806
* deps: bump dvc-data to 2.12.0 by @efiop in https://github.com/iterative/dvc/pull/9809
```

`FAIL_TO_PASS`: `33` 条，全部集中在两组测试：

- `tests/func/utils/test_hydra.py::*`
- `tests/unit/repo/experiments/test_utils.py::*`

`PASS_TO_PASS`: `44` 条。

这题的真实任务边界很明确：

1. `dvc.utils.hydra.compose_and_dump()` 需要支持：
   - `config_dir`
   - `config_module`
   - 二者至少一个存在
2. experiments utils 需要新增：
   - `gen_random_name()`
   - 并让 `get_random_exp_name()` 调用它

### 2.2 runner-level user query

```text
You are working inside a git repository checked out to the benchmark base commit.

Implement the minimal code-only fix for this software evolution task.

SWE-EVO Instance ID: iterative__dvc_3.12.0_3.13.0

Release note / requirement:
<!-- Release notes generated using configuration in .github/release.yml at 3.13.0 -->

## What's Changed
### 🚀 New Features and Enhancements
* Feature/hydra config modules by @d-miketa in https://github.com/iterative/dvc/pull/9783
* fetch: add basic onerror by @efiop in https://github.com/iterative/dvc/pull/9810
### Other Changes
* exp: abstract random name gen from repo by @dberenbaum in https://github.com/iterative/dvc/pull/9806
* deps: bump dvc-data to 2.12.0 by @efiop in https://github.com/iterative/dvc/pull/9809

Expected failing tests that should pass after your fix:
- tests/func/utils/test_hydra.py::...
- tests/unit/repo/experiments/test_utils.py::...

Rules:
- Modify only non-test source files.
- Do not edit tests, fixtures, docs, changelog files, or version metadata files unless absolutely required.
- Prefer a minimal fix over broad refactors.
- You may inspect and run commands in the repository.
- When you are done, just finish normally. The patch will be collected from git diff.
```

这里虽然 prompt 很长，但 F2P 实际只覆盖 Hydra 与 experiments 两簇。

### 2.3 trace-level agent goals

- `innercc`
  - 很早就把任务压成：
    - `dvc/utils/hydra.py`
    - `dvc/repo/experiments/utils.py`
  - 还直接通过 tag diff / `git show 3.13.0:...` 去抓官方变更
- `claude-code`
  - 同时读了 hydra tests 和 experiments tests
  - 但后续把 experiments 线收缩成了 `check_ref_format()` 的字符串格式问题
  - 把 hydra 线收缩成 `OmegaConf.resolve()` 的位置问题

### 2.4 official golden answer

官方 patch 的真正核心有两组。

#### Golden fix A: Hydra 新增 `config_module`

```diff
diff --git a/dvc/utils/hydra.py b/dvc/utils/hydra.py
@@
-def compose_and_dump(output_file: "StrPath", config_dir: str, config_name: str, overrides: List[str]) -> None:
+def compose_and_dump(
+    output_file: "StrPath",
+    config_dir: Optional[str],
+    config_module: Optional[str],
+    config_name: str,
+    overrides: List[str],
+) -> None:
@@
-    from hydra import compose, initialize_config_dir
+    from hydra import compose, initialize_config_dir, initialize_config_module
@@
+    config_source = config_dir or config_module
+    if not config_source:
+        raise ValueError("Either `config_dir` or `config_module` should be provided.")
+    initialize_config = initialize_config_dir if config_dir else initialize_config_module
+    with initialize_config(config_source, version_base=None):
```

#### Golden fix B: 抽出 `gen_random_name()`

```diff
diff --git a/dvc/repo/experiments/utils.py b/dvc/repo/experiments/utils.py
@@
-def get_random_exp_name(scm, baseline_rev):
+def gen_random_name():
@@
+    adjective = random_generator.choice(ADJECTIVES)
+    noun = random_generator.choice(NOUNS)
+    return f"{adjective}-{noun}"
+
+def get_random_exp_name(scm, baseline_rev):
@@
-        adjective = random_generator.choice(ADJECTIVES)
-        noun = random_generator.choice(NOUNS)
-        name = f"{adjective}-{noun}"
+        name = gen_random_name()
```

注意：

- official patch 还改了 `config_schema.py`
- 但当前 benchmark 的 33 条 F2P 并不依赖这部分 schema 校验

## 3. Outcome Comparison

| CLI | resolved | F2P | P2P | cli_duration_ms | cli_num_turns | tool_use_count | tool_error_count |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| `innercc` | `true` | `33/33` | `44/44` | `319982` | `45` | `44` | `0` |
| `claude-code` | `false` | `0/33` | `44/44` | `966061` | `92` | `91` | `6` |

这是一个非常强的对照：

- `innercc` 命中两簇核心，且没有任何 P2P 回归
- `claude-code` 完全没命中 F2P 主体，但也没引入额外 P2P 回归
- 说明 `claude-code` 的问题不是“写坏系统”，而是“任务理解完全跑偏”

## 4. Artifact Index

### innercc

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_3.12.0_3.13.0/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_3.12.0_3.13.0/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_3.12.0_3.13.0/cli_result.json)
- [cli_stdout.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_3.12.0_3.13.0/cli_stdout.log)
- [cli_stderr.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_3.12.0_3.13.0/cli_stderr.log)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_3.12.0_3.13.0/router_trace_bundle.json)
- [eval_worker_log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/eval_worker_logs/iterative__dvc_3.12.0_3.13.0.log)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_3.12.0_3.13.0/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_3.12.0_3.13.0/test_output.txt)
- [run_instance.log](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_3.12.0_3.13.0/run_instance.log)

### claude-code

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_3.12.0_3.13.0/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_3.12.0_3.13.0/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_3.12.0_3.13.0/cli_result.json)
- [cli_stdout.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_3.12.0_3.13.0/cli_stdout.log)
- [cli_stderr.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_3.12.0_3.13.0/cli_stderr.log)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_3.12.0_3.13.0/router_trace_bundle.json)
- [eval_worker_log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/eval_worker_logs/iterative__dvc_3.12.0_3.13.0.log)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_3.12.0_3.13.0/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_3.12.0_3.13.0/test_output.txt)
- [run_instance.log](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_3.12.0_3.13.0/run_instance.log)

## 5. Chronological Trace Reconstruction

### 5.1 innercc

#### Phase A: release-to-tests alignment (`step 1-16`)

- 关键动作：
  - 看 tag diff 与 `git show 3.13.0:...`
  - 读 `tests/func/utils/test_hydra.py`
  - 读 `tests/unit/repo/experiments/test_utils.py`
  - 读 `dvc/utils/hydra.py`
  - 读 `dvc/repo/experiments/utils.py`
- 阶段结论：
  - 很快确认 benchmark 真正关心的是 Hydra config module + random name helper

#### Phase B: official patch reconstruction (`step 17-30`)

- 关键动作：
  - 直接用 git tag / release diff 回查 `3.13.0`
  - 读 `git show 3.13.0:dvc/utils/hydra.py`
  - 读 `git show 3.13.0:dvc/repo/experiments/utils.py`
- 阶段结论：
  - 这一步几乎直接把 official patch 的关键 hunk 抓出来了

#### Phase C: narrow code editing (`step 31-33`)

- 修改文件：
  - `dvc/utils/hydra.py`
  - `dvc/repo/experiments/utils.py`
- 阶段产出：
  - `compose_and_dump()` 新增 `config_module`
  - 新增 `gen_random_name()` 并让 `get_random_exp_name()` 调用它

#### Phase D: diff verification (`step 34-36`)

- 关键动作：
  - 回读两个文件
  - `git diff --no-color`
- 阶段结论：
  - 它明确确认“改动等于 3.13.0 的核心变更”

### 5.2 claude-code

#### Phase A: broad exploration (`step 2-16`)

- 关键动作：
  - 读 hydra tests 与 experiments tests
  - grep `gen_random_name`
  - 读 `dvc/utils/hydra.py` 与 `dvc/repo/experiments/utils.py`
- 问题：
  - 虽然拿到了正确输入，但没有把两簇 failing tests 绑定到 release note 对应的两个核心 hunk

#### Phase B: wrong-target localization (`step 17-50`)

- experiments 线：
  - 锁到了 `check_ref_format()` 的字符串处理
  - 实际 tests 直接因为 `ImportError: cannot import name 'gen_random_name'` 失败
- hydra 线：
  - 锁到了 `OmegaConf.resolve()` 的位置
  - 实际 tests 是 `compose_and_dump()` 签名仍然只有 4 个参数

#### Phase C: code editing (`step 50-63`)

- 修改文件：
  - `dvc/repo/experiments/utils.py`
  - `dvc/utils/hydra.py`
- 修改内容：
  - `check_ref_format()` 的局部变量命名与字符串逻辑
  - 把 `OmegaConf.resolve(cfg)` 移到 `initialize_config_dir()` 块内
- 结果：
  - 都不是 benchmark target

#### Phase D: prolonged validation on wrong hypothesis (`step 84-91`)

- 关键动作：
  - 继续用 snippets 验证 `check_ref_format()`
  - `git diff`
- 阶段结论：
  - 即使失败证据已经指向 `gen_random_name` 与 `compose_and_dump` 签名，它仍围绕错误假设收口

## 6. Hypothesis Iteration Log

| CLI | step_range | hypothesis | evidence_used | why_it_seemed_plausible | why_it_was_correct_or_wrong |
| --- | --- | --- | --- | --- | --- |
| `innercc` | `1-16` | benchmark 实际只关心 hydra + experiments 两簇 | tests 分布、release note、源码文件 | 33 条 F2P 全落在这两组测试 | 正确 |
| `innercc` | `17-30` | 直接对齐 3.13.0 的对应 hunk 就能解题 | git show / tag diff | release note 与 tag diff 完全一致 | 正确 |
| `claude-code` | `17-35` | experiments 线的问题在 `check_ref_format()` | test_utils 文件阅读 | 该函数确实被多条 tests 涉及 | 错误，tests 先死在 `gen_random_name` 缺失 |
| `claude-code` | `36-50` | hydra 线的问题在 `OmegaConf.resolve()` 的位置 | `compose_and_dump` 阅读 | 这是函数里明显可见的一个行为点 | 错误，真实问题是函数签名和 `config_module` 初始化模式 |

## 7. Patch And Code-Level Analysis

### 7.1 innercc

- 命中文件：
  - `dvc/utils/hydra.py`
  - `dvc/repo/experiments/utils.py`
- 与 official patch 的关系：
  - 直接命中了 benchmark 真正用到的两组 hunk
- 特点：
  - patch 非常窄
  - 没有碰无关的 fetch/onerror 或 dvc-data bump

### 7.2 claude-code

- 命中文件也只有两处：
  - `dvc/utils/hydra.py`
  - `dvc/repo/experiments/utils.py`
- 但命中内容完全错了：
  - 没有新增 `config_module`
  - 没有新增 `gen_random_name()`
- 这不是“差一点”，而是“命中了同名文件，但修错了行为簇”

## 8. Evaluation And Failure Evidence

来自 [claude-code test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_3.12.0_3.13.0/test_output.txt) 的两条决定性证据：

experiments 线直接在导入期失败：

```text
E   ImportError: cannot import name 'gen_random_name' from 'dvc.repo.experiments.utils'
```

hydra 线直接在调用签名上失败：

```text
E       TypeError: compose_and_dump() takes 4 positional arguments but 5 were given
```

这两条已经足够说明：

- 它没有修到 benchmark 主体
- 后续所有 `check_ref_format` 或 `OmegaConf.resolve` 相关验证都属于偏航

相反，`innercc` 的 [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_3.12.0_3.13.0/report.json) 显示：

- `FAIL_TO_PASS = 33/33`
- `PASS_TO_PASS = 44/44`

## 9. Root Cause

- `direct_root_cause`
  - `claude-code` 的直接根因是 task understanding 错误：面对一个两簇明确的 release note case，它没有让 F2P 主导任务边界，而是被文件内其他看起来“也可能相关”的局部逻辑带偏。
- `contributing_factors`
  - 没有用最直接的 failure evidence 收口：
    - `ImportError: gen_random_name`
    - `TypeError: compose_and_dump(... 5 args ...)`
  - trace 中缺少基于 release tag / official diff 的回查动作。
- `non_root_but_misleading_signals`
  - `check_ref_format()` 与 `OmegaConf.resolve()` 都位于失败模块内，所以表面上很像合理切入点。
  - 但它们不是这次新增测试真正覆盖的变化点。

## 10. CLI Optimization Opportunities

1. 当 F2P 里直接出现 `ImportError` 与 `TypeError(signature mismatch)` 时，应优先把它们当作一级根因，而不是继续搜索相邻逻辑。适用于新增 helper、函数签名扩展、导出 API 变化等 case。验证方式是看 agent 是否在计划里把“缺少符号 / 参数个数不匹配”显式列为优先修复项。
2. 对 release-note case，如果 tests 明确只覆盖两个文件簇，应当先做 “tests-to-release-hunk” 对齐，再展开局部探索。`innercc` 这题通过 tag diff 直接拿到关键 hunk，是值得固化的策略。验证方式是检查 trace 前半段是否出现 tag diff / git show 之类的 ground-truth 对齐动作。
3. 命中文件不等于命中任务。这个 case 两边都改了同样两个文件，但只有一边命中了真正的行为簇。适用于大型模块文件里存在多个相邻 feature/fix 的情况。验证方式是要求 patch 说明必须能对应到失败断言或 test patch 新增断言，而不是只对应到“这个文件里某段看起来相关的代码”。
