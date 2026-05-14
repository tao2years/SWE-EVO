# pc7-claude-2.1.138 单轮细致复盘（2026-05-11）

## 1. 范围与数据源

本文只回答两个问题：

1. `20260511-095638-project-coverage-7-claude-2.1.138` 这轮为什么能做到 `resolved = 4/7`
2. 这个 `4/7` 更像是稳定能力，还是更像一次随机成功

为避免把 router 变量和 direct run 混在一起，本文把原始 `2.1.138` 只和同口径 direct baseline 对比：

| 版本名 | run id | 日期 | mode | cli bin |
| --- | --- | --- | --- | --- |
| `pc7-claude-2.1.89` | `20260511-115545-project-coverage-7-claude-2.1.89` | 2026-05-11 | direct | `/home/wt/.local/claude-code-2.1.89/bin/claude` |
| `pc7-claude-2.1.138` | `20260511-095638-project-coverage-7-claude-2.1.138` | 2026-05-11 | direct | `/home/wt/.local/bin/claude` |
| `pc7-claude-2.1.138-rerun` | `20260511-202352-project-coverage-7-claude-2.1.138-rerun` | 2026-05-11 | direct | `/home/wt/.local/bin/claude` |

本轮使用的证据：

- `official48_runs/<run_id>/metadata.json`
- `official48_runs/<run_id>/analysis/summary.json`
- `official48_runs/<run_id>/infer/runs/<instance_id>/cli_result.json`
- `official48_runs/<run_id>/infer/runs/<instance_id>/patch.diff`
- `official48_runs/<run_id>/eval_worker_logs/<instance_id>.log`
- `logs/run_evaluation/eval_input_<run_id>/.../<instance_id>/report.json`
- `logs/run_evaluation/eval_input_<run_id>/.../<instance_id>/test_output.txt`
- 新 rerun 外部日志：`/tmp/20260511-202352-project-coverage-7-claude-2.1.138-rerun.log`

限制：

- 这里不使用 `router_trace_bundle.json` 做主证据，因为原始 `pc7-claude-2.1.138` 是 direct run，不是 router run。
- evaluator 的 `resolved=true` 不等于“整个 pytest 全绿”，只等于 benchmark 关心的 `FAIL_TO_PASS` 与 `PASS_TO_PASS` 集合通过。这点在 `iterative__dvc_1.0.0b6_1.0.0` 尤其关键。

## 2. 统计口径

- `resolved`：看 `report.json` 的最终 `resolved` 布尔值，不信 agent 自报。
- `f2p micro`：先把所有 case 的 `FAIL_TO_PASS` 测试条目汇总，再算总通过率。
- `p2p micro`：先把所有 case 的 `PASS_TO_PASS` 测试条目汇总，再算总通过率。
- 它们都不是“先算每个 case 百分比，再做平均”。

## 3. run 级结论

### 3.1 原始 `2.1.138` 相对 `2.1.89` 的变化

| 指标 | `2.1.89` | `2.1.138` | 变化 |
| --- | --- | --- | --- |
| `resolved` | `3/7` | `4/7` | `+1` |
| `resolved rate` | `42.9%` | `57.1%` | 提升 |
| `f2p micro` | `45.5%` | `54.5%` | 提升 |
| `p2p micro` | `54.2704%` | `54.2923%` | 几乎不变，只是尾数更高 |
| `total cost` | `$34.72` | `$42.63` | 上升 |
| `avg duration` | `444701 ms` | `258700 ms` | 下降 |
| `total turns` | `460` | `328` | 下降 |
| `input tok` | `9.90M` | `7.33M` | 下降 |
| `output tok` | `113972` | `81861` | 下降 |
| `cache hit` | `46.8%` | `48.2%` | 小幅上升 |

一句话：

- 这不是“全面质量提升”
- 它的真实收益只来自一个 driver case：`iterative__dvc_1.0.0b6_1.0.0`
- 其余三个 resolved case 在 `2.1.89` 里本来就已经 resolved
- `p2p micro` 几乎没变，说明大盘稳定性并没有一起跃迁

### 3.2 原始 `2.1.138` 的四个 resolved case

- `dask__dask_2024.3.1_2024.4.0`
- `iterative__dvc_1.0.0b6_1.0.0`
- `modin-project__modin_0.27.0_0.27.1`
- `psf__requests_v2.27.0_v2.27.1`

其中：

- `dask / modin / requests` 在 `2.1.89` 里已经 resolved
- 真正新增的是 `iterative`

