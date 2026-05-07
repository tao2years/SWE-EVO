# iterative__dvc_0.52.1_0.53.1 Analysis

本文遵循 [bad_case_analysis_design.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/bad_case_analysis_design.md) 的统一结构。

## 1. Case Metadata

- `instance_id`: `iterative__dvc_0.52.1_0.53.1`
- `repo`: `iterative/dvc`
- `innercc_run`: `20260427-154634`
- `claude_code_run`: `20260429-114027`
- `comparison_category`: `bundle_collapse_and_patch_pollution`
- 一句话结论：
  这是一个覆盖 `132` 条 `FAIL_TO_PASS` 的重型 bundle case：`claude-code` 把它缩成了 `path_info` 单点兼容修复，完全没覆盖 benchmark target；`innercc` 虽然试图同时实现多条 release note，却把官方 test patch 混进自己的 patch，导致 evaluator 应用阶段出现大面积 `Reversed (or previously applied)`，最终留下的新测试期望与缺失的源代码实现互相错位，两个 CLI 都是 `0/132 F2P`。
- 根因标签：
  - `task_understanding_error`
  - `bundle_collapse`
  - `validation_gap`
  - `tooling_or_harness_issue`

## 2. Task And Gold Spec

### 2.1 benchmark task

`problem_statement`:

```text
1) [Support older `md5` tool versions for external ssh deps/outs;](https://github.com/iterative/dvc/issues/2242)
2) [Add a workaround for submodules bug in gitpython;](https://github.com/iterative/dvc/issues/1898); Kudos @gdyuldin :tada:
3) [Fixed bash autocompletion;](https://github.com/iterative/dvc/issues/2069)Kudos @Naba7 :tada:
4) [Fixed bugs in ssh remote that caused unexpected errors;](https://github.com/iterative/dvc/issues/2280)
5) [Sped up dir checksum calculation for ssh remote;](https://github.com/iterative/dvc/pull/2278)
6) [Fixed recursion when using deepcopy for PathInfos;](https://github.com/iterative/dvc/issues/2259)
7) [Fixed --jobs bug in pull/push/etc;](https://github.com/iterative/dvc/pull/2289)
8) [Lock `dvc import-url` stages by default;](https://github.com/iterative/dvc/pull/2307)
9) [Fixed bug that caused dvc-file checksum change when `meta` field changes;](https://github.com/iterative/dvc/issues/2209)
10) [Fixed bug in ssh remote, that caused multiple password prompts;](https://github.com/iterative/dvc/issues/2305)
11) [Fixed bug in checksum calculation for directories, that caused dvc to not use state db for files inside of that dir, which resulted in performance degradation;](https://github.com/iterative/dvc/issues/2258)
12) [Temporarily made psutil dependency optional for `dvc version` command;](https://github.com/iterative/dvc/issues/2284)
```

`FAIL_TO_PASS`: `132` 条，不是单点 bug，而是一个标准 `bundle_case`。按测试分布可以分成至少 7 个主题簇：

1. `import-url` / `locked=True`：`tests/func/test_import_url.py`, `tests/unit/command/test_imp_url.py`, `tests/func/test_update.py`
2. `PathInfo` / `URLInfo` deepcopy 与路径语义：`tests/unit/test_path_info.py`, `tests/func/test_output.py`
3. `stage checksum` 忽略 `meta`：`tests/unit/test_stage.py`
4. `--jobs` / data sync / repro：`tests/func/test_data_cloud.py`, `tests/func/test_repro.py`, `tests/func/test_remote.py`
5. `ssh remote` / password prompt / md5 兼容：`tests/unit/remote/ssh/test_pool.py`, `tests/func/test_data_cloud.py`, `tests/func/test_remote.py`
6. `git submodule tree workaround`：`tests/func/test_tree.py`
7. `version` / `psutil` optional：少量 version path 与 CLI 支撑逻辑

`PASS_TO_PASS`: `0` 条。这个 benchmark 只关心一组新增/变化后的 F2P；没有额外的历史回归保护集。

### 2.2 runner-level user query

