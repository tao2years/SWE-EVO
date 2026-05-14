# Claude Code vs innercc 缓存命中率差异复盘（单 case / 单 session 视角，2026-05-12）

## 1. 问题定义

本文只回答一个问题：

- **不考虑跨 session、跨任务共享缓存**，为什么 `Claude Code` 的 `cache_hit_rate` 明显更高，而我们的 `innercc` 更低？

这里明确排除的解释：

- “上一个 run 正好热缓存了”
- “多个 case 之间共用了同一个长 session”
- “不同任务之间共享了 provider cache”

本文只看：

- **单个 case 内部**的多轮对话
- 同一 run 内每个 case 的 `cli_model_input_tokens` / `cli_model_cache_read_tokens`
- router trace 里每一轮 `request_body` 的增长方式

## 2. 数据源

本轮主要用四个 run 做对照：

| 标签 | run id | 说明 |
| --- | --- | --- |
| `claude_router` | `20260511-clean-router-project-coverage-7-claude-2.1.138` | Claude Code + router |
| `innercc_router` | `20260511-194955-project-coverage-7-innercc-context-router-rerun` | innercc context + router |
| `claude_direct` | `20260511-095638-project-coverage-7-claude-2.1.138` | Claude Code direct |
| `innercc_context_direct` | `20260509-115738` | innercc context direct |

辅助对照：

- `20260509-112102` (`innercc init direct`)
- `20260509-142112-project-coverage-7-innercc` (`innercc dcp direct`)

主要证据文件：

- [runtime/summarize_official48_run.py](/home/wt/sss_repos/sss_auto/SWE-EVO-subset-run/runtime/summarize_official48_run.py:366)
- [custom_cli_case/run_custom_cli_case.py](/home/wt/sss_repos/sss_auto/SWE-EVO-subset-run/custom_cli_case/run_custom_cli_case.py:235)
- `official48_runs/<run_id>/analysis/summary.json`
- `official48_runs/<run_id>/infer/runs/<instance_id>/router_trace_bundle.json`

## 3. 先澄清 `cache_hit_rate` 的定义

这批 run 的 `cache_hit_rate` 不是“命中请求数 / 总请求数”，而是：

`cache_read_tokens / (input_tokens + cache_read_tokens)`

代码见 [runtime/summarize_official48_run.py](/home/wt/sss_repos/sss_auto/SWE-EVO-subset-run/runtime/summarize_official48_run.py:366)。

直接含义：

- 分母里包含所有**新增输入 token**
- 只要会话里每一轮继续引入很多新内容，命中率就会被迅速稀释
- 所以 `33%` 不代表“只有 33% 的轮次命中”，而是“按 token 计，约三分之一来自缓存”

另一个关键点：

- `cache_creation_input_tokens` **不在**这个比率的分母里
- 所以“cache creation 多”不会直接把 `cache_hit_rate` 算低
- 但它是一个旁证，说明系统在不断建立新的缓存前缀

## 4. 高层现象

### 4.1 run 级别

| run | `cache_hit_rate` | `total_input_tokens` | `cache_read_tokens` | `turns` | `cost` |
| --- | --- | --- | --- | --- | --- |
| `claude_direct` | `48.2%` | `7.33M` | `6.83M` | `328` | `$42.63` |
| `claude_router` | `28.7%` | `29.30M` | `11.81M` | `594` | `$160.71` |
| `innercc_context_direct` | `17.1%` | `5.11M` | `1.06M` | `296` | `$16.80` |
| `innercc_init_direct` | `14.6%` | `6.13M` | `1.05M` | `294` | `$19.88` |
| `innercc_dcp_direct` | `9.1%` | `18.62M` | `1.86M` | `254` | `$59.12` |
| `innercc_router` | `10.2%` | `14.95M` | `1.70M` | `445` | `$47.11` |

观察：

- 同样不考虑跨 session，`Claude Code` 在 direct 模式下明显更高
- 到 router 模式，`Claude Code` 命中率也下降，但仍然明显高于 `innercc`
- 所以这不是“router 才导致 innercc 低”，而是同样的趋势在 direct / router 都存在

### 4.2 同一批 case 的 router 对照

| case | `claude_router rate` | `claude turns` | `innercc_router rate` | `innercc turns` |
| --- | --- | --- | --- | --- |
| `conan` | `0.2147` | `374` | `0.0590` | `153` |
| `dask` | `0.7379` | `33` | `0.0988` | `109` |
| `iterative` | `0.5558` | `76` | `0.2517` | `52` |
| `modin` | `0.7241` | `32` | `0.3739` | `38` |
| `requests` | `0.8622` | `12` | `0.4303` | `24` |
| `pydantic` | `0.5773` | `49` | `0.2258` | `52` |
| `scikit` | `0.8225` | `18` | `0.4106` | `17` |