### 3.3 同口径 rerun 的最终结果

| 指标 | 原始 `2.1.138` | rerun `2.1.138` | 变化 |
| --- | --- | --- | --- |
| `resolved` | `4/7` | `3/7` | `-1` |
| `resolved rate` | `57.1%` | `42.9%` | 下降 |
| `f2p micro` | `54.5%` | `40.9%` | 下降 |
| `p2p micro` | `54.2923%` | `51.1249%` | 下降 |
| `total cost` | `$42.63` | `$154.36` | 大幅上升 |
| `avg duration` | `258700 ms` | `427230 ms` | 上升 |
| `total turns` | `328` | `666` | 大幅上升 |
| `input tok` | `7.33M` | `28.34M` | 大幅上升 |
| `output tok` | `81861` | `166799` | 上升 |
| `cache hit` | `48.2%` | `33.2%` | 下降 |

一句话：

- 原始 `2.1.138` 的 `4/7` 没有复现
- rerun 最终掉回 `3/7`
- 而且不是“少解 1 个但其余一样”，而是整体成本、turns、token 和 `p2p` 都更差

## 4. case 级差异矩阵

下表只列最关键字段：

| case | `resolved 2.1.89` | `resolved 2.1.138` | `f2p 2.1.89` | `f2p 2.1.138` | `p2p 2.1.89` | `p2p 2.1.138` | `cost 2.1.89` | `cost 2.1.138` | `turns 2.1.89` | `turns 2.1.138` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `conan` | `False` | `False` | `0.125` | `0.125` | `0.9936908517` | `0.9936908517` | `$15.70` | `$27.83` | `110` | `111` |
| `dask` | `True` | `True` | `1.0` | `1.0` | `1.0` | `1.0` | `$5.37` | `$3.16` | `71` | `37` |
| `iterative` | `False` | `True` | `0.0` | `1.0` | `0.0` | `1.0` | `$2.92` | `$2.29` | `60` | `37` |
| `modin` | `True` | `True` | `1.0` | `1.0` | `1.0` | `1.0` | `$1.29` | `$3.60` | `47` | `47` |
| `requests` | `True` | `True` | `1.0` | `1.0` | `1.0` | `1.0` | `$0.36` | `$0.57` | `21` | `16` |
| `pydantic` | `False` | `False` | `0.0` | `0.0` | `0.0879144852` | `0.0879144852` | `$5.13` | `$3.40` | `75` | `48` |
| `scikit` | `False` | `False` | `1.0` | `1.0` | `0.99543379` | `0.99543379` | `$3.96` | `$1.78` | `76` | `32` |

直接结论：

- 决定 `resolved` 变化的是 `iterative`
- 决定 `f2p micro` 变化的也是 `iterative`
- 决定 `p2p micro` 的仍然主要不是新增成功，而是大盘里 `pydantic` 的灾难性失败继续存在，所以 run-level `p2p` 只动了小数点后几位
- 成本上最大的坏变化来自 `conan`

如果把同口径 rerun 也拉进来，结论会更明确：

| case | `resolved old 2.1.138` | `resolved rerun` | `f2p old` | `f2p rerun` | `p2p old` | `p2p rerun` | `cost old` | `cost rerun` | `turns old` | `turns rerun` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `conan` | `False` | `False` | `0.125` | `0.0` | `0.9936908517` | `0.0788643533` | `$27.83` | `$124.95` | `111` | `364` |
| `dask` | `True` | `True` | `1.0` | `1.0` | `1.0` | `1.0` | `$3.16` | `$7.37` | `37` | `64` |
| `iterative` | `True` | `False` | `1.0` | `0.0` | `1.0` | `1.0` | `$2.29` | `$8.38` | `37` | `81` |
| `modin` | `True` | `True` | `1.0` | `1.0` | `1.0` | `1.0` | `$3.60` | `$7.78` | `47` | `68` |
| `requests` | `True` | `True` | `1.0` | `1.0` | `1.0` | `1.0` | `$0.57` | `$0.89` | `16` | `20` |
| `pydantic` | `False` | `False` | `0.0` | `0.0` | `0.0879144852` | `0.0879144852` | `$3.40` | `$4.71` | `48` | `63` |
| `scikit` | `False` | `False` | `1.0` | `1.0` | `0.99543379` | `0.99543379` | `$1.78` | `$0.29` | `32` | `6` |

这张表说明两件事：

