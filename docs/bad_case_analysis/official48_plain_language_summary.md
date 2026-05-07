# official48 白话版总表（2026-05-06）

这份文件只做一件事：把 `48` 个 case 改写成能直接看懂、能直接汇报的中文。

如果只想看今天汇报用的版本，直接看 [official48_daily_report_2026-05-06.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/official48_daily_report_2026-05-06.md)。

## 总判断

- 已整理 case：`48/48`
- 可直接当正例复用：`6`
- `innercc` 更接近或直接修成：`14`
- `claude-code` 更接近或直接修成：`11`
- 两边都修到一部分，但没有真正收口：`6`
- 两边都明显修偏：`11`
- 高频问题第一名是验证没收口：`validation_gap = 41/48`
- 第二名是任务理解错位：`task_understanding_error = 30/48`
- 第三名是过早锁定假设：`hypothesis_lock_in = 27/48`
- 一句话结论：大题先拆分，小题看契约，所有题都要用目标测试收口。

## 可以直接当正例复用的 6 案

这一组可以当“成功范式”看：任务目标集中，两个 CLI 都能比较快地对准 benchmark 真目标。

- `iterative__dvc_0.92.0_0.92.1`：两个 CLI 都把大段 release note 快速收缩到 benchmark 真正关心的 `--all-commits` 参数传递链，并把 command 层和 repo 层一起补齐。`claude-code` 还顺手补了 metrics diff，但没有带来副作用。
- `iterative__dvc_1.1.0_1.1.1`：这是一个非常干净的单点正例。两个 CLI 都识别出问题就是 `dvc/utils/diff.py::table(markdown=True)` 少了 trailing newline，只用一个函数的 3 行改动就同时修好了 diff、metrics、params 三组输出。
- `iterative__dvc_1.11.12_1.11.13`：这是一个窄任务正例。`innercc` 在 `protect()` 外层最小化吞掉 `EPERM/EACCES`，`claude-code` 把“忽略 protect 错误”抽象成 `chmod(ignore_errors=True)`，两者都打中了 benchmark 的真实目标。
- `iterative__dvc_3.15.0_3.15.1`：两个 CLI 都定位到 `dvc/output.py::unprotect()` 对非缓存输出调用过头，只要补上“只有 cached output 才 unprotect”的守卫就能修成。
- `modin-project__modin_0.27.0_0.27.1`：这是一个“小而尖”的成功案例。两个 CLI 都准确定位到 `DataFrameGroupBy.first/last` 缺少 `skipna` 参数，而且都只改了 `modin/pandas/groupby.py` 一处。
- `psf__requests_v2.27.0_v2.27.1`：问题非常集中，就是 `prepend_scheme_if_needed()` 重建 URL 时把 `auth` 丢了。两个 CLI 都定位到 `requests/utils.py`，并把 `auth` 补回 `netloc`，所以 `2/2` F2P 和 `185/185` P2P 都保住了。

## innercc 更接近或直接修成的 14 案

这一组的共性是：`innercc` 在大 bundle、多子任务、多层联动的题上更愿意扩大覆盖面，所以更容易碰到 benchmark 主轴；代价是更容易改宽。