这张表很关键：

- 不是只有一个极端 case 低
- 几乎所有中小 case 上，`Claude Code` 的单案命中率都高于 `innercc`
- 而且在 `dask / requests / pydantic / modin` 这些典型 case 上，差距非常稳定

## 5. 先排除一个常见误解：首轮 prompt 不是主因

看同一个 case 的前几轮 router request：

- `dask`
  - `claude` 第 1 轮 `body_len = 106277`
  - `innercc` 第 1 轮 `body_len = 106277`
- 前 10 轮的 `body_len` 与 `tokens_input` 基本一致

也就是说：

- 两边不是“一开始就喂了完全不同的大 prompt”
- 至少在 case 起步阶段，前缀几乎一样

所以低命中率的主因**不是首轮注入大小**，而是后续会话如何演化。

## 6. 真正的第一根因：innercc 会中途重写历史，Claude Code 基本保持单调追加

### 6.1 可直接观测到的“历史重写”

在 `innercc_router` 里，多个 case 都出现了 `request_body` 突然大幅变短的事件：

| case | shrink turn | shrink 前 | shrink 后 | 说明 |
| --- | --- | --- | --- | --- |
| `requests` | `10 -> 11` | `body_len = 125265`, `msg_count = 19`, `tokens_in = 28678` | `body_len = 18694`, `msg_count = 1`, `tokens_in = 4358` | 历史被重写 |
| `modin` | `27 -> 28` | `body_len ≈ 177k`, `msg_count = 53`, `tokens_in ≈ 40k` | `body_len = 18976`, `msg_count = 1`, `tokens_in = 4451` | 历史被重写 |
| `iterative` | `71 -> 72` | `body_len ≈ 252k`, `msg_count = 141`, `tokens_in = 58468` | `body_len = 18502`, `msg_count = 1`, `tokens_in = 4325` | 历史被重写 |

具体证据：

- `requests`：
  - 第 `10` 轮还是 `19` 条 message，最后几条是 `assistant/tool_result` 往返
  - 第 `11` 轮直接变成 `1` 条 `user` message
- `modin` / `iterative` 也同样如此

而对照 `claude_router / requests`：

- **没有任何 negative delta**
- request body 始终是单调增长，没有突然重置

### 6.2 这为什么会直接伤缓存

provider 侧 prompt cache 的前提通常是：

- 前缀相同
- 或前缀高度相似且稳定追加

`Claude Code` 的 case 内部更像：

- `turn 1 -> 2 -> 3 -> ...`
- 每轮都在同一条历史上继续追加

而 `innercc` 在这些 case 内部更像：

- 先追加到一个很长的历史
- 然后在某一轮突然把整个历史压成一个新的短 prompt
- 从这个新 prompt 重新开始累计

这等于：

- 旧前缀缓存不再能直接复用
- 新前缀又要重新“冷启动”

所以，**中途 history rewrite / compact** 是我们命中率低的第一结构性原因。

## 7. 第二根因：同一 case 往往多跑很多轮，新增 token 远多于读缓存 token

### 7.1 先看 turns

同一批 router case：

- `dask`: `claude 33` vs `innercc 109`
- `requests`: `claude 12` vs `innercc 24`
- `pydantic`: `claude 45` vs `innercc 93`

这意味着：

- 即便前缀一样
- `innercc` 也会在单 case 内经历更多轮的工具往返、错误处理、再假设

### 7.2 再看“新 token / cache read token”比值

对 run-level 来说，这个比值越大，命中率越低。

同一批 router run：

- `claude_router`：`new/read = 2.48`
- `innercc_router`：`new/read = 8.81`

也就是说，`innercc` 这轮里每读 `1` 个缓存 token，大约还要引入 `8.81` 个新 token；而 `Claude Code` 只引入 `2.48` 个新 token。

拆到 case 级更明显：

### `claude_router`

- `requests`: `new/read = 0.16`
- `scikit`: `0.22`
- `dask`: `0.36`
- `modin`: `0.38`
- `pydantic`: `0.73`
- `iterative`: `0.80`
- `conan`: `3.66`

### `innercc_router`

- `requests`: `1.32`
- `scikit`: `1.44`
- `modin`: `1.67`
- `iterative`: `2.97`
- `pydantic`: `3.43`
- `dask`: `9.13`
- `conan`: `15.96`

这说明：