- 原始 `4/7` 的新增收益只靠 `iterative`，而它在 rerun 里丢失了
- rerun 的大盘恶化主要由 `iterative` 和 `conan` 共同造成

## 5. driver cases 深挖

### 5.1 `iterative__dvc_1.0.0b6_1.0.0`

#### 当前状态

- `2.1.89`：`resolved = False`, `F2P = 0/2`, `P2P = 0/2`
- `2.1.138`：`resolved = True`, `F2P = 2/2`, `P2P = 2/2`

#### 概览

这是 `2.1.138` 唯一真正多解出来的 case。

#### 判断

这里更像是 **`contract_alignment_improved`**，不是纯随机蒙中。

`2.1.138` 把问题收敛成 `no_exec` 接口契约补齐，只改了：

- `dvc/command/imp_url.py`
- `dvc/repo/imp_url.py`

而 `2.1.89` 在同一条主线之外，又额外改了：

- `dvc/path_info.py`

这让它把任务从“补 `no_exec` 契约”扩成了“顺手修 Python 3.12/PathInfo 兼容问题”，结果 evaluator 关心的测试没有收口。

#### 证据

`2.1.138` 的 `patch.diff` 只有 `imp_url` 相关逻辑：

- `dvc/command/imp_url.py` 加 `--no-exec`
- `dvc/repo/imp_url.py` 加 `no_exec=False`
- `no_exec=True` 时跳过 `stage.run()`
- `dvcfile.dump(stage, no_lock=no_exec)`

文件：`official48_runs/20260511-095638-project-coverage-7-claude-2.1.138/infer/runs/iterative__dvc_1.0.0b6_1.0.0/patch.diff`

`2.1.89` 的 `patch.diff` 除了上面这些，还多了：

- `dvc/path_info.py` 把 `return cls._from_parts(args)` 改成 `object.__new__(cls) + __init__`

文件：`official48_runs/20260511-115545-project-coverage-7-claude-2.1.89/infer/runs/iterative__dvc_1.0.0b6_1.0.0/patch.diff`

evaluator 最终判定：

- `2.1.89 report.json`：`FAIL_TO_PASS failure = 2`, `PASS_TO_PASS failure = 2`
- `2.1.138 report.json`：`FAIL_TO_PASS success = 2`, `PASS_TO_PASS success = 2`

#### 为什么旧版错 / 新版对

`2.1.89` 的 `cli_result.json` 自报说“all 3 tests pass”，并把 `PathInfo._from_parts` 修复也算进了“完成摘要”。

这就是一个典型的：

- `self_report_optimism`
- `validation_gap`

它把更大的兼容性问题混进了当前任务，最后 evaluator 不认。

`2.1.138` 的 `cli_result.json` 反而更克制：

- 明确说自己的变更只是在 `no_exec`
- 还把 `_from_parts` 说成“pre-existing environment issue”

这次它虽然没有让整个测试环境变干净，但 benchmark 指定的 `F2P/P2P` 目标集确实全过了，所以 evaluator 判成 `resolved=true`。

#### 能力变化还是环境噪音

优先归类为：

- `contract_alignment_improved`
- `validation_better_targeted`

不是环境收益。

#### rerun 补充

同口径 rerun 里，这个 case 没有复现原始成功，而是直接掉回失败：

- `resolved = False`
- `FAIL_TO_PASS success = 0`, `failure = 2`
- `PASS_TO_PASS success = 2`, `failure = 0`

更关键的是，rerun 的 `cli_result.json` 和 `patch.diff` 都显示它再次被 `path_info.py` 的 Python 3.12 兼容问题吸走，只改了：

- `dvc/path_info.py`

并没有完成原始成功 run 那种真正的 `no_exec` 契约补齐。

这说明：

- 原始 `2.1.138` 在 `iterative` 上的成功不是稳定复现能力
- 至少有相当一部分是轨迹级非确定性
- 同一个模型、同一个 case，rerun 完全可能重新掉回错误主线

### 5.2 `dask__dask_2024.3.1_2024.4.0`

#### 当前状态

- `2.1.89`：`resolved = True`
- `2.1.138`：`resolved = True`

#### 概览

这不是新增 resolved case，但它说明 `2.1.138` 不是靠“多试多撞”拿到 `4/7`，因为在已经能解的 case 上，它反而更快更省。

#### 判断

这里是 **质量持平 + fault localization 更短**。

#### 证据

`2.1.89` patch：

- 同时改 `_value_counts`
- 再补 `_value_counts_aggregate`
- turns `71`
- cost `$5.37`

