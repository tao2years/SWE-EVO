# iterative__dvc_1.0.0b6_1.0.0 Analysis

本文遵循 [bad_case_analysis_design.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/bad_case_analysis_design.md) 的统一结构。

## 1. Case Metadata

- `instance_id`: `iterative__dvc_1.0.0b6_1.0.0`
- `repo`: `iterative/dvc`
- `innercc_run`: `20260427-154634`
- `claude_code_run`: `20260429-114027`
- `comparison_category`: `claude_only`
- 一句话结论：
  `innercc` 把 CLI 层参数语义映射成了 repo 层已有的 `dry` 参数，形成了“内部实现看起来合理、但对外测试契约不匹配”的错误修复；`claude-code` 则直接顺着单测契约把 repo API 也改成了 `no_exec`，因此通过了目标测试。
- 根因标签：
  - `task_understanding_error`
  - `localization_error`
  - `hypothesis_lock_in`
  - `validation_gap`

## 2. Task And Gold Spec

### 2.1 benchmark task

`problem_statement`:

```text
* completion: misc fixes (#4076) @casperdcl
* add --no-exec mode to import url (#4075) @karajan1001
```

`FAIL_TO_PASS`:

- `tests/unit/command/test_imp_url.py::test_import_url`
- `tests/unit/command/test_imp_url.py::test_import_url_no_exec`

`PASS_TO_PASS`: `2` 条

- `tests/func/test_import_url.py::TestCmdImport::test_unsupported`
- `tests/unit/command/test_imp_url.py::test_failed_import_url`

这个 case 的任务很短，但约束非常明确：

- `import-url` 命令需要增加 `--no-exec`
- 不只是 CLI parser 能识别这个 flag
- 下游调用链也必须维持 `no_exec` 这一套参数语义，满足单测断言

### 2.2 runner-level user query

两个 CLI 实际收到的 prompt 为：

```text
You are working inside a git repository checked out to the benchmark base commit.

Implement the minimal code-only fix for this software evolution task.

SWE-EVO Instance ID: iterative__dvc_1.0.0b6_1.0.0

Release note / requirement:
* completion: misc fixes (#4076) @casperdcl
* add --no-exec mode to import url (#4075) @karajan1001

Expected failing tests that should pass after your fix:
- tests/unit/command/test_imp_url.py::test_import_url
- tests/unit/command/test_imp_url.py::test_import_url_no_exec

Rules:
- Modify only non-test source files.
- Do not edit tests, fixtures, docs, changelog files, or version metadata files unless absolutely required.
- Prefer a minimal fix over broad refactors.
- You may inspect and run commands in the repository.
- When you are done, just finish normally. The patch will be collected from git diff.
```

### 2.3 trace-level agent goals

两个 CLI 在 trace 中都把任务重写成了“给 import-url 增加 no-exec 支持”，但中间的理解路径不同。

- `innercc`
  - 在 `step 17` 明确写出内部目标：
    - 添加 `--no-exec` 参数
    - 把 `no_exec` 转换成 `dry`
    - 给 `repo.imp_url()` 增加 `dry` 参数并传给 `stage.run()`
  - 也就是说，它把外部契约翻译成了内部已有语义

- `claude-code`
  - 在 `step 26` 前后把任务表述为：
    - 为 `import-url` 增加 `--no-exec`
    - 让 command 层和 repo 层都沿用 `no_exec`
  - 它的目标更贴近测试名字和 mock 断言文本

### 2.4 official golden answer

benchmark 的 `patch` 里，真正和行为修复相关的关键 hunk 是：

```diff
diff --git a/dvc/command/imp_url.py b/dvc/command/imp_url.py
@@
-                self.args.url, out=self.args.out, fname=self.args.file
+                self.args.url, out=self.args.out, fname=self.args.file,
+                no_exec=self.args.no_exec

@@
+    import_parser.add_argument(
+        "--no-exec",
+        action="store_true",
+        help="Do not execute the download, only create the dvc file.",
+    )
```

```diff
diff --git a/dvc/repo/imp_url.py b/dvc/repo/imp_url.py
@@
-def imp_url(self, url, out=None, fname=None, erepo=None, frozen=True):
+def imp_url(self, url, out=None, fname=None, erepo=None, frozen=True, no_exec=False):
@@
-    stage.run()
+    if no_exec:
+        stage.ignore_outs()
+    else:
+        stage.run()
```