```text
You are working inside a git repository checked out to the benchmark base commit.

Implement the minimal code-only fix for this software evolution task.

SWE-EVO Instance ID: iterative__dvc_0.52.1_0.53.1

Release note / requirement:
1) [Support older `md5` tool versions for external ssh deps/outs;](https://github.com/iterative/dvc/issues/2242)
2) [Add a workaround for submodules bug in gitpython;](https://github.com/iterative/dvc/issues/1898); Kudos @gdyuldin :tada:
3) [Fixed bash autocompletion;](https://github.com/iterative/dvc/issues/2069)Kudos @Naba7 :tada:
4) [Fixed bugs in ssh remote that caused unexpected errors;](https://github.com/iterative/dvc/issues/2280)
5) [Sped up dir checksum calculation for ssh remote;](https://github.com/iterative/dvc/pull/2278)
6) [Fixed recursion when using deepcopy for PathInfos;](https://github.com/iterative/dvc/issues/2259)
7) [Fixed --jobs bug in pull/push/etc;](https://github.com/iterative/dvc/pull/2289)
8) [Lock `dvc import-url` stages by default;](https://github.com/iterative/dvc/pull/2307)
9) [Fixed bug that caused dvc-file checksum change when `meta` field changes;](https://github.com/iterative/dvc/issues/2209)
10) [Fixed bug in ssh remote, that caused multiple password prompts;](https://github.com/iterative/dvc/issues/2305)
11) [Fixed bug in checksum calculation for directories, that caused dvc to not use state db for files inside of that dir, which resulted in performance degradation;](https://github.com/iterative/dvc/issues/2258)
12) [Temporarily made psutil dependency optional for `dvc version` command;](https://github.com/iterative/dvc/issues/2284)

Expected failing tests that should pass after your fix:
- tests/func/test_data_cloud.py::TestCheckSumRecalculation::test
- tests/func/test_data_cloud.py::TestDataCloud::test
- tests/func/test_data_cloud.py::TestDataCloudCLIBase::test
- tests/func/test_data_cloud.py::TestDataCloudErrorCLI::test_error
- tests/func/test_data_cloud.py::TestRecursiveSyncOperations::test
- tests/func/test_data_cloud.py::TestRemoteLOCAL::test
- tests/func/test_data_cloud.py::TestRemoteLOCALCLI::test
- tests/func/test_data_cloud.py::TestRemoteSSHMocked::test
- tests/func/test_data_cloud.py::TestShouldWarnOnNoChecksumInLocalAndRemoteCache::test
- tests/func/test_data_cloud.py::TestWarnOnOutdatedStage::test
- tests/func/test_import_url.py::TestCmdImport::test
- tests/func/test_import_url.py::TestCmdImport::test_unsupported
- tests/func/test_import_url.py::TestDefaultOutput::test
- tests/func/test_import_url.py::TestImportFilename::test
- tests/func/test_import_url.py::TestShouldRemoveOutsBeforeImport::test
- tests/func/test_output.py::test_scheme[../file-local]
- tests/func/test_output.py::test_scheme[..\\file-local]
- tests/func/test_output.py::test_scheme[./file-local]
- tests/func/test_output.py::test_scheme[.\\file-local]
- tests/func/test_output.py::test_scheme[file-local]
- tests/func/test_output.py::test_scheme[gs://bucket/path-gs]
- tests/func/test_output.py::test_scheme[path/to/file-local]
- tests/func/test_output.py::test_scheme[path\\to\\file-local]
- tests/func/test_output.py::test_scheme[s3://bucket/path-s3]
- tests/func/test_output.py::test_scheme[ssh://example.com:/dir/path-ssh]
- tests/func/test_output.py::test_scheme[unknown://path-local]
- tests/func/test_remote.py::TestRemote::test
- tests/func/test_remote.py::TestRemote::test_overwrite
- tests/func/test_remote.py::TestRemote::test_referencing_other_remotes
- tests/func/test_remote.py::TestRemote::test_relative_path
- tests/func/test_remote.py::TestRemoteDefault::test
- tests/func/test_remote.py::TestRemoteRemove::test
- tests/func/test_remote.py::TestRemoteRemoveDefault::test
- tests/func/test_remote.py::TestRemoteShouldHandleUppercaseRemoteName::test
- tests/func/test_remote.py::test_dir_checksum_should_be_key_order_agnostic
- tests/func/test_remote.py::test_large_dir_progress
- tests/func/test_remote.py::test_partial_push_n_pull
- tests/func/test_repro.py::TestCmdRepro::test
- tests/func/test_repro.py::TestCmdReproChdir::test
- tests/func/test_repro.py::TestCmdReproChdirCwdBackwardCompatible::test
- tests/func/test_repro.py::TestNonExistingOutput::test
- tests/func/test_repro.py::TestReproAllPipelines::test
- tests/func/test_repro.py::TestReproAlreadyCached::test
- tests/func/test_repro.py::TestReproAlreadyCached::test_force_import
- tests/func/test_repro.py::TestReproAlreadyCached::test_force_with_dependencies
- tests/func/test_repro.py::TestReproChangedCode::test
- tests/func/test_repro.py::TestReproChangedData::test
- tests/func/test_repro.py::TestReproChangedDeepData::test
- tests/func/test_repro.py::TestReproChangedDir::test
- tests/func/test_repro.py::TestReproChangedDirData::test
- tests/func/test_repro.py::TestReproCyclicGraph::test
- tests/func/test_repro.py::TestReproDataSource::test
- tests/func/test_repro.py::TestReproDepDirWithOutputsUnderIt::test
- tests/func/test_repro.py::TestReproDepUnderDir::test
- tests/func/test_repro.py::TestReproDownstream::test
- tests/func/test_repro.py::TestReproDry::test
- tests/func/test_repro.py::TestReproDryNoExec::test
- tests/func/test_repro.py::TestReproExternalBase::test
- tests/func/test_repro.py::TestReproExternalGS::test
- tests/func/test_repro.py::TestReproExternalHDFS::test
- tests/func/test_repro.py::TestReproExternalHTTP::test
- tests/func/test_repro.py::TestReproExternalLOCAL::test
- tests/func/test_repro.py::TestReproExternalS3::test
- tests/func/test_repro.py::TestReproExternalSSH::test
- tests/func/test_repro.py::TestReproFail::test
- tests/func/test_repro.py::TestReproForce::test
- tests/func/test_repro.py::TestReproIgnoreBuildCache::test
- tests/func/test_repro.py::TestReproLocked::test
- tests/func/test_repro.py::TestReproLocked::test_non_existing
- tests/func/test_repro.py::TestReproLockedCallback::test
- tests/func/test_repro.py::TestReproLockedUnchanged::test
- tests/func/test_repro.py::TestReproMetricsAddUnchanged::test
- tests/func/test_repro.py::TestReproMissingMd5InStageFile::test
- tests/func/test_repro.py::TestReproNoCommit::test
- tests/func/test_repro.py::TestReproNoDeps::test
- tests/func/test_repro.py::TestReproPhony::test
- tests/func/test_repro.py::TestReproPipeline::test
- tests/func/test_repro.py::TestReproPipeline::test_cli
- tests/func/test_repro.py::TestReproPipelines::test
- tests/func/test_repro.py::TestReproPipelines::test_cli
- tests/func/test_repro.py::TestReproUpToDate::test
- tests/func/test_repro.py::TestReproWorkingDirectoryAsOutput::test
- tests/func/test_repro.py::TestReproWorkingDirectoryAsOutput::test_nested
- tests/func/test_repro.py::TestReproWorkingDirectoryAsOutput::test_similar_paths
- tests/func/test_repro.py::TestShouldDisplayMetricsOnReproWithMetricsOption::test
- tests/func/test_repro.py::test_dvc_formatting_retained
- tests/func/test_repro.py::test_recursive_repro_default
- tests/func/test_repro.py::test_recursive_repro_empty_dir
- tests/func/test_repro.py::test_recursive_repro_on_stage_file
- tests/func/test_repro.py::test_recursive_repro_recursive_missing_file
- tests/func/test_repro.py::test_recursive_repro_single
- tests/func/test_repro.py::test_recursive_repro_single_force
- tests/func/test_tree.py::TestGitSubmoduleTree::test_exists
- tests/func/test_tree.py::TestGitSubmoduleTree::test_isdir
- tests/func/test_tree.py::TestGitSubmoduleTree::test_isfile
- tests/func/test_tree.py::TestGitSubmoduleTree::test_open
- tests/func/test_tree.py::TestGitTree::test_exists
- tests/func/test_tree.py::TestGitTree::test_isdir
- tests/func/test_tree.py::TestGitTree::test_isfile
- tests/func/test_tree.py::TestGitTree::test_open
- tests/func/test_tree.py::TestWalkInGit::test_branch
- tests/func/test_tree.py::TestWalkInGit::test_nobranch
- tests/func/test_tree.py::TestWalkInNoSCM::test
- tests/func/test_tree.py::TestWalkInNoSCM::test_subdir
- tests/func/test_tree.py::TestWorkingTree::test_exists
- tests/func/test_tree.py::TestWorkingTree::test_isdir
- tests/func/test_tree.py::TestWorkingTree::test_isfile
- tests/func/test_tree.py::TestWorkingTree::test_open
- tests/func/test_update.py::test_update_import
- tests/func/test_update.py::test_update_import_url
- tests/unit/command/test_imp_url.py::test_failed_import_url
- tests/unit/command/test_imp_url.py::test_import_url
- tests/unit/dependency/test_hdfs.py::TestDependencyLOCAL::test_save_missing
- tests/unit/output/test_hdfs.py::TestOutputLOCAL::test_save_missing
- tests/unit/remote/ssh/test_pool.py::test_doesnt_swallow_errors
- tests/unit/test_path_info.py::test_url_info_deepcopy[CloudURLInfo]
- tests/unit/test_path_info.py::test_url_info_deepcopy[URLInfo]
- tests/unit/test_path_info.py::test_url_info_eq[CloudURLInfo]
- tests/unit/test_path_info.py::test_url_info_eq[URLInfo]
- tests/unit/test_path_info.py::test_url_info_parent[CloudURLInfo]
- tests/unit/test_path_info.py::test_url_info_parent[URLInfo]
- tests/unit/test_path_info.py::test_url_info_parents[CloudURLInfo]
- tests/unit/test_path_info.py::test_url_info_parents[URLInfo]
- tests/unit/test_path_info.py::test_url_info_str[CloudURLInfo]
- tests/unit/test_path_info.py::test_url_info_str[URLInfo]
- tests/unit/test_stage.py::test_meta_ignored
- tests/unit/test_stage.py::test_stage_checksum
- tests/unit/test_stage.py::test_stage_fname[False]
- tests/unit/test_stage.py::test_stage_fname[True]
- tests/unit/test_stage.py::test_stage_update
- tests/unit/test_stage.py::test_wdir_default_ignored
- tests/unit/test_stage.py::test_wdir_non_default_is_not_ignored

Rules:
- Modify only non-test source files.
- Do not edit tests, fixtures, docs, changelog files, or version metadata files unless absolutely required.
- Prefer a minimal fix over broad refactors.
- You may inspect and run commands in the repository.
- When you are done, just finish normally. The patch will be collected from git diff.
```

