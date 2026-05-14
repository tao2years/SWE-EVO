# conan：`innercc_0509_context` 在 `bare/no-skill` 与 `full/skill` 下的早期对比（2026-05-13）

## 1. 为什么先单独看 `conan`

前面的 `dask` 三方消融已经告诉我们：

- `dask` 上几乎所有收益都来自去掉 `--bare`
- skill 本身在这个 case 上几乎没有额外价值

所以如果要判断 skill 是否“可能有真实作用”，就应该看更像 `conan` 这种：

- 原本容易误探索
- 任务目标更宽
- 容易在相邻改动上发散

## 2. 当前可用的两条对比

### A. `bare + no-skill`

- run: `20260511-194955-project-coverage-7-innercc-context-router-rerun`

### B. `full + skill`

- run: `20260513-153919-project-coverage-7-innercc-router`

### C. `full + no-skill`（中间态）

- run: `20260513-164631-project-coverage-7-innercc-router`
- display name: `pc7-innercc-0509-context-full-router-noskill-isolated`
- 这是通过隔离 `CLAUDE_CONFIG_DIR` 得到的真正 no-skill 控制组
- 当前 `conan` 还没收口，所以这里只能写中间轨迹，不写最终 F2P/P2P

## 3. 先给结论

在 `conan-io__conan_2.0.2_2.0.3` 上，当前看到的不是“skill 带来更高成功率”，而是：

- `full + skill` 把 `innercc` 推向了一个**更短 trace bundle**、但**更糟 patch 方向**的状态

换句话说：

- 它没有像 `dask` 那样只表现为 cache/轨迹优化
- 而是直接改坏了解题方向

## 4. 结果对比

| metric | `bare + no-skill` | `full + skill` |
| --- | ---: | ---: |
| resolved | `false` | `false` |
| f2p | `0/8` | `0/8` |
| p2p failure | `2` | `291` |
| turns | `153` | `161` |
| input tokens | `9.57M` | `10.59M` |
| cache read tokens | `599k` | `3.32M` |
| cost | `$29.40` | `$34.47` |
| trace requests | `331` | `31` |
| tool errors | `11` | `8` |

这个表说明了一个非常危险的现象：

- `full + skill` 并没有解决 F2P
- 但却把 `P2P` 从 `2` 个回归放大到 `291`

所以在 `conan` 上：

- skill 至少当前版本，不是“温和帮助”
- 而是可能在错误方向上更高效地推进

## 5. CLI 收口文本也支持这个判断

### `bare + no-skill`

它的总结是一个很宽的、大范围的 API/credential/integrity patch 套餐：

- `conan/api/output.py`
- `conan/internal/integrity_check.py`
- `conan/api/subapi/cache.py`
- `conan/cli/commands/cache.py`
- `conans/client/rest/conan_requester.py`
- `conans/client/downloaders/file_downloader.py`
- `conans/client/downloaders/caching_file_downloader.py`

也就是说，它是：

- **大范围误探索**

### `full + skill`

它最终没有正常收口，而是：

- `error_max_turns`
- `Reached maximum number of turns (160)`

这说明：

- skill 并没有帮助它更快找对路径
- 只是让它在错误探索中走得更久

## 6. patch 方向也完全变了

### `bare + no-skill`

patch 主要落在：

- `conan/api/output.py`
- `conan/internal/integrity_check.py`
- `conan/api/subapi/cache.py`
- `conan/cli/commands/cache.py`
- `conans/client/rest/conan_requester.py`
- `conans/client/downloaders/*`

### `full + skill`

patch 主要落在：

- `conan/api/subapi/upload.py`
- `conan/cli/commands/cache.py`
- `conan/cli/commands/upload.py`
- `conan/internal/conan_app.py`
- `conan/tools/files/files.py`

这个差异很重要：

- skill-on 并不是“在原有方向上更稳”
- 而是把 agent 推到了另一条大分支上

## 7. 为什么这题和 `dask` 不一样

`dask` 的问题是：

- `bare` 本身让前缀太小、轨迹太长

所以一旦切 full，问题自然收敛。

`conan` 不一样：

- 它不是简单的窄路径 bugfix
- 它更像一个目标不够尖锐、容易朝多条大分支误展开的 case

这类 case 上，一个强调：

- target-test-first
- 早 stop-loss
- 少广度探索

的 skill，如果写得不够精确，可能出现两种坏情况：

1. 没有真的把探索收窄到正确路径
2. 反而把 agent 推向另一个“看起来更结构化”的错误方向

## 8. 这对 skill 的含义

当前这个 `swebench-case-closer` 更像适合：

- `dask`
- `requests`
- 一类 target test 较尖锐的窄问题

而不一定适合：

- `conan` 这种多路径、大表面、容易在子系统边界发散的 case

所以不要再问：

- “这个 skill 有没有全局价值？”

更合理的问题应该是：

- “这个 skill 对哪些 case family 有价值？”

## 9. 下一步最值得做的事

1. 等 `full + no-skill` 的 `conan` 收完
   - 这是判断 skill 是否真的把 `conan` 引向坏方向的关键控制组

2. 如果 `full + no-skill` 的 `conan` 明显优于 `full + skill`
   - 说明 skill 需要对 `conan` 这类 case 降权或禁用

3. 后面给 skill 加 case-family gate
   - 对窄目标 bugfix 启用
   - 对宽表面 case 降低强度或不启用

## 10. no-skill 控制组的中间态已经能说明什么

虽然 `full + no-skill` 的 `conan` 还没最终评完，但当前 session traces 已经能给出一些有价值的信号。

### `conan` 当前中间态

#### `full + skill`

- 当前 session traces: `178`
- 最后一条仍然是 `tool_use`
- 当前 request body 约 `179,651 bytes`
- 当前 `input_tokens ≈ 21,179`

#### `full + no-skill`

- 当前 session traces: `80`
- 最后一条仍然是 `tool_use`
- 当前 request body 约 `495,633 bytes`
- 当前 `input_tokens ≈ 106,458`

这说明：

1. 两条轨迹形态已经明显分叉
2. `skill-on` 不是简单地“更快收敛”，而是走向了另一条更短但不一定更对的路径
3. `no-skill` 仍然更像旧的广域搜索形态

所以，等控制组收完以后，最关键要看的不是：

- 哪边 trace 更短

而是：

- 哪边最后的 patch 更接近正确目标
- 哪边最终 `P2P` 破坏更小

### `iterative`

控制组当前：

- traces: `61`
- 已经 `end_turn`
- `input_tokens ≈ 60,710`

说明它和 `skill-on` 的量级比较接近，后续更值得比最终结果，不值得只看中间轨迹。

### `modin`

控制组当前：

- traces: `45`
- 已经 `end_turn`
- `input_tokens ≈ 5,566`

它也更像一个“窄问题”，大概率不会成为 skill 价值的关键判别样本。

## 11. 一句话收束

在 `conan` 上，当前的 `full + skill` 没有表现出像 `dask` 那样的正收益，反而更像是把 `innercc` 引向了另一条高破坏性的错误路径；这意味着这个 skill 不能被视为全局正向增强，而更像一个对某些 case family 有利、对另一些 case family 有害的定向干预。  