官方 golden test patch 关键 hunk 是：

```diff
diff --git a/tests/unit/command/test_imp_url.py b/tests/unit/command/test_imp_url.py
@@
-    m.assert_called_once_with("src", out="out", fname="file")
+    m.assert_called_once_with("src", out="out", fname="file", no_exec=False)
@@
+def test_import_url_no_exec(mocker):
+    ...
+    m.assert_called_once_with("src", out="out", fname="file", no_exec=True)
```

因此官方 gold spec 的关键不只是“实现 no-exec 效果”，而是：

1. CLI 层 mock 断言必须看到 `no_exec`
2. repo 层公开接口也必须接受 `no_exec`
3. `no_exec` 的行为是“创建 dvc file 但不执行下载”

## 3. Outcome Comparison

| CLI | resolved | F2P | P2P | cli_duration_ms | cli_num_turns | tool_use_count | tool_error_count | patch_apply |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| `innercc` | `false` | `0/2` | `2/2` | `280284` | `53` | `52` | `7` | `true` |
| `claude-code` | `true` | `2/2` | `2/2` | `740103` | `52` | `51` | `15` | `true` |

这个 case 的特点很清楚：

- `innercc` 没有引入额外回归，`PASS_TO_PASS = 2/2`
- 但目标测试一个都没过，说明是“修错方向”而不是“改坏系统”
- `claude-code` 则完整命中目标契约

## 4. Artifact Index

### innercc

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_1.0.0b6_1.0.0/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_1.0.0b6_1.0.0/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_1.0.0b6_1.0.0/cli_result.json)
- [cli_stdout.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_1.0.0b6_1.0.0/cli_stdout.log)
- [cli_stderr.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_1.0.0b6_1.0.0/cli_stderr.log)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_1.0.0b6_1.0.0/router_trace_bundle.json)
- [eval worker log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/eval_worker_logs/iterative__dvc_1.0.0b6_1.0.0.log)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_1.0.0b6_1.0.0/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_1.0.0b6_1.0.0/test_output.txt)
- [run_instance.log](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_1.0.0b6_1.0.0/run_instance.log)

### claude-code

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_1.0.0b6_1.0.0/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_1.0.0b6_1.0.0/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_1.0.0b6_1.0.0/cli_result.json)
- [cli_stdout.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_1.0.0b6_1.0.0/cli_stdout.log)
- [cli_stderr.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_1.0.0b6_1.0.0/cli_stderr.log)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_1.0.0b6_1.0.0/router_trace_bundle.json)
- [eval worker log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/eval_worker_logs/iterative__dvc_1.0.0b6_1.0.0.log)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_1.0.0b6_1.0.0/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_1.0.0b6_1.0.0/test_output.txt)
- [run_instance.log](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_1.0.0b6_1.0.0/run_instance.log)

## 5. Chronological Trace Reconstruction

### 5.1 innercc

#### Phase A: bootstrap + repo exploration (`step 1-16`)

- 关键动作：
  - 读 `tests/unit/command/test_imp_url.py`
  - 读 `dvc/command/imp_url.py`
  - grep `no_exec` / `no-exec`
  - 读 `dvc/repo/imp_url.py`
  - 读 `dvc/stage/__init__.py` 与 `dvc/stage/imports.py`
- 阶段目标：
  - 找到 `import-url` 的命令层、repo 层、stage 执行层是如何串起来的
- 阶段结论：
  - `stage.run(dry=...)` 看起来像现成语义，于是开始把 `no_exec` 映射成 `dry`

#### Phase B: task planning + implementation hypothesis (`step 17`)

- 关键文本：
  - “I need to add `--no-exec` ... pass `no_exec` as `dry` ... add `dry` parameter ... pass it to `stage.run()`”
- 阶段结论：
  - 这里已经形成了错误核心假设：
    - 认为对外新增的 `no_exec` 最终应该转译成 repo 层 `dry`

#### Phase C: code editing (`step 18-21`)

- 关键动作：
  - 编辑 `dvc/repo/imp_url.py`
  - 编辑 `dvc/command/imp_url.py`
- 修改结果：
  - command 层把 `no_exec` 条件性展开成 `dry`
  - repo 层新增 `dry=False`
  - `stage.run(dry=dry)`

#### Phase D: validation drift (`step 22-49`)

- 关键动作：
  - 读 unit tests
  - 多次尝试运行 pytest
  - 反复装依赖、绕过 fixture、mock 手工复现
  - 多次 `git diff`