### 2.3 trace-level agent goals

- `innercc`
  - 明确认出这是 release bundle，并尝试“一次性实现多条修复”。
  - 在 trace 中依次列出 `meta checksum`、`import-url locked`、`psutil optional`、`jobs=None`、`PathInfo deepcopy`、`SSH pool`、`GitSubmoduleTree` 等多个子任务。
  - 但它没有守住 prompt 的 `Modify only non-test source files` 约束，后期直接编辑多份测试文件，导致 patch artifact 被污染。
- `claude-code`
  - 初始阶段先跑了少量 failing tests，很快被 `path_info.py` / pathlib 兼容错误吸走。
  - 后续内部目标收缩成“修复旧版 pathlib 内部 API 差异”，即 `_from_parts` / `_cparts`。
  - 基本放弃了其余 `11` 条 release note 对应的功能修复。

### 2.4 official golden answer

这个 case 的官方 golden patch横跨 `40+` 个源码文件，核心不是一条 patch，而是一组行为簇。真正决定 benchmark target 的关键 hunk 至少包括：

#### Golden cluster A: `import-url` 默认 `locked=True`

```diff
@@
-def imp_url(
-    self, url, out=None, resume=False, fname=None, erepo=None, locked=False
-):
+def imp_url(self, url, out=None, fname=None, erepo=None, locked=True):
@@
-        stage.run(resume=resume)
+        stage.run()
```

