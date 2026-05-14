# innerCC skill ablation：当前中间结论总览（2026-05-13）

## 1. 目标

当前要回答的核心问题只有两个：

1. `innercc_0509_context` 在 skill-on 实验里看到的收益，究竟有多少来自 **去掉 `--bare`**
2. `swebench-case-closer` 这个 skill 本身，到底是正向增强，还是只对部分 case 有用

为此，当前有 3 条关键 innerCC 线路：

### A. baseline

- `20260511-194955-project-coverage-7-innercc-context-router-rerun`
- 近似 `bare + no-skill`

### B. full + skill

- `20260513-153919-project-coverage-7-innercc-router`

### C. full + no-skill（隔离用户 skill）

- `20260513-164631-project-coverage-7-innercc-router`
- `CLAUDE_CONFIG_DIR=/tmp/codex-noskill-config`
- 首轮真实 router request 已确认 **没有** `swebench-case-closer`

## 2. 当前已经能确定的结论

### 2.1 大盘上：skill-on 不是成功率银弹

`full + skill` 相比 baseline：

- `resolved_true_cases`: `3 -> 3`
- `f2p_micro`: `40.9% -> 40.9%`
- `p2p_micro`: `54.3% -> 51.1%`
- `cache_hit`: `10.2% -> 35.4%`

这意味着：

- 成功率没有提升
- cache-friendliness 显著提升

所以至少可以排除一个错误结论：

- 不能说“这个 skill 已经证明能提高 innerCC 的最终成功率”

### 2.2 `dask` 已经证明：主效应几乎全是去掉 `--bare`

在 `dask__dask_2024.3.1_2024.4.0` 上：

| mode | resolved | turns | input tok | cache hit | cost |
| --- | ---: | ---: | ---: | ---: | ---: |
| `bare + no-skill` | `true` | `109` | `3.67M` | `9.88%` | `$11.77` |
| `full + skill` | `true` | `29` | `315k` | `63.11%` | `$1.28` |
| `full + no-skill` | `true` | `29` | `315k` | `63.93%` | `$1.27` |

这个 case 的结论非常硬：

- `full + skill` 和 `full + no-skill` 几乎完全一样
- 所以在 `dask` 上，收益不是 skill 带来的
- 几乎全部来自：**去掉 `--bare`**

### 2.3 `conan` 已经显示出相反模式：skill 可能有害

当前 `conan` 上：

#### `bare + no-skill`

- `resolved = false`
- `f2p = 0/8`
- `p2p_failure = 2`

#### `full + skill`

- `resolved = false`
- `f2p = 0/8`
- `p2p_failure = 291`
- `error_max_turns`

#### `full + no-skill`

还没收口，但当前 session trace 已经表明：

- 轨迹形态和 `full + skill` 完全不同
- skill-on 不是简单“更快”
- 更像“更快地走向一条坏路径”

所以在 `conan` 上：

- 这个 skill 至少当前版本有明显风险

## 3. 这三条结论合起来说明什么

把 `dask` 和 `conan` 放在一起看，已经能得到比“大盘汇总”更清楚的判断：

### 结论 A：`--bare` 是一个非常强的混杂因素

如果不把 `--bare` 去掉，你们很容易高估 skill 对 cache hit 的贡献。

因为在 `dask` 上已经清楚看到：

- bare -> full

本身就足以把：

- `109 turns`
- `3.67M input`
- `9.88% hit`

变成：

- `29 turns`
- `315k input`
- `~63% hit`

### 结论 B：skill 不是“全局有效”增强，而是 case-family dependent 干预

至少到目前为止：

- `dask`: skill 几乎没额外收益
- `conan`: skill 可能有害

这意味着更合理的 framing 是：

- skill 对不同 case family 的作用不同

而不是：

- skill 全局提高成功率

### 结论 C：当前 skill 更像“工作流收缩器”

它更擅长做的是：

- 缩短轨迹
- 降低搜索宽度
- 提高 cache-friendliness

但这未必等于：

- 提高最终任务成功率

在 `dask` 这种窄目标问题上，缩短轨迹不伤结果；在 `conan` 这种宽表面问题上，缩短轨迹反而可能让 agent 更快走错。

## 4. 现在最值得做的，不是继续扩面

当前已经有两类很清晰的信号：

1. 一个 case（`dask`）证明了“去 bare 是主效应”
2. 一个 case（`conan`）暴露了“skill 可能有害”

所以，下一步最有价值的事情不是再跑更多花样，而是：

### 路线 1：等 `full + no-skill` 控制组收完

这一步是必要的，因为只有这样才能：

- 在 `conan / scikit / pydantic` 上真正拆开 `full + skill` vs `full + no-skill`

### 路线 2：给 skill 加 case-family gate

如果后续 `conan` 控制组证明 `full + no-skill` 好于 `full + skill`，就说明：

- 这个 skill 不能默认全局启用

更合理的方案是：

- 对 `dask / requests` 这类窄目标 case 启用
- 对 `conan` 这类宽表面、多分支 case 降权或禁用

## 5. 当前最合理的中间总结

如果现在就要一句高置信判断，我会写成：

- `innercc skill-on` 看到的大部分 cache hit 改善，很可能来自去掉 `--bare`；而 `swebench-case-closer` 作为 skill，本身更像一个会改变探索风格的定向干预，它对某些窄目标 case 基本无害，但对 `conan` 这类宽表面 case 可能有明显副作用。  