- 关键问题：
  - 它其实已经看到了单测期望是：
    - `imp_url(..., no_exec=False)`
    - `imp_url(..., no_exec=True)`
  - 但没有把这条契约提升成高优先级约束，而是继续围绕 `dry` 方向验证

#### Phase E: termination (`step 50`)

- 关键动作：
  - 输出修复总结
- 结果：
  - 在局部实现自洽的前提下结束，但和单测 mock 契约不一致

### 5.2 claude-code

#### Phase A: bootstrap + repo exploration (`step 1-25`)

- 关键动作：
  - 读 `tests/unit/command/test_imp_url.py`
  - `cat dvc/command/imp_url.py`
  - `cat dvc/repo/imp_url.py`
  - 参考 `run` 命令的现有参数模式
- 阶段目标：
  - 理解 `--no-exec` 需要贯穿哪些层

#### Phase B: task planning (`step 23-26`)

- 关键文本：
  - “I need to add `--no-exec` support to `import-url` command, similar to how it works in `run`”
- 阶段结论：
  - 形成的任务拆解更接近测试约束：
    - parser 支持 `--no-exec`
    - command 层向 repo 层传 `no_exec`
    - repo 层真正实现 `no_exec`

#### Phase C: code editing (`step 26-35`)

- 关键动作：
  - 反复编辑 `dvc/command/imp_url.py`
  - 重写 `dvc/repo/imp_url.py`
- 修改结果：
  - repo API 直接改成 `no_exec=False`
  - command 层 mock 断言需要的参数形状得以保留

#### Phase D: noisy validation (`step 36-50`)

- 关键动作：
  - 多次运行 pytest
  - 绕过 fixture 直接执行局部 Python 检查
  - `git diff --stat`
- 噪声：
  - evaluator 环境里存在很多和 `fractions.gcd` 相关的功能测试噪声
- 但关键区别是：
  - 它最终保住了目标单测契约，因此 F2P 通过

#### Phase E: termination (`step 51-52`)

- 关键动作：
  - 输出最终变更摘要

## 6. Hypothesis Iteration Log

### 6.1 innercc

| step_range | hypothesis | evidence_used | why_it_seemed_plausible | why_it_was_correct_or_wrong |
| --- | --- | --- | --- | --- |
| `1-16` | `--no-exec` 最终应映射到 stage 层已有的 `dry` 语义 | `dvc/stage/__init__.py`、`stage.run(dry=...)`、`dvc/repo/imp_url.py` | 内部实现确实已经有 `dry` 这一套语义，看起来像最小复用路径 | 错。测试契约要求 repo 层公开接口就是 `no_exec` |
| `17-21` | 只要 command 层把 `no_exec` 条件性转成 `dry`，整体就完成了 | command 层与 repo 层局部代码 | 这是最直接的“少改内部逻辑”方案 | 错。unit mock 明确断言调用形状是 `no_exec=...` |
| `22-49` | 局部 mock 和依赖绕过验证足以证明 patch 正确 | 手工 mock、pytest、`git diff` | 局部实现逻辑自洽 | 错。它没有把单测断言里“参数名必须叫 no_exec”当成核心事实 |

### 6.2 claude-code

| step_range | hypothesis | evidence_used | why_it_seemed_plausible | why_it_was_correct_or_wrong |
| --- | --- | --- | --- | --- |
| `1-25` | `--no-exec` 需要从 parser 一路传到 repo 层 | unit test 文件、command 层、repo 层 | failing tests 全在 command/unit 层，契约边界很明确 | 正确 |
| `26-35` | repo 层公开签名也应使用 `no_exec`，而不是内部别名 | mock 断言文本、repo 代码 | 单测已经把参数名写死成 `no_exec` | 正确 |
| `36-50` | 功能层环境噪声不影响目标 F2P 判断 | pytest 输出、局部 Python 验证 | 目标单测都通过，额外失败是环境兼容噪声 | 对 benchmark resolved 判定来说是正确的 |

## 7. Patch And Code-Level Analysis

### 7.1 innercc patch

`innercc` 的 patch 逻辑上“实现了 no-exec 效果”，但接口层错了：

```diff
+                **({"dry": self.args.no_exec} if self.args.no_exec else {}),
...
+def imp_url(..., dry=False):
...
+    stage.run(dry=dry)
```