这对应 `tests/func/test_import_url.py`, `tests/unit/command/test_imp_url.py`, `tests/func/test_update.py`。

#### Golden cluster B: `stage checksum` 忽略 `meta`

```diff
@@
-        if self.PARAM_MD5 in d.keys():
-            del d[self.PARAM_MD5]
+        d.pop(self.PARAM_MD5, None)
+        d.pop(self.PARAM_META, None)
```

这对应 `tests/unit/test_stage.py::*`。

#### Golden cluster C: `pull/push/fetch` 的 `jobs=None`

```diff
@@
-    jobs=1,
+    jobs=None,
```

这对应大量 `data_cloud`, `remote`, `repro` 测试。

#### Golden cluster D: `PathInfo` / `URLInfo` 的 deepcopy 与路径语义

```diff
+    def __deepcopy__(self, memo):
+        return self
```

这对应 `tests/unit/test_path_info.py::*` 和一批 output/path scheme 测试。

#### Golden cluster E: `SSH pool` 抽象上移到 `dvc.remote.pool`

benchmark patch 中显式新增 `dvc.remote.pool` 的导入与关闭逻辑，测试也在 `tests/conftest.py` / `tests/unit/remote/ssh/test_pool.py` 中依赖它：

```diff
+from dvc.remote.pool import close_pools
```