`2.1.138` patch：

- 只在 `_value_counts_aggregate` 里补 `if not data`
- turns `37`
- cost `$3.16`

两轮 evaluator 都是：

- `FAIL_TO_PASS success = 2`
- `PASS_TO_PASS success = 2747`

#### 为什么旧版错 / 新版对

这里不是“旧版错 / 新版对”，而是“都对，但新版更短”。

`2.1.138` 更像直接抓到了 `_value_counts_aggregate` 的核心空输入路径，而 `2.1.89` 多绕了一层 `_value_counts`。

#### 能力变化还是环境噪音

归类为：

- `localization_improved`

但这案本身不解释 `resolved +1`，只解释为什么 `2.1.138` 整体 turns 和时长下降。

#### rerun 补充

rerun 里的 `dask` 依然 resolved，所以这案更像稳定正例；但效率明显变差：

- 原始：`37 turns / $3.16`
- rerun：`64 turns / $7.37`

这说明：

- “能不能解出来”在 `dask` 上相对稳定
- “要花多少上下文和多少轮才解出来”并不稳定

### 5.3 `conan-io__conan_2.0.2_2.0.3`

#### 当前状态

- `2.1.89`：`resolved = False`
- `2.1.138`：`resolved = False`

#### 概览

这是 `2.1.138` 的最大成本黑洞。

#### 判断

这里是明显的 **`task_understanding_error` + `validation_gap`**，不是能力提升。

#### 证据

`2.1.138` 的 `cli_result.json` 一口气声称实现了多个 release-note 级特性：

- 新 `conan cache check-integrity`
- download cache fallback
- backup sources support

对应 cost：

- `2.1.89`：`$15.70`
- `2.1.138`：`$27.83`

但 evaluator 结果没有改善：

- `F2P success = 1`, `failure = 7`
- `P2P success = 315`, `failure = 2`

失败直接集中在：

- `backup_sources_test.py` 一串测试
- 少量 `PASS_TO_PASS` 回归

#### 为什么旧版错 / 新版对

这里没有“新版对”。

更准确地说，`2.1.138` 在这个 case 上把任务理解成了“顺手做一组 release-note 功能包”，而不是 benchmark 关心的最小修复面，所以成本大涨但结果没变。

#### 能力变化还是环境噪音

归类为：

- `task_understanding_error`
- `self_report_optimism`
- `validation_gap`

#### rerun 补充

rerun 里的 `conan` 不仅没变好，反而明显更差：

- `F2P 0.125 -> 0.0`
- `P2P 0.9937 -> 0.0789`
- `cost $27.83 -> $124.95`
- `turns 111 -> 364`

从 rerun 的 `cli_result.json` 看，它把任务进一步扩成了几十个 feature / bugfix 的大礼包，远远超出 benchmark 关心的最小修复面。

所以这次 rerun 的大幅退化，不是“环境偶然抖了一下”，而是明确的：

- `hypothesis_lock_in`
- `scope explosion`
- `validation_gap`

### 5.4 `pydantic__pydantic_v2.7.1_v2.7.2`

#### 当前状态

- `2.1.89`：`resolved = False`, `F2P = 0/3`, `P2P failure = 4181`
- `2.1.138`：`resolved = False`, `F2P = 0/3`, `P2P failure = 4181`

#### 概览

这是 `2.1.138` 没能把 `resolved` 从 `4` 推到更高的最大原因。

#### 判断

这里几乎完全不是能力提升，而是 **`environment_compatibility_break`** 持续存在。

#### 证据

`2.1.138` 的 `cli_result.json` 自报说：

- 目标 generics test 过了
- 一个 docs example 过了
- 另一个 docs example 只是 pre-existing black formatting issue

但 evaluator 不认，最终：

- `FAIL_TO_PASS failure = 3`
- `PASS_TO_PASS failure = 4181`

`test_output.txt` 里最硬的证据是：

- `[PdmException]: Resolving from lockfile failed`
- `collected 1019 items / 57 errors`

这说明它连正常的 collection 环境都没恢复，后面的几千条 P2P 失败主要是环境兼容崩溃扩散，不是几千个独立语义点都错了。

#### 为什么旧版错 / 新版对

这里两轮都没对。

`2.1.138` 只是在 turns、cost 上更省：

- turns `75 -> 48`
- cost `$5.13 -> $3.40`

但质量指标完全没动。

#### 能力变化还是环境噪音

归类为：

- `dependency_resolution_nondeterminism`
- `environment_compatibility_break`
- `self_report_optimism`