问题不在行为本身，而在：

- command mock 期望的是 `no_exec`
- 它实际发出去的是 `dry=True`
- 默认路径甚至连 `no_exec=False` 也没显式传

这导致两个目标单测都失败：

- `Expected: imp_url(..., no_exec=False)` / `Actual: imp_url(... )`
- `Expected: imp_url(..., no_exec=True)` / `Actual: imp_url(..., dry=True)`

### 7.2 claude-code patch

`claude-code` 的 patch 更贴测试契约：

```diff
+                self.args.url, out=self.args.out, fname=self.args.file,
+                no_exec=self.args.no_exec
...
+def imp_url(..., no_exec=False):
...
+    if no_exec:
+        stage.ignore_outs()
+    else:
+        stage.run()
```

它不去做参数名翻译，而是直接把 repo 层 API 也改成 `no_exec`。

## 8. Evaluation And Failure Evidence

### 8.1 innercc: 这是“修错接口契约”

最关键的失败证据不是功能层大 traceback，而是 unit test 的 mock 断言：

```text
Expected: imp_url('src', out='out', fname='file', no_exec=False)
Actual:   imp_url('src', out='out', fname='file')
```

以及：

```text
Expected: imp_url('src', out='out', fname='file', no_exec=True)
Actual:   imp_url('src', out='out', fname='file', dry=True)
```

这说明：

- `innercc` 把任务理解成“实现 no-exec 行为”
- 但 benchmark 真正检查的是“公开接口契约 + 行为”

### 8.2 claude-code: 这是“命中契约层”

`claude-code` 的 evaluator 输出里虽然仍有大量函数测试噪声，但目标单测状态是：

- `FAIL_TO_PASS = 2/2`
- `PASS_TO_PASS = 2/2`
- `resolved = true`

说明它命中的关键不是更深的内部逻辑，而是测试真正关心的接口层语义。

### 8.3 misleading evaluator noise

两个 run 的 `test_output.txt` 都出现了很多与 `fractions.gcd` 相关的功能测试失败，例如：

```text
ERROR: unexpected error - cannot import name 'gcd' from 'fractions'
```

但 benchmark `report.json` 只按指定的 F2P / P2P 列表计算 resolved，所以这些噪声不是本 case 的直接根因，不能误判成 patch 失败主因。

## 9. Root Cause

### 9.1 direct root cause

- `task_understanding_error`
  - `innercc` 把任务理解成“复用内部 dry 语义”，而不是“满足 no_exec 的公开接口契约”

- `localization_error`
  - 它定位到了相关模块，但修错了抽象边界：
    - 修在内部参数翻译
    - 而不是修在 command -> repo 的契约一致性

### 9.2 contributing factors

- `hypothesis_lock_in`
  - 一旦形成“no_exec 只是 dry 的别名”假设，后续验证都围绕这个方向展开

- `validation_gap`
  - 它看过单测文件，但没有把 mock 的 `assert_called_once_with(..., no_exec=...)` 当成最高优先级真相

### 9.3 non-root but misleading signals

- `stage.run(dry=...)` 的存在很容易让人误以为这是正确最小实现
- 功能层的大量环境噪声也可能掩盖掉“unit contract 才是这题的决定性证据”这一点

## 10. CLI Optimization Opportunities

### 10.1 case-specific actions

1. 当 failing tests 是 mock/assert_called_once_with 这类契约测试时，优先满足被断言的调用形状，不要先做内部语义翻译。
2. 如果单测显式写死参数名，结束前必须逐字对照 patch 后的真实调用形状。

### 10.2 generalizable actions

1. 增加“测试类型识别”策略：
   - 如果 failing tests 是 command/unit mock tests，优先检查接口契约而不是深层业务行为。
2. 增加“断言优先级”规则：
   - `assert_called_once_with(...)` 的文本应高于内部实现已有语义的吸引力。
3. 增加“接口别名风险”检查：
   - 当 agent 想把外部新参数映射成内部旧参数时，需要先验证测试是否允许这种抽象折叠。

### 10.3 validation plan for the optimization

1. 针对 command/unit mock 类 case，要求 agent 在结束前输出“最终调用签名对照表”，再回放此 case。
2. 加入规则：若失败测试包含 `assert_called_once_with`，则必须重读断言并解释 patch 如何满足它。
3. 回放此 case，验证 `innercc` 是否还能走向 `dry=` 这条错误路径。
