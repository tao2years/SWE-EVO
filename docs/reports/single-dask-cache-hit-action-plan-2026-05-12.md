# single-dask：缓存命中差异的工程归因与改造清单（2026-05-12）

## 1. 这次对比里，哪些差异是“产品真实差异”，哪些是“调用方式差异”

先把边界说清楚。

这次 `single-dask` 对比并不是完全 apples-to-apples，因为同一套 runner 对 `claude` 和 `innercc` 的调用参数不对称：

- `claude` 调用：
  - `-p`
  - `--no-session-persistence`
  - `--output-format json`
  - `--dangerously-skip-permissions`
  - `--settings`
  - `--model`

- `innercc_0509_context` 调用：
  - `--bare`
  - `-p`
  - `--no-session-persistence`
  - `--output-format json`
  - `--dangerously-skip-permissions`
  - `--settings`
  - `--model`

证据见：

- [custom_cli_case/run_custom_cli_case.py](/home/wt/sss_repos/sss_auto/SWE-EVO-subset-run/custom_cli_case/run_custom_cli_case.py:235)
- `innercc` 分支会额外加 `--bare`：[custom_cli_case/run_custom_cli_case.py](/home/wt/sss_repos/sss_auto/SWE-EVO-subset-run/custom_cli_case/run_custom_cli_case.py:252)

而 `--bare` 在 `innerCC` 里会打开 `CLAUDE_CODE_SIMPLE=1`：

- [src/main.tsx](/home/wt/sss_repos/innerCC/src/main.tsx:1023)
- [src/constants/prompts.ts](/home/wt/sss_repos/innerCC/src/constants/prompts.ts:450)

这会直接把 system prompt 切到极简模式：

```ts
if (isEnvTruthy(process.env.CLAUDE_CODE_SIMPLE)) {
  return [
    `You are Claude Code, Anthropic's official CLI for Claude.\n\nCWD: ${getCwd()}\nDate: ${getSessionStartDate()}`,
  ]
}
```

所以，这次对比里有两层差异：

1. **产品/runtime 差异**
   - `Claude Code` 与 `innerCC 2.1.88 context build` 的真实行为差异

2. **调用方式差异**
   - `innercc` 被强制跑在 `--bare/simple` 模式
   - `claude` 跑的是完整模式

如果不把这两层拆开，后面很容易得出错误结论。

## 2. 可以确定归因到 runner 的部分

### 2.1 首轮可缓存前缀差异，首先来自 `--bare`

当前 session 过滤后：

### `innercc`

- `tools = 3`
  - `Bash`
  - `Edit`
  - `Read`
- `system` 文本长度约 `705` chars
- 首轮 `cache_creation_input_tokens = 4892`
- 后续稳定 `cache_read_input_tokens ≈ 4017`

### `claude`

- `tools = 23`
- `system` 文本长度约 `26341` chars
- 首轮 `cache_creation_input_tokens = 24153`
- 后续稳定 `cache_read_input_tokens ≈ 22678`

这不是偶然，而是 `--bare/simple` 的直接后果。

也就是说：

- 这次 `single-dask` 里，`innercc` 的低 cache hit **一部分**是 runner 人为放大的

### 2.2 这意味着当前对比更像“极简 innercc vs 完整 Claude”

所以这次数据更适合回答：

- 在当前 benchmark 跑法下，为什么 `innercc --bare` 的缓存命中显著更差？

而不适合直接回答：

- 去掉所有调用差异后，`innercc` 的缓存能力是否仍然显著差于 `Claude`？

后者还需要一轮更严格的 A/B：

- `innercc` 不用 `--bare`
- 或者 `claude` 也人为收窄到近似 simple/bare 的前缀

## 3. 即使把 `--bare` 影响扣掉，innercc 仍然存在的真实问题

即使承认这次首轮前缀对比不公平，`innercc` 还是有三类真实问题不会因为去掉 `--bare` 自动消失。

### 3.1 轨迹更长

当前 run：

- `claude`: `41` turns
- `innercc`: `86` turns

当前 session 真实 traces：

- `claude`: `41`
- `innercc`: `83`

这不是 runner 造成的，而是 agent 轨迹本身更长。

### 3.2 工具错误分支更多

当前 session：

- `claude`
  - tool calls: `40`
  - request-side `tool_result` errors: `110`

- `innercc`
  - tool calls: `85`
  - request-side `tool_result` errors: `355`

即使去掉 `--bare`，更多错误分支仍然会让 observation token 失控。

### 3.3 修复点没有打中

最终 patch：

### `Claude`

```diff
if not data:
    return pd.Series([], dtype=int, name="count")