这也是后续 evaluator 中最早出现的决定性 `ModuleNotFoundError` 之一。

换句话说，这个 case 的官方答案要求 agent：

1. 先判断这是 `bundle_case`，而不是单点兼容 bug。
2. 至少覆盖 `import-url`、`stage checksum`、`jobs`、`ssh/pool`、`path_info`、`git submodule tree` 这些跨模块行为。
3. 不能通过改测试来“同步期望”。

## 3. Outcome Comparison

| CLI | resolved | F2P | P2P | cli_duration_ms | cli_num_turns | tool_use_count | tool_error_count | patch_apply |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| `innercc` | `false` | `0/132` | `0/0` | `14640` | `1` | `230` | `9` | `true` |
| `claude-code` | `false` | `0/132` | `0/0` | `828976` | `93` | `92` | `18` | `true` |

同样都是 `0/132`，但失败形态不同：

- `innercc`：覆盖范围本来更广，但 patch artifact 里混入大量测试文件；评测应用时出现大面积 reverse/reject，最终留下的是“新测试期望前移、源代码实现缺失”的错位状态。
- `claude-code`：patch 干净得多，但目标极窄，只改了 `dvc/path_info.py`，对 bundle target 几乎没有覆盖。

## 4. Artifact Index

### innercc

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_0.52.1_0.53.1/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_0.52.1_0.53.1/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_0.52.1_0.53.1/cli_result.json)
- [cli_stdout.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_0.52.1_0.53.1/cli_stdout.log)
- [cli_stderr.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_0.52.1_0.53.1/cli_stderr.log)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/infer/runs/iterative__dvc_0.52.1_0.53.1/router_trace_bundle.json)
- [eval worker log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260427-154634/eval_worker_logs/iterative__dvc_0.52.1_0.53.1.log)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_0.52.1_0.53.1/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_0.52.1_0.53.1/test_output.txt)
- [run_instance.log](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260427-154634/eval_input_20260427-154634/iterative__dvc_0.52.1_0.53.1/run_instance.log)

### claude-code

- [patch.diff](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_0.52.1_0.53.1/patch.diff)
- [preds.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_0.52.1_0.53.1/preds.json)
- [cli_result.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_0.52.1_0.53.1/cli_result.json)
- [cli_stdout.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_0.52.1_0.53.1/cli_stdout.log)
- [cli_stderr.log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_0.52.1_0.53.1/cli_stderr.log)
- [router_trace_bundle.json](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/infer/runs/iterative__dvc_0.52.1_0.53.1/router_trace_bundle.json)
- [eval worker log](/home/wt/sss_repos/sss_auto/SWE-EVO/official48_runs/20260429-114027/eval_worker_logs/iterative__dvc_0.52.1_0.53.1.log)
- [report.json](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_0.52.1_0.53.1/report.json)
- [test_output.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_0.52.1_0.53.1/test_output.txt)
- [run_instance.log](/home/wt/sss_repos/sss_auto/SWE-EVO/logs/run_evaluation/eval_input_20260429-114027/eval_input_20260429-114027/iterative__dvc_0.52.1_0.53.1/run_instance.log)

## 5. Chronological Trace Reconstruction

### 5.1 innercc

#### `bootstrap` (`step 1-31`)

- `step_range`: `1-31`
- 关键工具：`Bash`, `Read`
- 关键文件：大量 failing tests、`dvc/path_info.py`, `dvc/stage.py`
- 关键命令：
  - 多次 `python3 -m pytest ...`
  - `python3 -c "import mockssh"`
  - `pip install -e .`
- 当前阶段目标：先跑测试、恢复依赖环境。
- 阶段产出：环境噪声很大，但它至少确认了这不是一个单一 failing test。

#### `repo_exploration` (`step 32-93`)

- `step_range`: `32-93`
- 关键工具：`Bash`, `Read`
- 关键文件：`dvc/stage.py`, `dvc/repo/imp_url.py`, `dvc/remote/base.py`, `dvc/path_info.py`, `dvc/remote/ssh/*`, `tests/func/test_tree.py`
- 关键命令：
  - `git log --oneline`
  - 大量 `grep -n`
  - 读取多个测试簇
- 当前阶段目标：把 release note 映射到源码模块。
- 阶段产出：确实识别出多个子任务簇。

