# official48 快速验证子集建议

## 背景与主线收益句

当前主线是“用比 full official48 更小的集合，快速验证 CLI 的定位、编辑、验证和收敛能力”。  
这份子集方案的直接收益是：后续每轮不必再跑完整 `48` 案，也不必临时手工挑题，而是可以按固定集合做低成本回归。

## 当前目标、阶段、下一刀

- 当前目标：
  - 从 `docs/bad_case_analysis/` 已分析的 `48` 案里，按项目和错误根因挑出一组低成本、代表性足够的 case。
- 当前阶段：
  - 已完成 case 筛选与分组。
- 下一刀：
  - 先跑 `config/subsets/quick-smoke-5.txt`；
  - 如果结果可用，再扩到 `config/subsets/project-coverage-7.txt`。

## 选取方法

本次只用仓库内现有证据，不依赖已经移出的 raw run 目录。

使用的筛选信号：

- `docs/bad_case_analysis/*_analysis.md` 中的：
  - `comparison_category`
  - 根因标签
  - `FAIL_TO_PASS` / `PASS_TO_PASS`
  - `cli_duration_ms`
  - `cli_num_turns`
- 额外约束：
  - 优先 `FAIL_TO_PASS <= 4` 的小题
  - 优先历史 `cli_duration_ms` 更低的题
  - 每个项目优先保留 `1` 个主选；必要时再给 `1` 个备选
  - 对明显的大 bundle（如 `72+` F2P、`132+` F2P、`2774` F2P）默认降权，除非该项目没有更轻量代表

说明：

- 下文的“耗时”统一用历史两个 CLI 的 `cli_duration_ms` 区间做 proxy。
- 这不是完整端到端 wall time；真实总时长还会受镜像缓存、repo clone、evaluator 和 Docker 状态影响。
- 但在当前仓库里，这是最稳定、可横向比较的成本口径。

## 项目主选 / 备选

| 项目 | 主选 case | 备选 case | 主要根因 / 价值 | 历史耗时 proxy |
| --- | --- | --- | --- | --- |
| `psf/requests` | [psf__requests_v2.27.0_v2.27.1_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/psf__requests_v2.27.0_v2.27.1_analysis.md) | [psf__requests_v2.9.0_v2.9.1_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/psf__requests_v2.9.0_v2.9.1_analysis.md) | 主选是小而稳的 reference success；备选是典型 `overgeneralized_fix + validation_gap` | 主选 `2.3-9.8` 分钟；备选 `3.5-5.7` 分钟 |
| `dask/dask` | [dask__dask_2024.3.1_2024.4.0_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/dask__dask_2024.3.1_2024.4.0_analysis.md) | [dask__dask_2023.9.2_2023.9.3_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/dask__dask_2023.9.2_2023.9.3_analysis.md) | 主选是最典型的小题 `localization_error`；备选是小规模 partial-fix / validation case | 主选 `1.6-11.7` 分钟；备选 `4.2-9.1` 分钟 |
| `iterative/dvc` | [iterative__dvc_1.0.0b6_1.0.0_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_1.0.0b6_1.0.0_analysis.md) | [iterative__dvc_3.15.0_3.15.1_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/iterative__dvc_3.15.0_3.15.1_analysis.md) | 主选是 DVC 最有代表性的“外部契约 vs 内部语义错层”；备选是低成本 reference success | 主选 `4.7-12.3` 分钟；备选 `3.4-5.0` 分钟 |
| `pydantic/pydantic` | [pydantic__pydantic_v2.7.1_v2.7.2_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/pydantic__pydantic_v2.7.1_v2.7.2_analysis.md) | [pydantic__pydantic_v2.6.0b1_v2.6.0_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/pydantic__pydantic_v2.6.0b1_v2.6.0_analysis.md) | 主选覆盖 `task_understanding_error + termination_error`；备选是单 F2P 的局部定位题，但历史耗时波动较大 | 主选 `2.7-7.6` 分钟；备选 `0.3-20.4` 分钟 |
| `scikit-learn/scikit-learn` | [scikit-learn__scikit-learn_0.20.1_0.20.2_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/scikit-learn__scikit-learn_0.20.1_0.20.2_analysis.md) | [scikit-learn__scikit-learn_0.21.1_0.21.2_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/scikit-learn__scikit-learn_0.21.1_0.21.2_analysis.md) | 这是最便宜的 `F2P 通过但 P2P 回归` 验证点 | 主选 `1.2-3.6` 分钟；备选 `3.5-12.4` 分钟 |
| `modin-project/modin` | [modin-project__modin_0.27.0_0.27.1_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/modin-project__modin_0.27.0_0.27.1_analysis.md) | [modin-project__modin_0.24.0_0.24.1_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/modin-project__modin_0.24.0_0.24.1_analysis.md) | 主选是小而尖的 reference success；备选是单 F2P `localization_error`，但更贵 | 主选 `5.0-15.3` 分钟；备选 `13.7-20.4` 分钟 |
| `conan-io/conan` | [conan-io__conan_2.0.2_2.0.3_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/conan-io__conan_2.0.2_2.0.3_analysis.md) | [conan-io__conan_2.0.14_2.0.15_analysis.md](/home/wt/sss_repos/sss_auto/SWE-EVO/docs/bad_case_analysis/conan-io__conan_2.0.14_2.0.15_analysis.md) | Conan 没有真正便宜的案子；主选已经是相对更小的 `8 F2P` bundle，备选 `72 F2P` 只适合扩展压测 | 主选 `15.9-26.8` 分钟；备选 `13.6-14.5` 分钟但任务面明显更大 |