#### rerun 补充

rerun 的 `pydantic` 结果和原始 run 几乎完全一致：

- `F2P = 0/3`
- `P2P failure = 4181`

只是在成本和 turns 上更高：

- `$3.40 -> $4.71`
- `48 -> 63 turns`

这进一步说明：

- 这个 case 的失败不是一次偶发误差
- `2.1.138` 本身就没有稳定穿过 `pydantic` 的环境/依赖崩溃面

## 6. 根因排序

按影响大小排序：

1. `contract_alignment_improved`
   - 只发生在 `iterative`
   - 直接贡献了 `resolved 3 -> 4`

2. `localization_improved`
   - 体现在 `dask`
   - 不是新增 resolved，但显著减少 turns / cost

3. `task_understanding_error`
   - 体现在 `conan`
   - 让成本显著膨胀，但没有带来 resolved 收益

4. `environment / install / dependency noise`
   - 体现在 `pydantic`
   - 继续把 `F2P/P2P` 大头拖死

5. `validation_gap / self_report_optimism`
   - `2.1.89 iterative` 和 `2.1.138 pydantic` 都很典型
   - agent 自报与 evaluator 最终结论不一致

如果把 rerun 也算进来，排序要再补两点：

6. `trajectory nondeterminism`
   - 体现在 `iterative`
   - 原始 run 走上 `no_exec` 主线，rerun 又掉回 `path_info` 兼容线

7. `scope explosion`
   - 体现在 rerun `conan`
   - 同样的模型版本可以从“高成本但尚可”恶化成“超高成本且严重回归”

## 7. 最终判断

截至原始 `pc7-claude-2.1.138` 这轮本身，最实事求是的判断是：

- 这次 `resolved = 4/7` 不是“全面变强”
- 它的真实新增收益几乎全部来自 `iterative__dvc_1.0.0b6_1.0.0`
- 这更像一次可解释的 **接口契约对齐提升**
- 不是纯随机靠运气多解了一个 case

同口径 rerun 跑完以后，这个判断要修正成：

- 原始 `4/7` **不能**视为稳定能力
- rerun 最终只得到 `3/7`
- 丢掉的正是原始 run 多出来的那个 `iterative`
- 因此，原始 `2.1.138` 的新增第 4 个 resolved 至少部分依赖非确定性轨迹，不是稳态收益

更强一点的最终结论是：

- `2.1.138` 的“基础盘”稳定收益是 `3/7`
  - `dask`
  - `modin`
  - `requests`
- 原始那次冲到 `4/7`，主要是 `iterative` 恰好走上了正确契约修复线
- 但 rerun 证明这条线会重新掉回 `path_info` 兼容分支，所以不能把原始 `4/7` 当成可重复的稳定结论

同时，rerun 还暴露出另一个更坏的事实：

- `conan` 的轨迹波动非常大
- 同样是未 resolved，它可以从“高成本但基本不伤 P2P”恶化成“超高成本 + 明显 P2P 崩塌”

## 8. rerun 观察

同口径 direct rerun：

- run id：`20260511-202352-project-coverage-7-claude-2.1.138-rerun`
- display name：`pc7-claude-2.1.138-rerun`
- 外部日志：`/tmp/20260511-202352-project-coverage-7-claude-2.1.138-rerun.log`

这轮已经完整跑完。最终结果：

- `resolved = 3/7`
- `f2p micro = 40.9%`
- `p2p micro = 51.1249%`
- `cost = $154.36`
- `turns = 666`

最终 resolved case 只有：

- `dask`
- `modin`
- `requests`

相对原始 run：

- `iterative` 丢失
- `conan` 显著恶化
- `pydantic` 继续完全没改善

这轮过程中确实观察到与模型无关的外部噪音：

- `git fetch` 到 `github.com` 出现过 `curl 28` / `expected flush after ref listing`

但这些网络抖动并不足以解释最终结论，因为：

- `dask` 在同样有 fetch 抖动的前提下仍然 resolved
- `iterative` 的失败有明确的轨迹级证据：patch 再次偏到 `path_info.py`
- `conan` 的退化也有明确的轨迹级证据：过度扩张到几十个 feature / bugfix 打包修改

因此本轮最终判断是：

- 原始 `pc7-claude-2.1.138` 的 `4/7` 不是稳定可复现结果
- 更可信的稳态表现接近 `3/7`
- 那个额外的第 4 个 resolved，至少目前看，带有显著随机性
