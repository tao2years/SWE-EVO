# dask：`innercc_0509_context` 的 `bare` / `full+skill` / `full+no-skill` 三方消融（2026-05-13）

## 1. 为什么单独拿 `dask` 做三方消融

`project-coverage-7` 的完整 no-skill 控制组还在跑，但 `dask__dask_2024.3.1_2024.4.0` 已经先完成了。

这个 case 足够回答当前最关键的问题：

- `innercc` 在 skill-on 实验里看到的改善，究竟主要来自：
  - 去掉 `--bare`
  - 还是来自 `swebench-case-closer` skill 本身

因为 `dask` 同时满足：

1. baseline 是成功 case
2. `full + skill` 也是成功 case
3. `full + no-skill` 也已经成功

所以它是一个干净的控制点。

## 2. 三个对比对象

### A. `bare + no-skill`

- run: `20260511-194955-project-coverage-7-innercc-context-router-rerun`
- case: `dask__dask_2024.3.1_2024.4.0`

### B. `full + skill`

- run: `20260513-153919-project-coverage-7-innercc-router`
- case: `dask__dask_2024.3.1_2024.4.0`

### C. `full + no-skill`

- run: `20260513-164631-project-coverage-7-innercc-router`
- case: `dask__dask_2024.3.1_2024.4.0`
- 通过 `CLAUDE_CONFIG_DIR=/tmp/codex-noskill-config` 隔离用户级 skill
- 首轮真实 request 已确认 **没有** `swebench-case-closer`

## 3. 最终结果一览

| mode | resolved | f2p | p2p failure | turns | input tok | cache read tok | cache hit | cost |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `bare + no-skill` | `true` | `2/2` | `0` | `109` | `3,666,118` | `401,721` | `9.88%` | `$11.77` |
| `full + skill` | `true` | `2/2` | `0` | `29` | `315,750` | `540,147` | `63.11%` | `$1.28` |
| `full + no-skill` | `true` | `2/2` | `0` | `29` | `315,748` | `559,634` | `63.93%` | `$1.27` |

这个表已经足够说明核心事实：

1. 三种模式都能把 `dask` 解出来
2. `bare -> full` 带来了**巨大**的效率与缓存收益
3. `full + skill` 和 `full + no-skill` 之间几乎没有差异

## 4. 先给结论

在 `dask` 这个 case 上：

- **去掉 `--bare` 是主效应**
- **skill 几乎没有提供额外收益**

更强一点说：

- 在这个 case 上，`innercc` 从 `109 turns / 9.9% cache hit` 变成 `29 turns / ~63% cache hit`，几乎完全可以由“从 bare 切到 full”解释
- `skill-on` 并没有把 `full + no-skill` 再往前推

## 5. 真实 trace 也支持这个结论

### `bare + no-skill`

- 当前 session traces: `100`
- 首轮：
  - `msg_count = 1`
  - `request_body = 20,604 bytes`
  - `cache_creation_input_tokens = 1,054`
  - `cache_read_input_tokens = 3,840`
- 末轮：
  - `msg_count = 199`
  - `request_body = 333,151 bytes`
  - `input_tokens = 76,706`
  - `cache_read_input_tokens = 4,019`

这说明：

- bare 模式下稳定可缓存前缀非常小
- 后续只能稳定读回约 `4k` tokens

### `full + skill`

- 当前 session traces: `28`
- 首轮：
  - `msg_count = 1`
  - `request_body = 91,050 bytes`
  - `cache_creation_input_tokens = 6,568`
  - `cache_read_input_tokens = 13,998`
- 末轮：
  - `msg_count = 55`
  - `request_body = 177,932 bytes`
  - `input_tokens = 22,434`
  - `cache_read_input_tokens = 19,487`

### `full + no-skill`

- 当前 session traces: `29`
- 首轮：
  - `msg_count = 1`
  - `request_body = 90,603 bytes`
  - `cache_creation_input_tokens = 6,467`
  - `cache_read_input_tokens = 13,998`
- 末轮：
  - `msg_count = 57`
  - `request_body = 175,234 bytes`
  - `input_tokens = 22,311`
  - `cache_read_input_tokens = 19,487`

这个对比几乎是“镜像”的：

- `full + skill` 和 `full + no-skill` 的首轮缓存建立规模几乎一样
- 后续每轮稳定读回的缓存量也几乎一样
- 连最终轨迹长度都只差 `1` 条 trace

这基本排除了“skill 本身显著改变了 cache 行为”的可能。

## 6. 最终 patch 也几乎一样

### `full + no-skill`

```diff
if not data:
    return pd.Series(dtype=int)
```

### `full + skill`

```diff
if not data:
    return pd.Series(dtype=int)
...
if len(res) == 0:
    return res
```

两者都已经命中到了正确的 aggregate 路径，而不是旧的 `_value_counts` 相邻路径。

差别只在于：

- `skill-on` 多补了一层 `len(res) == 0` 防御

但这层没有带来 benchmark 结果上的额外收益。

## 7. 对 `innercc` 的直接解释

这次 `dask` 三方消融可以很明确地说明：

### 7.1 `--bare` 是主要问题

在 bare 模式下：

- 可缓存前缀太小
- 轨迹太长
- 搜索过度展开

所以：

- turns 高
- input tokens 高
- cache hit 低

### 7.2 skill 不是这个 case 的关键变量

一旦切到 full：

- 无 skill 就已经能到 `29 turns / 63.9% cache hit`
- 加 skill 后只是变成 `28-29 traces / 63.1% cache hit`

所以：

- 这个 case 上 skill 不是主效应

## 8. 这意味着什么

你们前面在 `pc7 skill-on` 大盘上看到的：

- `innercc cache hit: 10.2% -> 35.4%`

现在已经可以做更严谨的解释了：

- 至少在 `dask` 这个成功样本上，这个提升几乎完全来自**去掉 bare**
- skill 本身几乎没有额外贡献

这也解释了为什么大盘里：

- `cache hit` 变好了
- 但 `resolved` / `f2p` 没变

因为 runner 改善了 prompt/cache 结构，但 skill 没有在这个 case 上显著提高解题能力。

## 9. 最关键的下一步

如果你们要验证 skill 是否真的有价值，下一步不要再看 `dask` 这种“full 一开就恢复正常”的 case，而要看：

1. `conan`
2. `scikit`
3. `iterative`

这些才是 skill 更可能产生差异的地方。

换句话说：

- `dask` 主要验证的是 `--bare` 的伤害
- 不是验证 skill 本身的上限

## 10. 一句话收束

在 `dask__dask_2024.3.1_2024.4.0` 上，`innercc` 从 `109 turns / 9.9% cache hit` 变成 `29 turns / ~63% cache hit`，**几乎完全是去掉 `--bare` 的收益**；`swebench-case-closer` 这个 skill 在这个 case 上几乎没有带来额外提升。  