- `dask__dask_2022.9.2_2022.10.0`：这是一个中大型打包任务。`innercc` 虽然也没修成，但至少拿到 `13/44` F2P，覆盖了 `array copy noop`、部分 `groupby median`、`datetime.time tokenization` 等多条线；`claude-code` 只修到 `1/44`，覆盖率明显更低。
- `dask__dask_2023.3.2_2023.4.0`：两边都没覆盖 HDF、parquet、IO 这一大簇，但 `innercc` 至少在 pandas 2.x、property、categorical、groupby cov 这几个兼容方向上修到 `3/61`，`claude-code` 是 `0/61`。
- `dask__dask_2023.8.0_2023.8.1`：`innercc` 把任务当成多子任务 bundle，覆盖了 cgroup v2、groupby sort/split_out、`enforce_runtime_divisions`、`to_csv(single_file, mode='x')` 等多条线，因此拿到 `2/11`；`claude-code` 只盯着 dataframe backend 和 groupby 一簇，最后 `0/11`。
- `dask__dask_2023.9.2_2023.9.3`：`innercc` 同时命中了两个独立修复点：`config.get(override_with=None)` 语义恢复和 complex reductions；`claude-code` 只修成前一半，后一半还引入了 `f4` 回归。
- `dask__dask_2024.3.1_2024.4.0`：两个 CLI 都没写坏代码，但 `claude-code` 把问题定位在 `_value_counts` 的局部输入处理，真实故障层却在 `_value_counts_aggregate`；`innercc` 命中了正确层级。
- `iterative__dvc_0.30.0_0.30.1`：这是单点 stage checksum bug。两个 CLI 都理解了 `wdir` default 导致 checksum 不一致，但只有 `innercc` 留下了正确 patch；`claude-code` 定位也接近，最后还是没过 F2P，还带来 1 条 P2P 回归。
- `iterative__dvc_1.0.1_1.0.2`：这题只有两条 F2P，但分属两个层次。`innercc` 至少修成了 `git-hook` 这半条线；`claude-code` 虽然也碰了两个点，但一个修错控制流，一个给错报错文案，最后 `0/2`。
- `iterative__dvc_2.19.0_2.20.0`：这是典型的多层 import/update bundle。`innercc` 不只是把 `--no-download` 接进 CLI 和 repo API，还把 partial import 生命周期、`fetch()` 补下载路径、`update()` 无下载语义一起补齐，因此 `14/14` F2P 全过；`claude-code` 只做了表面接线。
- `iterative__dvc_2.58.1_2.58.2`：官方修复点很窄，本质上是“该继续的时候继续，不该 pull 的时候别 pull”。`innercc` 至少修成了前一半；`claude-code` 把异常处理放错到 `dvc/stage/run.py`，两条都没落准。
- `iterative__dvc_2.7.2_2.7.3`：别看只有 `4` 条 F2P，实际上横跨三条线：`GitAuthError`、SSH passphrase、WebDAV 上传 API。`innercc` 至少碰到了前两条正确方向；`claude-code` 基本被 `fsspec_loop` 噪声带偏。
- `iterative__dvc_3.12.0_3.13.0`：表面看是大 bundle，实际 benchmark 只关心 Hydra 新签名和 experiments 随机名抽取两簇。`innercc` 很快借助 git diff 把两簇都命中，`33/33` 全过；`claude-code` 两簇都修偏了。
- `iterative__dvc_3.4.0_3.5.0`：这是明显的多子任务题。`innercc` 同时覆盖 `api.get_url` 和 `fetch --type` 两个目标点，所以 `2/2` F2P 全过；`claude-code` 只抓住了 `get_url_subrepos` 这一半，漏掉了命令行契约。
- `psf__requests_v2.4.0_v2.4.1`：目标包括 `ProtocolError` 重抛和“自重定向死循环”处理。`innercc` 两条都修到了，所以 `F2P = 2/2`；但它混入了一堆 Python 3.12 兼容改动，最终引入 1 条 P2P 回归。`claude-code` 则只修成了其中一半。
- `pydantic__pydantic_v2.7.0_v2.7.1`：这是“同一份 release note 里混着多个独立 fix”的典型例子。`innercc` 至少同时命中了 `AliasChoices`、`model_post_init`、`RootModel description`、`Secret serialization` 这几个子问题，拿到 `4/234`；`claude-code` 只修到其中一小部分。

## claude-code 更接近或直接修成的 11 案

这一组的共性是：`claude-code` 在小题、强契约题、接口行为题上更稳；但到大 bundle 时，也经常只是“比另一边更接近”，并不代表真的修成。

