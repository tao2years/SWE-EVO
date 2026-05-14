# project-coverage-7：`swebench-case-closer` 注入后的 innerCC / Claude Code 对比（2026-05-13）

## 1. 范围

本次对比只看两组 `project-coverage-7` router run：

### skill-on

- `innercc`: `20260513-153919-project-coverage-7-innercc-router`
- `claude`: `20260513-155928-project-coverage-7-claude-router`

### baseline（skill-off）

- `innercc`: `20260511-194955-project-coverage-7-innercc-context-router-rerun`
- `claude`: `20260511-clean-router-project-coverage-7-claude-2.1.138`

注意：

1. `skill-on` 的 `innercc` **已经去掉了 runner 强制 `--bare`**
2. 所以这次 `innercc skill-on` 的提升，不能简单全归因于 skill，本质上是：
   - `skill 注入`
   - `调用模式变化（不再 bare）`
   两者共同作用

## 2. skill 是否真的进了请求

结论：**进了**。

两边都在真实 `llm router` request 里出现了：

- `swebench-case-closer`

也就是说，这不是只写进 `metadata.json` 的假注入，而是模型真的看到了这个 skill。

## 3. run 级总览

| metric | `innercc skill-on` | `innercc baseline` | `claude skill-on` | `claude baseline` |
| --- | ---: | ---: | ---: | ---: |
| resolved | `3` | `3` | `2` | `3` |
| resolved rate | `42.9%` | `42.9%` | `28.6%` | `42.9%` |
| f2p micro | `40.9%` | `40.9%` | `36.4%` | `40.9%` |
| p2p micro | `51.1%` | `54.3%` | `54.2%` | `50.8%` |
| total cost | `$51.10` | `$47.11` | `$67.68` | `$160.71` |
| total turns | `445` | `445` | `409` | `594` |
| input tok | `15.21M` | `14.95M` | `11.71M` | `29.72M` |
| cache hit | `35.4%` | `10.2%` | `42.2%` | `28.7%` |

## 4. 先给结论

### 4.1 `innercc`

`skill-on` 对 `innercc` 的主要收益不是成功率，而是：

- **缓存命中显著提高**
- 但 `resolved` / `f2p` **没有提升**
- `p2p` 反而略降

换句话说：

- `innercc` 在“更 cache-friendly 的前缀 / 工作流”上变好了
- 但 benchmark 最终成功率没有同步变好

### 4.2 `claude`

`skill-on` 对 `Claude Code` 的主要收益是：

- **成本、turns、input tokens 大幅下降**
- `cache hit` 提高
- `p2p` 略升

但代价是：

- `resolved` 从 `3 -> 2`
- `f2p micro` 从 `40.9% -> 36.4%`

所以：

- `Claude Code` 在 skill-on 下变得更节制、更省
- 但也更容易错过某些原本能解出来的 case

## 5. innerCC：为什么 cache hit 从 `10.2%` 提到 `35.4%`

这里最重要的不是 skill 本身，而是：

### `runner 不再强制 --bare`

这会让 `innercc_0509_context` 不再走极简 simple prompt 路径，而能保留更大的稳定前缀。

所以这次 `innercc` 的 cache hit 提升，**首先**来自调用模式变化，其次才可能是 skill 对轨迹的约束效果。

更准确地说：

- `skill-on innercc` 证明了“把 `--bare` 去掉 + 给一点 workflow guidance”后，缓存命中可以明显改善
- 但它**还不能证明**“skill 本身就能显著提高成功率”

## 6. Claude：为什么 cache hit 提高、成本下降，但 resolved 下降

这是这次最值得分析的点。

从 run 级结果看：

- `cache hit`: `28.7% -> 42.2%`
- `cost`: `$160.71 -> $67.68`
- `turns`: `594 -> 409`
- `input`: `29.72M -> 11.71M`

也就是说，skill-on 后的 `Claude`：

- 搜索更少
- 轨迹更短
- 前缀更稳定

但同时：

- `resolved`: `3 -> 2`
- `f2p micro`: `40.9% -> 36.4%`

这说明这个 skill 对 `Claude` 的作用更像：

- **强约束探索**

它在一些 case 上抑制了无效探索，但在另一些 case 上也抑制了原本必要的扩展搜索。

## 7. case 级变化：哪些 case 真的被影响了

### 7.1 innerCC

#### 明显正向

- `dask`
  - 仍然 `resolved=true`
  - turns: `109 -> 29`
  - trace requests: `133 -> 28`
  - 这是明显更快的收敛

- `requests`
  - 仍然 `resolved=true`
  - turns: `24 -> 16`
  - 也是更快的收敛

#### 基本不变

- `modin`
  - 仍然 `resolved=true`
- `pydantic`
  - 仍然失败

#### 变差或更脆

- `iterative`
  - 仍然失败
  - `p2p_failure: 0 -> 2`