#### `task_planning` (`step 94-141`)

- `step_range`: `94-141`
- 关键工具：`Edit`, `Read`
- 关键文件：`dvc/stage.py`, `dvc/repo/imp_url.py`, `dvc/command/version.py`, `dvc/repo/fetch.py`, `dvc/repo/pull.py`, `dvc/repo/push.py`, `dvc/path_info.py`, `dvc/remote/base.py`, `dvc/scm/git/tree.py`
- 关键命令：无
- 当前阶段目标：分批实现多个 release note。
- 阶段产出：进入多点并行修复模式。

#### `fault_localization` (`step 94-156`)

- `step_range`: `94-156`
- 关键工具：`Edit`
- 关键文件：同上，另加 `dvc/remote/ssh/pool.py`, `dvc/command/imp_url.py`
- 当前阶段目标：把 bundle 中的关键簇都落到具体文件。
- 阶段产出：源码层面确实覆盖了不少 official patch 核心文件。

#### `hypothesis_testing` (`step 162-220`)

- `step_range`: `162-220`
- 关键工具：`Bash`
- 关键命令：
  - `python3 -m pytest tests/unit/test_stage.py...`
  - `python3 -m pytest tests/unit/test_path_info.py...`
  - 多个 `python3 -c` 小 probe
- 当前阶段目标：逐簇验证。
- 阶段产出：验证噪声极大，且开始被 `path_info` / mockssh / pytest 环境问题打散，没有形成稳定闭环。

#### `code_editing` (`step 96-176`)

- `step_range`: `96-176`
- 关键工具：`Edit`
- 关键文件：
  - 源码：`dvc/stage.py`, `dvc/repo/imp_url.py`, `dvc/command/version.py`, `dvc/repo/fetch.py`, `dvc/repo/pull.py`, `dvc/repo/push.py`, `dvc/path_info.py`, `dvc/remote/base.py`, `dvc/remote/ssh/connection.py`, `dvc/remote/ssh/pool.py`, `dvc/scm/git/tree.py`, `scripts/completion/dvc.bash`
  - 测试：`tests/func/test_tree.py`, `tests/unit/command/test_imp_url.py`, `tests/unit/test_stage.py`, `tests/unit/test_path_info.py`, `tests/func/test_update.py`
- 当前阶段目标：让 patch 与 release bundle 对齐。
- 阶段产出：直接违反 prompt 的 non-test 限制，patch 被测试文件污染。

#### `validation` (`step 181-229`)

- `step_range`: `181-229`
- 关键工具：`Bash`
- 关键命令：
  - 多个局部 pytest
  - `git diff --stat`
  - `git stash && pytest ...`
- 当前阶段目标：收口验证。
- 阶段产出：没有拿到任何接近 `132/132 F2P` 的整体验证，只是在局部失败与依赖噪声之间反复切换。

#### `termination` (`step 231-232`)

- `step_range`: `231-232`
- 关键工具：无
- 当前阶段目标：结束会话。
- 阶段产出：声称“12 条 release notes 都已覆盖”，但与 evaluator 结果完全不符。

### 5.2 claude-code

#### `bootstrap` (`step 1-14`)

- `step_range`: `1-14`
- 关键工具：`Bash`
- 关键文件：`tests/unit/test_stage.py`, `tests/unit/test_path_info.py`
- 关键命令：多次 `python3 -m pytest ...`
- 当前阶段目标：先从 failing tests 中找一个可复现入口。
- 阶段产出：很快被 `path_info.py` 的 pathlib 兼容错误吸住。

#### `repo_exploration` (`step 15-25`)

- `step_range`: `15-25`
- 关键工具：`Read`, `Bash`
- 关键文件：`dvc/path_info.py`
- 关键命令：检查 `_from_parts`, `_cparts`
- 当前阶段目标：理解 `path_info` 报错。
- 阶段产出：把整案重写成“旧 pathlib2 API 与现代 pathlib 不兼容”。

#### `task_planning` (`step 25-36`)

- `step_range`: `25-36`
- 关键工具：`Bash`
- 关键文件：`dvc/path_info.py`
- 当前阶段目标：为 `path_info` 制定兼容性修复。
- 阶段产出：决定只改 `_from_parts` / `_cparts` 相关逻辑。

#### `fault_localization` (`step 25-48`)

- `step_range`: `25-48`
- 关键工具：`Bash`
- 关键文件：`dvc/path_info.py`
- 当前阶段目标：缩小到单点兼容修复。
- 阶段产出：完全放弃其余 release note 主题。

