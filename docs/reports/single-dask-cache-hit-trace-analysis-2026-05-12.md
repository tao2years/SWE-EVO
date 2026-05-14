# single-dask：为什么 Claude Code 缓存命中更高（基于真实 LLM Router traces，2026-05-12）

## 1. 问题与范围

本文只回答一个非常具体的问题：

- 在同一个 case `dask__dask_2024.3.1_2024.4.0` 上，为什么 `Claude Code` 的缓存命中显著高于 `innercc_0509_context`？

本次只分析两条单 case run：

| label | run id | cli |
| --- | --- | --- |
| `single-dask-claude-router` | `20260512-164502-cache-trace-dask-1-claude-router` | `claude` |
| `single-dask-innercc-0509-context-router` | `20260512-163036-cache-trace-dask-1-innercc-router` | `/home/wt/sss_repos/innerCC/innercc_0509_context` |

数据源：

- [official48_runs/20260512-164502-cache-trace-dask-1-claude-router/analysis/summary.json](/home/wt/sss_repos/sss_auto/SWE-EVO-subset-run/official48_runs/20260512-164502-cache-trace-dask-1-claude-router/analysis/summary.json:1)
- [official48_runs/20260512-163036-cache-trace-dask-1-innercc-router/analysis/summary.json](/home/wt/sss_repos/sss_auto/SWE-EVO-subset-run/official48_runs/20260512-163036-cache-trace-dask-1-innercc-router/analysis/summary.json:1)
- 两边的 `cli_result.json`
- 两边的 `router_trace_bundle.json`
- 两边的 `patch.diff`

## 2. 先给结论

结论不是“Claude Code 更会用缓存”这么空泛，而是下面四件事叠加：

1. `Claude Code` 的**首轮可缓存前缀显著更大**。
2. `Claude Code` 的**轨迹显著更短**，新增 token 更少。
3. `innercc_0509_context` 的**工具调用和错误回合更多**，导致 observation token 累积更快。
4. `Claude Code` 更快命中正确修复点，**任务更早收敛**；缓存命中高既是 prompt/runtime 现象，也是任务收敛质量的结果。

把这四点压成一句话：

- `Claude Code = 大稳定前缀 + 短轨迹`
- `innercc_0509_context = 小稳定前缀 + 长轨迹`

## 3. 先澄清一个容易误判的点：innercc 原始 trace bundle 被旧 session 污染了

如果直接看原始 `router_trace_bundle.json`：

- `innercc` 会显示 `251` 条 traces
- 而 `Claude Code` 只有 `41` 条 traces

但这里有一个重要陷阱：

- `innercc` 的原始 bundle 里混进了多个历史 `x-claude-code-session-id`
- 不能直接把 `251` 当成“这一次单 case run 的真实请求数”

具体看原始 bundle 中的 `x-claude-code-session-id` 分布：

- `6fefbbd0-05cf-46df-a2ca-fd6e066d25eb`: `30`
- `d420fa5a-fd85-4b02-babc-c95d3f67962f`: `83`
- `1c72c512-2c7c-4317-a5a6-2a9284bcedcd`: `22`
- `d33b76d6-dae3-4ace-af0d-79a06d465ab9`: `33`
- `df5577aa-c46c-493c-aeb1-974e0648b5b3`: `83`

而这次单 case run 的真实 `session_id` 在 `cli_result.json` 里写得很清楚：

- `innercc`: `df5577aa-c46c-493c-aeb1-974e0648b5b3`
- `claude`: `835bd535-e3fb-4672-847c-47fbb32ed60b`

所以，后面的 trace 级分析统一只使用：

- `innercc`: 过滤出 `x-claude-code-session-id == df5577aa-c46c-493c-aeb1-974e0648b5b3`
- `claude`: 过滤出 `x-claude-code-session-id == 835bd535-e3fb-4672-847c-47fbb32ed60b`

过滤后：

- `innercc` 当前 session 的真实 trace 数是 `83`
- `claude` 当前 session 的真实 trace 数是 `41`

这和 `cli_result.num_turns` 也更一致：

- `innercc`: `86` turns
- `claude`: `41` turns

## 4. run 级 KPI：你给的表本身已经说明了问题规模