- `scikit`
  - 仍然失败
  - turns: `17 -> 83`
  - 说明 skill 没有稳定抑制错误探索

- `conan`
  - 仍然失败
  - `p2p_failure: 2 -> 291`
  - 并且带 `cli_reported_error`
  - 这是本次 `innercc skill-on` 最大的坏 case

### 7.2 Claude

#### 明显正向

- `conan`
  - `f2p_success: 0 -> 1`
  - `p2p_failure: 317 -> 3`
  - turns: `374 -> 161`
  - 这是本次 `Claude skill-on` 最大的正收益 case

#### 基本不变

- `iterative`
  - 仍然失败
- `modin`
  - 仍然成功
- `requests`
  - 仍然成功
- `pydantic`
  - 仍然失败
- `scikit`
  - 仍然失败

#### 明显负向

- `dask`
  - `resolved: true -> false`
  - `f2p_success: 2 -> 0`
  - `p2p_failure: 0 -> 2`

这说明：

- skill-on 帮 `Claude` 在 `conan` 上避免了大范围误探索
- 但在 `dask` 上可能把它限制得过头，导致错过了原先能命中的路径

## 8. 这次对 skill 的合理解读

### 8.1 不能说“skill 提高了成功率”

至少从这组 `pc7` 看，结论不成立：

- `innercc`：resolved 没涨
- `claude`：resolved 还降了

### 8.2 可以说“skill 改变了搜索风格”

这个结论成立，而且证据很强：

- `Claude` 的成本、turns、input 明显下降
- `innercc` 的 `dask/requests` 轨迹显著变短
- 两边都显著更 cache-friendly

### 8.3 对 innerCC，当前更像“去掉 bare 的收益 > skill 本身的收益”

因为这次 innerCC 同时发生了两个变化：

1. runner 去掉了强制 `--bare`
2. skill 注入进了 prompt

从结果看：

- cache hit 大幅上升
- 但成功率不升

所以更合理的解释是：

- `--bare` 去掉以后，prompt/cache 行为变健康了
- 但这个 skill 第一版还不足以显著提高成功率

## 9. 这次最终数字意味着什么

### innerCC 最终结果

- `resolved_true_cases = 3`
- `f2p_micro = 40.9%`
- `p2p_micro = 51.1%`
- `cache_hit = 35.4%`

相对于 baseline：

- `resolved` 不变
- `f2p` 不变
- `p2p` 下降
- `cache hit` 大幅上升

所以对 `innercc` 来说，这次最显著的收益是：

- **更 cache-friendly**

但不是：

- **更高成功率**

### Claude 最终结果

- `resolved_true_cases = 2`
- `f2p_micro = 36.4%`
- `p2p_micro = 54.2%`
- `cache_hit = 42.2%`

相对于 baseline：

- `resolved` 下降
- `f2p` 下降
- `p2p` 上升
- `cache hit` 上升
- `cost / turns / input` 明显下降

所以对 `Claude` 来说，这次 skill 更像：

- **把搜索压得更短、更便宜**

但同时：

- **牺牲了一部分原本能命中的 case**

## 10. 下一步实验建议

如果你们想知道 skill 是否“真的提高成功率”，下一步实验必须拆开：

### 实验 A：innercc full, no skill

这一步回答：

- 去掉 bare 以后，不加 skill，本身会不会已经变好？

### 实验 B：innercc full, skill on

这一步回答：

- 在完整模式下，skill 本身是否再带来额外收益？

### 实验 C：claude, skill wording A/B

对 `Claude` 而言，当前 skill 似乎有点“压缩探索过头”。

所以应尝试：

1. 当前版本（强 stop-loss）
2. 更软版本（只强调 target test first，不限制扩展探索）

### 实验 D：case-family 分簇

这个 skill 更像对某些 case family 有效，而不是全局有效。

优先按这几类分：

- narrow target / direct bugfix
- release-note ambiguity
- aggregate-vs-neighbor-path
- multi-cluster issue

## 11. 最值得立即做的改进

### 对 `innercc`

1. 保留“去掉 bare”的变更
2. 不要把第一版 skill 当成成功率银弹
3. 单独修 `conan` 和 `scikit` 这种 skill-on 后变坏的 case family

### 对 `Claude`

1. 保留这版 skill 的“成本压缩”价值
2. 但必须削弱它对某些 case 的过度收缩
3. 特别是不能让它在 `dask` 这种本来能解的窄问题上提前收口

## 12. 一句话收束

这次 `pc7` 结果说明：

- `skill-on` 的最大正面效果是**改变轨迹形态**和**提高 cache-friendliness**
- 但它还没有稳定转化成更高的最终成功率

对 `innercc` 来说，当前看到的提升里，**去掉 `--bare` 的收益很可能比 skill 本身更大**；对 `Claude` 来说，当前 skill 更像一个“节流器”，在压低成本的同时，也压掉了部分本来能成功的探索。  