#### `hypothesis_testing` (`step 26-86`)

- `step_range`: `26-86`
- 关键工具：`Bash`
- 关键命令：大量 `python3 -c` 探查 pathlib 内部 API
- 当前阶段目标：找到 Python 3.12 下可工作的构造方式。
- 阶段产出：形成了极强的 `hypothesis_lock_in`，所有验证都围绕 pathlib internals。

#### `code_editing` (`step 41-53`)

- `step_range`: `41-53`
- 关键工具：`Edit`
- 关键文件：`dvc/path_info.py`
- 当前阶段目标：实现最小兼容性修复。
- 阶段产出：只修改 `dvc/path_info.py`。

#### `validation` (`step 63-88`)

- `step_range`: `63-88`
- 关键工具：`Bash`
- 关键命令：若干 `pytest tests/unit/test_path_info.py` 及少量关联测试
- 当前阶段目标：验证 `path_info` 层面行为。
- 阶段产出：即便局部通过，也完全不足以支撑 bundle case 结束。

#### `termination` (`step 90-93`)

- `step_range`: `90-93`
- 关键工具：无
- 当前阶段目标：结束会话。
- 阶段产出：把整个 case 错判成 `path_info` 兼容性问题。

## 6. Hypothesis Iteration Log

### 6.1 innercc

| step_range | hypothesis | evidence_used | why_it_seemed_plausible | why_it_was_correct_or_wrong |
| --- | --- | --- | --- | --- |
| `32-93` | 这是一个真正的 release bundle，需要实现多条 release note | `git log`, 多组 failing tests, 多模块 grep/read | `132` 条 F2P 分布很广，直观看就是 bundle | 正确；这是四案中少数正确判断任务规模的 agent |
| `94-156` | 只要把每条 release note 对应的代码与测试都“补齐”，就能整体通过 | 各子任务源码阅读、历史搜索 | 看起来像在做系统升级回填 | 错在实现方式：agent 开始直接改测试，把“复现官方 patch”与“修改 benchmark 允许的 source-only patch”混为一谈 |
| `181-229` | 局部 pytest 与语法检查足够证明大 patch 已可交付 | 局部 unit tests、手写 probe、`git diff --stat` | bundle case 很难全量验证，容易退化成抽样验证 | 错；没有任何接近 benchmark 目标集的收口验证，而且 patch artifact 已经污染 |

### 6.2 claude-code

| step_range | hypothesis | evidence_used | why_it_seemed_plausible | why_it_was_correct_or_wrong |
| --- | --- | --- | --- | --- |
| `15-25` | 旧版 DVC 在现代 Python/pathlib 上的兼容问题是本案主因 | 早期 unit test 报错集中在 `path_info.py` | 局部错误信号非常强，且容易快速复现 | 错；这只覆盖 bundle 里的一个子簇，不是 benchmark target 的主体 |
| `25-53` | 只改 `dvc/path_info.py` 就能把大量 failing tests 拉起来 | `_from_parts`, `_cparts` 相关错误 | 从单测角度看有一定解释力 | 错；其余 `import-url`, `stage`, `jobs`, `ssh pool`, `git submodule` 完全未触及 |
| `63-93` | `path_info` 局部通过后即可结束 | 局部 pytest | 单点兼容 bug 常见收口方式 | 错；对 bundle case 来说是典型 `bundle_collapse` |

## 7. Patch And Code-Level Analysis

### 7.1 innercc

`innercc` 的源码 patch 覆盖了不少 golden 簇：

- `dvc/stage.py`：`PARAM_META`
- `dvc/repo/imp_url.py` / `dvc/command/imp_url.py`
- `dvc/command/version.py`
- `dvc/repo/fetch.py`, `pull.py`, `push.py`
- `dvc/path_info.py`
- `dvc/remote/base.py`
- `dvc/remote/ssh/connection.py`, `pool.py`
- `dvc/scm/git/tree.py`
- `scripts/completion/dvc.bash`

问题不在“完全修错方向”，而在两个更严重的层面：

1. 它直接编辑了多份测试文件，违反 prompt，也把 patch artifact 变成了 source+test 混合包。
2. `run_instance.log` 显示 evaluator 应用 patch 时，大量 hunk 被判定为 `Reversed (or previously applied)`，最终 `git diff before/after` 里留下来的主要是测试文件改动，而不是完整源码实现。

因此它不是单纯的“没修到”，而是：