- `conan-io__conan_2.0.14_2.0.15`：这是超大打包任务。`innercc` 试图一次性覆盖很多 `platform_requires`、`replace_requires`、output、deploy 改动，改得很大但没形成闭环；`claude-code` 虽然也失败，但至少命中了 `platform_requires` 家族里的 `11` 条目标测试，回归也少得多。
- `conan-io__conan_2.0.2_2.0.3`：两边都只修到了局部。`innercc` 锁在 backup sources、integrity check、download cache 一簇；`claude-code` 锁在 `cache check-integrity` 和 `cache clean`，至少拿下了 `test_cache_integrity` 这 1 条 F2P。
- `iterative__dvc_1.0.0a1_1.0.0a2`：这是超大 bundle。`innercc` 几乎完全被 Python 3.12/pathlib 兼容噪声带偏，不仅 `68/68` F2P 全挂，还把 `242/242` P2P 全打坏；`claude-code` 至少只做了很窄的 `Mapping -> collections.abc` 修复，没有继续扩散回归。
- `iterative__dvc_1.0.0b6_1.0.0`：`innercc` 把 CLI 层参数语义映射到 repo 层已有的 `dry` 参数，看起来合理，但对外契约不匹配；`claude-code` 则顺着单测契约直接把 repo API 也改成 `no_exec`，所以修成了。
- `iterative__dvc_1.1.7_1.1.8`：这是“两条真实修复线混在同一份 release note 里”的 case。`claude-code` 基本把全部精力压在 `params falsy values` 上，拿到 `7/8`；`innercc` 也意识到 `.dvcignore` 问题存在，但修在了错误层级，最后只有 `5/8`。
- `iterative__dvc_1.10.2_1.11.0`：真实目标是 stage collection 和 missing-deps hint 的组合修复。`innercc` 被 `pathlib`、`TmpDir` 噪声带偏，做了大范围兼容补丁，还打坏了 `80` 条 P2P；`claude-code` 至少命中了 `Repo.get_stages()` 这一半。
- `iterative__dvc_2.21.1_2.21.2`：这题只有 `1` 条 F2P，但要求很刁钻：`api.params_show("untracked-file")` 单独调用可以读，和 `stages=` 或 `deps=True` 一起用时反而必须报 `No params found`。两个 CLI 都保留了不该有的 file fallback，不过 `innercc` 额外打坏了 3 条原本通过的场景，所以 `claude-code` 更接近。
- `iterative__dvc_2.5.0_2.5.1`：两个 CLI 都被 `tests/dir_helpers.py` 的 Python 3.12 兼容噪声带偏，直接改了测试辅助，而不是去修官方 patch 真正动到的 `dvc/objects/tree.py`、`dvc/fs/http.py`、`dvc/info.py`。`claude-code` 至少没有再带出额外回归。
- `iterative__dvc_2.8.1_2.8.2`：这是超大 bundle。`innercc` 从第一步起就被 `fsspec_loop`、async 兼容噪声带偏，只修了 `azure/http` 两个文件；`claude-code` 虽然也没对准 benchmark 主体，但至少命中了 `machine rename/status` 这一小簇，拿到 `8/133`。
- `iterative__dvc_3.43.1_3.44.0`：官方主轴是 import 场景下的 `skip-imports`、`check_updates` 控制，加上 DVC FS/ls/file-vs-dir 行为修复。`claude-code` 只抓住了 `--skip-imports` 这一条显眼 feature，但至少保住了 `104/104` P2P；`innercc` 被 pathspec `_DIR_MARK` 噪声带偏，只改了一行 `dvc/ignore.py`，还把 P2P 打到 `3/104`。
- `psf__requests_v2.12.2_v2.12.3`：`innercc` 任务方向其实接近正确，但第二次编辑把弯引号写进了 Python 源码，而且没用可靠验证及时发现；`claude-code` 把问题收敛到更窄的 early-return 条件，最终修成。

## 两边都修到一部分，但没有真正收口的 6 案

这一组最适合拿来讲“为什么只看 F2P 不够”。它们往往不是完全没修，而是修到一部分、或者把 F2P 修通了，却没有把相邻语义守住。

- `dask__dask_2023.6.1_2023.7.0`：`FAIL_TO_PASS = 5`，但两边都只修到了同一个小簇：CLI entry point loading、`_clean_ipython_traceback` typo、`from_pandas` immutability、`Series.rename(inplace=True)` warning。真正剩余的 failing tests 所在簇完全没碰到，所以都停在 `3/5`。
- `iterative__dvc_0.35.3_0.35.4`：两个 CLI 都看出 broken symlink 需要把 `exists` 改成 `lexists`，也都修好了 `remove` 路径；但都没有顺着 evaluator traceback 继续下钻到 `dvc/utils/fs.py:get_mtime_and_size()` 的目录遍历分支，最后都只做到 `1/2`。
- `iterative__dvc_1.6.3_1.6.4`：两个 CLI 都知道问题和 `dvc plots --experiment` 有关，也都修通了 command 层的 `test_plots_diff`；但真正的 repo-level 语义都修错了，所以双方都只停在 `1/9`。
- `psf__requests_v2.9.0_v2.9.1`：两个 CLI 都准确修到了 release note 明说的两个 bugfix，但又犯了同一个副作用错误：把 `_encode_params()` 对所有 `str/bytes` 都直接返回原值，导致共同引入 `test_params_bytes_are_encoded` 这 1 条 P2P 回归。
- `scikit-learn__scikit-learn_0.20.1_0.20.2`：两个 CLI 都把目标 F2P 修通了，正确给 `JaccardDistance` 加上 `nnz == 0 -> return 0.0` 的保护；但两边都留下 `2` 条 P2P 回归，说明对邻近语义完全没做够验证。
- `scikit-learn__scikit-learn_0.21.1_0.21.2`：和上一题很像。两边都命中了目标 F2P 的数值稳定性修复，但补丁副作用很大，最后都留下 `26` 条 P2P 回归。

## 两边都明显修偏的 11 案