| metric | `single-dask-claude-router` | `single-dask-innercc-0509-context-router` |
| --- | ---: | ---: |
| `resolved` | `1` | `0` |
| `f2p micro` | `100.0%` | `0.0%` |
| `p2p micro` | `100.0%` | `100.0%` |
| `total cost` | `$3.30` | `$7.81` |
| `avg duration` | `3.3 min` | `10.1 min` |
| `total turns` | `41` | `86` |
| `input tok` | `502k` | `2410k` |
| `output tok` | `7.5k` | `30.7k` |
| `cache hit` | `64.4%` | `12.0%` |

直接含义：

1. `innercc` 的输入 token 是 `Claude` 的约 `4.8x`
2. `innercc` 的 turns 是 `Claude` 的约 `2.1x`
3. `innercc` 的成本是 `Claude` 的约 `2.4x`
4. `Claude` 不仅命中率更高，而且真正把 case 解出来了

所以这不是“只看缓存，不看质量”的假象。

## 5. trace 级核心差异 1：Claude 的首轮可缓存前缀更大

从当前 session 的真实 traces 看首轮：

### `innercc_0509_context`

- 首轮 `request_body` 大小：`20,590` bytes
- 首轮 `cache_creation_input_tokens`: `4,892`
- 第 2 轮开始 `cache_read_input_tokens` 基本稳定在：`4,017`

### `Claude Code`

- 首轮 `request_body` 大小：`106,263` bytes
- 首轮 `cache_creation_input_tokens`: `24,153`
- 第 2 轮开始 `cache_read_input_tokens` 基本稳定在：`22,678`

这说明：

- `Claude Code` 建立了一个大约 `22.7k` token 的可复用前缀
- `innercc` 建立的可复用前缀只有大约 `4.0k` token

这是缓存命中率差异的第一原因，而且是最直接的原因。

## 6. trace 级核心差异 2：Claude 的系统提示和工具前缀更“贵”，但也更“值钱”

看首轮请求结构：

### `innercc_0509_context`

- `tools`: `3`
  - `Bash`
  - `Edit`
  - `Read`
- `system blocks`: `3`
- `system` 文本总长度：约 `705` chars
- `user` 文本总长度：约 `3183` chars

### `Claude Code`

- `tools`: `23`
- `system blocks`: `3`
- `system` 文本总长度：约 `26,341` chars
- `user` 文本总长度：约 `5,784` chars

这意味着一个很反直觉但非常关键的点：

- 更“小”的 prompt，不一定有更高 `cache_hit_rate`

原因是这类 provider/router 口径的缓存，本质上奖励的是：

- **大而稳定的前缀**

`innercc` 的 bare/simple 设计让它的初始请求更轻，但也把**可缓存的稳定头部**缩得很小。结果是：

- 后续每轮只能稳定读回约 `4k` token

反过来，`Claude Code` 的 system prompt、skills、tool schemas 很大，但它们足够稳定，于是：

- 后续每轮能稳定读回约 `22.7k` token

所以在这个指标上：

- `Claude` 的“大前缀”反而更占优

## 7. trace 级核心差异 3：Claude 的轨迹更短，新增 token 累积更慢

看代表性 turn 的 `input_tokens / cache_read_input_tokens`：

### `innercc_0509_context`

| turn | input | cache_read | hit |
| --- | ---: | ---: | ---: |
| `1` | `1216` | `4017` | `76.8%` |
| `10` | `8027` | `4017` | `33.4%` |
| `20` | `17230` | `4017` | `18.9%` |
| `30` | `22618` | `4017` | `15.1%` |
| `40` | `26859` | `4017` | `13.0%` |
| `60` | `40268` | `4017` | `9.1%` |
| `80` | `57570` | `4017` | `6.5%` |

### `Claude Code`

| turn | input | cache_read | hit |
| --- | ---: | ---: | ---: |
| `1` | `1866` | `22678` | `92.4%` |
| `10` | `6816` | `22678` | `76.9%` |
| `20` | `11377` | `22678` | `66.6%` |
| `30` | `18048` | `22678` | `55.7%` |
| `40` | `26871` | `22678` | `45.8%` |

你可以看到：

- 两边都会随着对话变长而掉 hit
- 但 `innercc` 掉得快得多

本质原因不是公式有问题，而是：

- `innercc` 的可读缓存只有 `4k`
- 但每一轮新增输入一直在长

一旦新增输入大于可复用前缀很多倍，`cache_hit_rate = read / (input + read)` 就会迅速塌掉。

## 8. trace 级核心差异 4：innercc 的工具往返和错误回合明显更多

当前 session 的真实轨迹：

### `innercc_0509_context`