- 任务规模判断正确；
- 但实现方式与 benchmark 协议不兼容；
- 最终交付物无法稳定表达它在 trace 中声称完成的那些源码修改。

### 7.2 claude-code

`claude-code` 的 patch 极窄，只改了：

- `dvc/path_info.py`

这个改动对 bundle 中的 `PathInfo deepcopy / pathlib internals` 子问题确实有相关性，但与 official golden patch 的主体相比，缺口极大：

1. 完全没改 `dvc/repo/imp_url.py`
2. 完全没改 `dvc/stage.py`
3. 完全没改 `dvc/repo/fetch.py/pull.py/push.py`
4. 完全没改 `dvc/remote/pool.py` 相关逻辑
5. 完全没改 `dvc/scm/git/tree.py`

从 patch 与 golden answer 的差异看，`claude-code` 属于典型 `bundle_collapse`。

## 8. Evaluation And Failure Evidence

两个 CLI 的 evaluator 终态都非常明确：

- `FAIL_TO_PASS`: `0/132`
- `PASS_TO_PASS`: `0/0`

### innercc 的决定性失败证据

`run_instance.log` 最关键的信号不是测试断言，而是 patch 应用阶段：

```text
Failed to apply patch to container: git apply --verbose
Failed to apply patch to container: git apply --verbose --reject
...
Reversed (or previously applied) patch detected!  Assuming -R.
...
patching file tests/unit/test_path_info.py
Reversed (or previously applied) patch detected!  Assuming -R.
```

而 `git diff before`/`after` 显示最终主要留下的是测试文件 diff。随后 `test_output.txt` 很快出现：

```text
ModuleNotFoundError: No module named 'dvc.remote.pool'
```

这说明 benchmark 新测试已经前移到了“应存在 `dvc.remote.pool`”的语义，但对应源码没有稳定落地。

### claude-code 的决定性失败证据

`claude-code` 的 patch 应用是干净的，但 evaluator 一样迅速失败在 benchmark 新测试依赖的源码缺口上：

```text
ModuleNotFoundError: No module named 'dvc.remote.pool'
```

这证明：

1. 不是 harness 单独出错。
2. 而是 agent 只修了 `path_info.py`，对 bundle 的其余关键簇没有任何覆盖。

因此本案两边都不是“差一点通过”，而是 benchmark target 覆盖率严重不足。

## 9. Root Cause

- `direct_root_cause`
  - `innercc`：任务规模判断正确，但把“实现 official bundle”错误地执行成了“同时改源码和测试”，属于 `task_understanding_error` 与 `tooling_or_harness_issue` 的叠加。
  - `claude-code`：把 `132` 条 F2P 的 bundle case 缩成 `path_info` 单点兼容性问题，属于标准 `bundle_collapse`。
- `contributing_factors`
  - 两边都没有用 benchmark test clusters 驱动计划，而是让早期最易复现的局部错误信号主导了后续方向。
  - 两边都没有形成对 `132` 条 F2P 的分簇验证闭环。
  - `innercc` 后期为了追求“全面对齐 release note”，直接越过了 prompt 的 non-test 边界。
- `misleading_signals`
  - `path_info` / Python 兼容问题在当前环境里噪声很强，容易让 agent 误以为这就是主任务。
  - release note 很长，且每条都看起来“值得修”，如果不先按 failing tests 聚类，容易不是缩点，就是失控。

## 10. CLI Optimization Opportunities

### 10.1 case_specific_actions

1. 对 `FAIL_TO_PASS` 数量超过阈值的 case，强制先做 failing-test clustering，再允许进入编辑阶段。
   本案如果先按 `import-url`, `path_info`, `stage`, `ssh pool`, `git tree` 分簇，就不会被单一错误信号带偏。
2. 对 prompt 明确禁止改测试的 benchmark，CLI 应把测试文件 edit 视为高风险动作并要求二次确认。
   这能直接阻断 `innercc` 这类 patch pollution。

### 10.2 generalizable_actions

1. 为 bundle case 增加“目标覆盖率”检查。
   如果 patch 只触及一个簇，而 F2P 分布在多个模块，应阻止 termination。
2. 把 evaluator 新测试引入的 import / symbol 变化视为高优先级 gap 信号。
   例如 `dvc.remote.pool` 一出现，就应反查是否有对应源码模块与调用链落地。
3. 对 release bundle 固化“双约束”。
   一方面要求任务分簇；另一方面要求 patch 仅限源码文件，防止 agent 用改测试掩盖实现空洞。