```

### `innercc`

```diff
if not x.groups or all(...):
    return x.value_counts(**kwargs)
```

`Claude` 命中了真正的 failing path；`innercc` 命中了相邻路径。

这会直接导致：

- 搜索回合更多
- 更多 Read/Bash/Grep
- 更多失败验证
- 更长轨迹
- 更低 cache hit

## 4. 这次 case 给 `innercc` 的具体改造清单

下面按优先级给，不讲空话。

### P0：先修 benchmark 跑法，避免把 `--bare` 差异混进主结论

这一步最先做。

建议：

1. 给 runner 增加开关：
   - `--innercc-bare true|false`
2. 默认做两组对比：
   - `innercc --bare`
   - `innercc` 完整模式
3. 在 `summary.json` / dashboard 里显式记录：
   - `cli_mode = bare | full`

理由：

- 否则你们后面每次都要重新争论“差异是 runner 造成的还是产品造成的”

### P1：增加“当前 session 过滤后 trace”作为一等产物

这次原始 bundle 混入了多个旧 session，导致最初看到的 `251` traces 带有误导性。

建议直接在推理产物里新增：

- `router_trace_bundle.current_session.json`

筛选逻辑：

- 从 `cli_result.json` 读取 `session_id`
- 按 `request_headers["x-claude-code-session-id"] == session_id` 过滤

这一步已经在本仓库里手工落了一版：

- [official48_runs/20260512-163036-cache-trace-dask-1-innercc-router/infer/runs/dask__dask_2024.3.1_2024.4.0/router_trace_bundle.current_session.json](/home/wt/sss_repos/sss_auto/SWE-EVO-subset-run/official48_runs/20260512-163036-cache-trace-dask-1-innercc-router/infer/runs/dask__dask_2024.3.1_2024.4.0/router_trace_bundle.current_session.json:1)
- [official48_runs/20260512-164502-cache-trace-dask-1-claude-router/infer/runs/dask__dask_2024.3.1_2024.4.0/router_trace_bundle.current_session.json](/home/wt/sss_repos/sss_auto/SWE-EVO-subset-run/official48_runs/20260512-164502-cache-trace-dask-1-claude-router/infer/runs/dask__dask_2024.3.1_2024.4.0/router_trace_bundle.current_session.json:1)

建议把它变成正式 pipeline 步骤。

### P1：减少错误分支回流

这次 innercc 当前 session 的 `355` 个 error tool_result 太高。

建议：

1. 对重复失败的 Bash/Read/Grep 增加止损
2. 同一错误模式达到阈值后，不要继续把原始错误正文完整带回上下文
3. 改成：
   - `error_fingerprint`
   - `count`
   - `last_message`
   - `summary`

也就是把：

- “每次都把完整失败结果重发”

改成：

- “首次完整，后续只回 error handle + delta”

### P1：让任务更早收敛到目标验证对象

这次 `innercc` 没有像 `Claude` 一样快速锁到 `_value_counts_aggregate` 空字典路径。

建议在 runtime 加两个守卫：

1. **目标测试优先守卫**
   - 每隔 N 轮检查最近动作是否仍然围绕 `FAIL_TO_PASS`
2. **相邻路径止损守卫**
   - 如果同一文件/相邻函数反复试探，但目标测试仍不变，则强制切换到更靠近 failing stack 的路径

在这题里，这个守卫本质上是在问：

- 你是不是一直在 `_value_counts` 附近打转，却没验证 aggregate 层？

### P2：即使保留 `--bare`，也把稳定前缀做大一点

这一步不是让 bare 变回 full，而是让 bare 不至于只有极小前缀。

建议：

1. bare 模式仍保留更稳定的少量系统指导
2. bare 模式工具池可考虑从 `3` 提升到一个稳定但更实用的小集合
3. 让首轮 `cache_creation_input_tokens` 不至于只有 `4.9k`

这一步目标不是追求“大而全”，而是避免：

- 稳定前缀太小，后续只能读回 `4k`

### P2：把“轨迹长度”变成一等调优指标

现在很多观察还是围绕：

- `resolved`
- `f2p`
- `cache_hit_rate`

建议新增：

1. `trace_request_count_current_session`
2. `cache_read_per_turn`
3. `new_input_per_turn`
4. `tool_error_per_turn`
5. `time_to_first_targeted_fix`

原因是这次最明显的信号其实是：

- `41 turns` vs `86 turns`

而不是单一的 `cache_hit_rate`。

### P3：把 compare 分析从“现象”变成“运行模式实验”

建议把后续实验固定成下面几组：

1. `Claude full` vs `innercc bare`
2. `Claude full` vs `innercc full`
3. `innercc bare` vs `innercc full`

这样可以拆出三件事：

1. 产品能力差异
2. 调用模式差异
3. `--bare` 对缓存和收敛的影响

## 5. 针对你们当前仓库，可以直接改的文件

### A. runner 对称性

优先改：

- [custom_cli_case/run_custom_cli_case.py](/home/wt/sss_repos/sss_auto/SWE-EVO-subset-run/custom_cli_case/run_custom_cli_case.py:215)

建议：

- 给 innercc 分支增加可选 `--bare`
- 不要把 `--bare` 写死在 runner 里

### B. 对比报告产物

优先改：

- [runtime/legacy/run_innercc_infer_official48.py](/home/wt/sss_repos/sss_auto/SWE-EVO-subset-run/runtime/legacy/run_innercc_infer_official48.py:437)

建议：

- 导出 `current_session` 过滤后的 trace bundle
- 在 `inference_summary.json` 里记录 `session_id`

### C. innerCC simple mode

优先看：

- [src/main.tsx](/home/wt/sss_repos/innerCC/src/main.tsx:1023)
- [src/constants/prompts.ts](/home/wt/sss_repos/innerCC/src/constants/prompts.ts:450)

建议：

- 重审 `CLAUDE_CODE_SIMPLE` 下 system prompt 和工具池到底该保留多少稳定前缀

## 6. 最小可执行下一步

如果只做一件事，我建议你们先做：

### `把 runner 里的 innercc --bare 改成可配置开关`

原因：

- 这是当前最明显的混杂因素
- 成本最低
- 一改就能立刻回答“去掉 bare 后，cache hit 还能差多少”

如果只做两件事，就再加上：

### `正式产出 current_session trace bundle`

因为没有这个，所有 trace 级分析都要先手工排污染。

## 7. 一句话收束

这次 case 里，`Claude Code` 高缓存命中并不是单一原因，而是：

- **runner 给了它更大的完整模式前缀**
- **它自己又用更短轨迹命中了正确修复点**

而 `innercc_0509_context` 的主要问题是：

- **这次 benchmark 跑法把它压进了过小的 bare 前缀**
- **它自己的轨迹又更长、错误分支更多、收敛更慢**

所以真正该做的，不是继续抽象讨论“谁缓存更好”，而是按下面顺序改：

1. 先消除 runner 调用不对称
2. 再减少错误分支回流
3. 再优化 simple/bare 模式的稳定前缀设计