- `83` traces
- `85` assistant tool calls
- 请求里累计出现的 `tool_result` blocks: `3646`
- 其中 `is_error=true` 的 `tool_result`: `355`

### `Claude Code`

- `41` traces
- `40` assistant tool calls
- 请求里累计出现的 `tool_result` blocks: `820`
- 其中 `is_error=true` 的 `tool_result`: `110`

这意味着：

1. `innercc` 走了更多回合
2. `innercc` 把更多 tool observations 带回了后续上下文
3. `innercc` 有更多错误分支和重试分支

这三点都会进一步拉低缓存命中，因为它们共同抬高了：

- `new input tokens per turn`

## 9. trace 级核心差异 5：这次当前 session 没有发生 reset/shrink，问题不是 compact

这是这次分析里最重要的一个边界条件。

在 `current session` 过滤后：

- `innercc`：**没有** `request shrink`
- `claude`：也没有 `request shrink`

所以：

- 这次单 case run 里的缓存差异，**不是**由中途 compact / history rewrite 导致的

这点和我们之前另一个历史 `dask` 样例不同。

也就是说，你们至少已经看到两类不同机制：

1. 历史某些 run：共享长前缀后，中途 reset/shrink，打断缓存
2. 这次当前 run：没有 reset，但 `innercc` 从一开始就只有很小的可缓存前缀，且后续轨迹更长

当前这题属于第 2 类。

## 10. 质量与缓存是耦合的：Claude 更快命中正确修复点

最终 patch 也说明了为什么 `Claude` 更早收敛：

### `innercc`

```diff
if not x.groups or all(...):
    return x.value_counts(**kwargs)
```

它把问题理解成：

- `_value_counts` 在全 NaN partition 时返回空 `Series(dtype=int)`，结构不对

### `Claude`

```diff
if not data:
    return pd.Series([], dtype=int, name="count")
```

它把问题理解成：

- `_value_counts_aggregate` 在 `data == {}` 时直接走到了 `pd.concat({})`

从 benchmark 结果看：

- `Claude` 的定位命中了真正的 failing path
- `innercc` 命中了一个相邻但不足以修复 F2P 的 path

这件事和缓存直接相关：

- 更快命中正确路径 → 更少搜索 → 更少工具调用 → 更少 observation token → 更高缓存命中率

所以：

- 高命中率不是独立于任务质量的纯 infra 现象
- 它和 agent 的任务收敛质量是耦合的

## 11. 为什么这次是 Claude 高命中，innercc 低命中

把所有证据压到一起，这次 case 的根因链可以写成：

### `Claude Code`

`大稳定前缀 (~22.7k read) + 少回合 (41 turns) + 更快命中正确修复点 + 更少工具/错误回合`

### `innercc_0509_context`

`小稳定前缀 (~4.0k read) + 多回合 (86 turns / 83 trace requests) + 更多 Bash/Read 与错误回合 + 任务命中点偏移`

于是最终得到：

- `Claude cache hit = 64.4%`
- `innercc cache hit = 12.0%`

## 12. 对 innercc 的直接建议

这次 case 给出的建议很具体：

1. **不要只追求更小首轮 prompt**
   - 如果系统/工具头部太小，后续能读回的缓存也会太小

2. **把“稳定头部”做大、做稳**
   - 当前 bare/simple 模式下只有 `Bash/Edit/Read`
   - 从缓存角度看，这会让首轮 `cache_creation_input_tokens` 太低

3. **更早收敛比单纯 prompt 压缩更重要**
   - 这次 `innercc` 的核心问题不是“有 compact”
   - 而是“定位没打中，回合拉长”

4. **工具错误分支要更快止损**
   - `355` 个 error tool_result 级别的回流太高
   - 这会快速放大 observation token

5. **分析 raw router bundle 时必须按 `cli_result.session_id` 过滤**
   - 否则很容易把历史会话混进来，误判 trace 数和 reset 事件

## 13. 一句话收束

这次单 case 里，`Claude Code` 缓存命中高，不是因为它“更省 token”，而是因为它：

- **先建立了一个更大的稳定可缓存前缀**
- **再用更短的轨迹完成任务**

而 `innercc_0509_context` 的问题是：

- **可缓存前缀太小**
- **轨迹太长**
- **工具错误分支太多**
- **最终还没有命中正确修复点**

所以这题最准确的结论不是“innercc 不会缓存”，而是：

- `innercc` 当前 runtime 让**可复用前缀太小**，同时又让**新增上下文增长太快**。