这一组最能说明当前主矛盾不在“能不能写代码”，而在“大题没拆、定位过早锁死、验证太弱”。

- `dask__dask_2023.6.0_2023.6.1`：两边都把这个 case 过度缩小成 `dask/utils.py` 的 property/signature 兼容问题。`innercc` 甚至只用了 `2` 个 turns 就收工；`claude-code` 多做了一些验证，但本质还是 10 行级修补。结果 `105` 条 F2P 全部没过。
- `dask__dask_2024.1.0_2024.1.1`：这是整个 official48 里最典型的“大题被当成小题修”的例子。官方 patch 有 `63` 万字符，`FAIL_TO_PASS = 2774`，`PASS_TO_PASS = 5778`；两边却都只盯住一个兼容症状，最后 `F2P = 0`、`P2P = 0`。
- `iterative__dvc_0.33.1_0.34.0`：这题的 benchmark 实际只关心 `tests/test_tag.py::TestTag::test` 这 1 条 F2P，但 `innercc` 锁到了 CLI subparser 冲突，`claude-code` 锁到了 `remote add` 覆盖现有 section。两边修的都是真实 feature/bug，只是不是 benchmark 目标。
- `iterative__dvc_0.52.1_0.53.1`：这是覆盖 `132` 条 F2P 的重型 bundle。`claude-code` 把它缩成 `path_info` 单点兼容；`innercc` 虽然试图同时实现多条 release note，却把 benchmark test patch 混进自己的 patch，导致 evaluator 应用阶段大面积报 `Reversed (or previously applied)`。结果两边都是 `0/132`。
- `iterative__dvc_0.89.0_0.90.0`：benchmark 真目标是 `HTTPURLInfo`、protected mode 和 `gc -c` 等 `6` 条 release 变更，但两个 CLI 都被 `pathlib`、Python 兼容噪声带偏，只改了 `dvc/path_info.py` 和 `tests/dir_helpers.py`。`innercc` 还因为错误同步 benchmark test patch，又带出 `183` 条 P2P 回归。
- `iterative__dvc_0.91.2_0.91.3`：官方目标是同时修 `remote/base.py` 的 remote size estimation 和 `gdrive.py` 的 safeguard 清理。`claude-code` 只修了 gdrive 一半；`innercc` 试图一起修，但又把 benchmark test patch 同步进 patch，导致 evaluator 最终只应用了测试改动，没有应用对应源码。
- `iterative__dvc_3.13.3_3.14.0`：两个 CLI 都把这个 config case 缩成“处理 `~` home dir”这一小点。`innercc` 至少补了 `expanduser`，但漏掉 `_resolve()`、`ExpPath`、`local_dvc_dir`、`merge()` 这一整套逻辑；`claude-code` 更差，连有效 patch 都没有留下。
- `modin-project__modin_0.24.0_0.24.1`：这是单目标 hotfix。两边都把问题定位在 row/column length cache，但真实失败断言指向 `_column_widths_cache`，所以两个 patch 都没修到点上。
- `modin-project__modin_0.25.0_0.25.1`：这是一个被“release note 太短”误导的 case。官方问题其实是 `pandas 2.1.2` 适配和 `unidist<=0.4.1` pin；`innercc` 却缩成 `pct_change` warning 文案，`claude-code` 则几乎只做了 `setup.py` 的版本 pin。
- `pydantic__pydantic_v2.6.0b1_v2.6.0`：这题只有 `1` 条 F2P，但两个 CLI 还是都没修到。目标是保住 JSON schema 里的 discriminator mapping；`innercc` 锁在 `_extract_discriminator()`，`claude-code` 锁在 `$defs` garbage collection 顺序，都是表面机制，不是真正丢失 mapping 的路径。
- `pydantic__pydantic_v2.7.1_v2.7.2`：这是被 release note 中单条修复误导的典型失败。benchmark 真正关心的 `3` 条 F2P 在 docs examples、generics、schema 行为上，但两个 CLI 都被 `TypeVar.__default__ == NoDefault` 这个 Python 3.12 兼容点锁死，结果对真实目标几乎零覆盖，还把数千条 P2P 一并打挂。

## 最后一句话

- `innercc` 的长处是大题上更敢铺开，短处是更容易改宽、吃噪声、带回归。
- `claude-code` 的长处是小题和强契约题更稳，短处是大题上更容易只修到最显眼的一小块。
- 这 `48` 案最稳定的结论不是“谁绝对更强”，而是“谁在什么任务形状上更适合”。
- 如果下一轮只改一件事，最值得优先加的是：先按 `FAIL_TO_PASS` 拆任务，再用 exact F2P 和相邻 P2P 双门槛收口。