- `Claude Code` 多数 case 都还处在“缓存读回比新增输入更多”的区间
- `innercc` 则多数 case 已经进入“新增输入远大于缓存读回”的区间

而由于公式是：

`cache_read / (input + cache_read)`

一旦 `input` 远大于 `cache_read`，命中率就自然掉下去。

## 8. 第三根因：少数长案会把 run-level 命中率整体拉穿

以 `claude_router` 和 `innercc_router` 两轮为例：

### `claude_router`

- 总 `cache_hit = 28.7%`
- 但除了 `conan` 外，多数中小 case 都在 `0.55 ~ 0.86`

真正拖低 run-level 的主因是：

- `conan`
  - `turns = 374`
  - `rate = 0.2147`
  - `input = 27.08M`

### `innercc_router`

- 总 `cache_hit = 10.2%`
- 同时被两个大案拖穿：
  - `conan`: `rate = 0.0590`, `input = 9.57M`
  - `dask`: `rate = 0.0988`, `input = 3.67M`

这点非常重要：

- run-level 低命中率不是“所有 case 都一样低”
- 经常是 1 到 2 个超长、超跑偏 case 决定了总体数值

## 9. 为什么 Claude Code 高，而我们低

如果把上面的证据压成最小解释链，就是：

### Claude Code 更高，因为：

1. 同一 case 内更常保持单调追加的历史前缀
2. 中途不容易发生整段 history rewrite
3. 单案 turns 往往更少
4. 因此 `cache_read_tokens` 能持续复用前缀，而 `input_tokens` 增长相对可控

### innercc 更低，因为：

1. 会话中途发生大幅 compact / history rewrite
2. 同一 case 往往多跑很多轮
3. 每轮新增大量 tool output、错误信息、再假设文本
4. 少数长案还会严重 scope explosion
5. 于是 `input_tokens` 增长远快于 `cache_read_tokens`

所以问题核心不是：

- provider cache 坏了
- router 坏了
- 首轮 prompt 太大了

而是：

- **轨迹演化方式不同**
- `Claude Code` 更像“沿着一条历史稳定追加”
- `innercc` 更像“多跑几倍回合，并且中途重写历史”

## 10. 哪些现象不能单独拿来解释

### 10.1 不是“首轮 prompt 太大”

因为同 case 前 10 轮里，`claude` 和 `innercc` 的 request body 基本一致。

### 10.2 不是“只要 turns 多就一定低”

turns 多会伤缓存，但不是充分条件。

例如：

- `claude / iterative`: `76 turns`, `rate = 0.5558`

这说明 turns 高本身不是决定性原因；真正决定性的，是：

- turns 高
- 同时历史不稳定
- 同时不断追加大量新内容

### 10.3 不是“cache_creation_tokens 高直接把 rate 算低”

因为当前 `cache_hit_rate` 公式根本没有把 `cache_creation_tokens` 放进分母。

它只能作为旁证：

- 说明系统在不断创建新缓存前缀
- 侧面支持“历史被重置/改写”

## 11. 最终判断

只看**单 case / 单 session**，不考虑跨任务共享缓存时：

**Claude Code 缓存命中率更高的真正原因，是它更常保持稳定前缀并在较少轮数内收口；innercc 更低的真正原因，是它在同一 case 内更容易发生 history rewrite，并且会用更多轮数引入大量新 token。**

最能解释差异的三个证据是：

1. `innercc` 多个 case 里都存在 request body 突然从十几万字符降到一万多字符的历史重写事件，而 `claude` 同案没有。
2. `innercc` 同案 turns 普遍更多，`new/read` 比值显著更高。
3. 低命中率通常被 `conan / dask / pydantic` 这类长案拖穿，而这些长案恰好也是最容易跑偏和历史膨胀的案子。

如果再压成一句话：

**Claude Code 高，是因为它更像“稳定追加同一条历史”；innercc 低，是因为它更像“多跑很多轮，并且中途重写历史”，导致 provider prefix cache 反复失效。**

## 12. 下一步建议

如果目标是提升 `innercc` 的单案缓存命中率，优先级建议如下：

1. 记录并量化每个 case 的 `history rewrite` 次数，把它当一等指标。
2. 把 compact / snip 从“重写整段历史”改成“尽量保留稳定前缀，只裁剪尾部噪音”。
3. 对大案加更早的主线约束，降低 `conan / dask / pydantic` 这种长跑偏。
4. 单案超过一定 turns 时，优先做 hypothesis pruning，而不是继续追加工具输出。
5. 在 dashboard 里补一个 `new/read ratio` 指标，它比单纯看 `cache_hit_rate` 更能直接反映“新增 token 是否失控”。