## 推荐组合

### 1. 最小快验 5

manifest:

- [config/subsets/quick-smoke-5.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/config/subsets/quick-smoke-5.txt)

包含：

1. `psf__requests_v2.27.0_v2.27.1`
2. `dask__dask_2024.3.1_2024.4.0`
3. `iterative__dvc_1.0.0b6_1.0.0`
4. `pydantic__pydantic_v2.7.1_v2.7.2`
5. `scikit-learn__scikit-learn_0.20.1_0.20.2`

用途：

- 用最少 case 覆盖 5 类最关键能力：
  - reference success
  - localization
  - external-contract alignment
  - termination / task sizing
  - F2P through but P2P regression

耗时 proxy：

- 历史 CLI 时长总和约 `12.6-45.1` 分钟

适用时机：

- 你的 CLI 刚改完主干策略
- 先看“有没有明显退化 / 是否至少修到几个高信号小题”

### 2. 项目覆盖 7

manifest:

- [config/subsets/project-coverage-7.txt](/home/wt/sss_repos/sss_auto/SWE-EVO/config/subsets/project-coverage-7.txt)

在 `最小快验 5` 基础上再加入：

6. `modin-project__modin_0.27.0_0.27.1`
7. `conan-io__conan_2.0.2_2.0.3`

用途：

- 每个项目至少 `1` 个代表 case
- 保留低成本优先原则，但补上 `modin` 和 `conan`

耗时 proxy：

- 历史 CLI 时长总和约 `33.4-87.1` 分钟

适用时机：

- 你已经通过 `最小快验 5`
- 需要看“跨 repo 泛化”而不是只看轻量项目

### 3. 二阶段扩展建议

如果 `项目覆盖 7` 的结果已经稳定，再按下面顺序增量加题：

1. `psf__requests_v2.9.0_v2.9.1`
   - 便宜，适合专门检验 `overgeneralized_fix`
2. `dask__dask_2023.9.2_2023.9.3`
   - 便宜，适合看 partial fix / validation 质量
3. `iterative__dvc_3.15.0_3.15.1`
   - 便宜，适合补一个 DVC success anchor

不建议在“快速验证”阶段优先加入的 case：

- `dask__dask_2024.1.0_2024.1.1`
  - `2774` 条 F2P，任务面过大
- `iterative__dvc_0.52.1_0.53.1`
  - `132` 条 F2P，还是典型 bundle + patch pollution
- `conan-io__conan_2.0.14_2.0.15`
  - `72` 条 F2P，即使历史 CLI 时间不算极端，任务复杂度也明显不适合快验
- `pydantic__pydantic_v2.7.0_v2.7.1`
  - `234` 条 F2P，成本和噪声都偏大

## 使用方式

当前 runner 直接消费的是 `--instances-dir <dir>`，不是 manifest 文件本身。  
建议按下面方式把 manifest 物化成一个临时目录：

```bash
SUBSET_NAME=quick-smoke-5
SRC_DIR="$PWD/official48_source/output_final"
DST_DIR="$PWD/tmp/$SUBSET_NAME"

rm -rf "$DST_DIR"
mkdir -p "$DST_DIR"

while read -r instance_id; do
  cp "$SRC_DIR/$instance_id.json" "$DST_DIR/"
done < "$PWD/config/subsets/$SUBSET_NAME.txt"
```

然后直接把这个目录喂给推理入口：

```bash
python3 run_innercc_infer_official48.py \
  --instances-dir "$DST_DIR" \
  --output-dir "$PWD/official48_runs/${SUBSET_NAME}-$(date +%Y%m%d-%H%M%S)/infer" \
  --cli-bin /path/to/your-cli \
  --settings-file /path/to/settings.json \
  --env-file /path/to/env.file \
  --model your-model \
  --agent-name your-agent \
  --max-concurrency 2 \
  --force-workspace
```

如果还要接评测 worker / 汇总脚本，再把同一份子集目录复制到仓库根的 `output_final/`，因为当前 `record_official48_progress.py` / `summarize_official48_run.py` 默认从仓库根目录读取实例清单。

## 结论

如果只想尽快得到“这轮 CLI 改动到底有没有正向效果”的答案，先跑：

1. `quick-smoke-5`
2. 通过后再跑 `project-coverage-7`

这两层已经能覆盖：

- 主要小题定位能力
- 外部契约对齐
- P2P 回归控制
- 终止条件是否靠谱
- 主要项目面的跨 repo 泛化
