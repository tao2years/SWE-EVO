# innerCC CodeAgent 缓存命中率系统研究（2026-05-12）

## 1. 范围与代码快照

本文研究的问题是：

- 为什么 autonomous code agent 的 prompt cache / KV cache / prefix cache 命中率天然偏低
- 学术界和工业界已有方法里，哪些真正适合 code agent
- 结合 `innerCC` 源码，应该如何做 runtime / context / inference architecture 改造

本次源码核对对象：

- 仓库：`/home/wt/sss_repos/innerCC`
- 分支：`context_dev`
- 分析 worktree：`/home/wt/sss_repos/innerCC_context_dev`
- 代码快照：`context_dev@718a3af`

本文不是单纯论文综述，而是按下面这条链路组织：

`trajectory entropy -> prefix instability -> cache locality -> serving/scheduler reuse`

## 2. 核心结论

先给结论：

1. 你们面对的不是“普通 KV cache 没开好”，而是 `autonomous trajectory entropy` 问题。
2. chat 产品缓存命中率高，根本原因是上下文拓扑稳定；autonomous code agent 低，根本原因是上下文拓扑持续重写、分叉、漂移。
3. 仅靠 provider 侧 exact-prefix prompt caching，最多只能解决一部分稳定头部，解决不了 branch divergence、tool-conditioned observation、retrieval reorder、history rewrite。
4. `innerCC/context_dev` 已经具备不少 cache-aware 基础设施，但仍然缺少三类关键能力：
   - `artifactized observation`
   - `branch/checkpoint-aware runtime`
   - `workflow-aware serving / shared KV fabric`
5. 最适合 startup 快速落地的方向，不是继续堆 prompt engineering，而是把 agent 从“高熵 transcript”改造成“低熵执行图”。

## 3. 第一性原理：为什么 CodeAgent 天然 cache hit rate 低

### 3.1 为什么 chat product 命中率通常更高

普通 chat 产品通常满足这几个条件：

- system prompt 长期固定
- tools 很少，schema 很少变化
- message 结构是线性 append-only
- 很少出现 retry / reflection / multi-branch
- 用户不会持续修改外部世界状态后再把结果塞回 prompt

所以它更接近：

`stable prefix + small dynamic suffix`

而 autonomous code agent 更接近：

`mutable prefix + large volatile tail + frequent branch divergence`

这不是“prompt 更长”这么简单，而是：

- context 的有效图结构从链表变成了 DAG
- 但大多数 serving 系统仍按“线性前缀复用”来设计 cache

### 3.2 token-level：最容易被忽视，但最致命

对 provider prompt caching、vLLM prefix caching、SGLang radix prefix reuse 来说，最关键的不是“语义相似”，而是“前缀字节序列是否稳定”。会直接造成 miss 的因素包括：

- timestamp / current date
- absolute path
- tool_use_id / request id / trace id
- diff header / hunk 顺序
- retrieval chunk 顺序变化
- JSON key 顺序不稳定
- planner / executor 的 wording drift
- memory 注入内容增删
- MCP instructions 晚连接、晚注入

也就是说，很多 miss 不是“大改动”，而是 tiny token diff。

### 3.3 attention-level：prefix cache 的结构性边界

标准 prefix KV cache 的复用前提是：

- 新请求的前缀 token 序列与旧请求一致
- 后续 token 的注意力依赖不被改变

一旦发生下面这些事，后续 KV 很难继续直接复用：

- retrieval chunk 改顺序
- tool result 插到中间
- compact 把旧 history 改写成 summary
- fork branch 在同一 parent checkpoint 后各自追加不同 observation
- reflection / retry 走了不同 reasoning path

所以 code agent 的问题不只是“prefix 不稳定”，而是“前缀后面的依赖图也不稳定”。

### 3.4 session-level：agent 不是 transcript，而是 execution DAG

真实 agent 轨迹更像：

- 主线执行
- 工具调用
- 失败重试
- 反思分叉
- 子 agent 分支
- compact / summarize
- 回到主线

如果 runtime 仍然把这套东西线性化成 transcript，就会出现：

- retry 从头 replay
- sibling branch 重复 prefill 同一个 parent prefix
- old observation 被多次拷贝进 prompt
- compact 触发大规模 history rewrite

这时缓存命中率低，不是偶然，而是数据结构选错了。

### 3.5 serving-level 与 scheduler-level：命中不只由 prompt 决定

即使 prefix 相同，缓存复用还取决于：

- 请求有没有被路由到持有该 KV 的 worker
- eviction 策略是否保住高价值 subtree
- multi-agent sibling branch 是否共用同一 KV fabric
- prefill/decode 是否解耦
- cache 是否支持跨 worker / 跨 GPU / 跨 node 共享

这也是为什么：

- exact-prefix provider cache 适合稳定头部
- 但要处理 multi-agent / retry / long-horizon workflow，必须引入 workflow-aware routing 与 shared KV fabric

## 4. 当前 SOTA：哪些真的适合 code agent

### 4.1 Provider / 产品侧 prompt caching

| 方案 | 核心思想 | 复用粒度 | 适合 code agent 吗 | 主要限制 |
| --- | --- | --- | --- | --- |
| Anthropic Prompt Caching | 对带 cache breakpoint 的 prompt 前缀做 exact-prefix 复用 | prompt prefix | 适合做稳定 system/tools 头部 | 对 tiny diff 极敏感，branch reuse 弱 |
| OpenAI Prompt Caching | exact prefix routing + cache key hints | prompt prefix | 适合做稳定层与 replay | 不解决 non-prefix reuse |
| Gemini Context Caching | 对显式缓存内容做复用 | cached context blob | 适合静态文档 / 长参考 | 更像 document cache，不是 agent DAG cache |

判断：

- 这类方案是必要基础，但不是 autonomous code agent 的完整答案。
- 对你们最重要的价值是“固定 L0/L1 层”，不是解决全部上下文。

### 4.2 推理框架与 serving 方向

| 方案 | 核心思想 | 复用粒度 | 适合 code agent 吗 | 主要限制 |
| --- | --- | --- | --- | --- |
| vLLM Prefix Caching | block hash 链做 automatic prefix caching | full block prefix | 适合作为自托管基线 | exact-prefix/full-block，怕 reorder |
| SGLang RadixAttention | 用 radix tree 组织共享前缀 | prefix subtree | 很适合多 agent 共享稳定头部 | 仍主要是 prefix reuse |
| TensorRT-LLM KV reuse | paged KV + reuse + eviction priority | KV block/page | 适合生产 serving | 更多是 infra 层，需要 runtime 配合 |
| LMCache | 把 KV 从 engine 本地扩展到共享层 | cross-worker KV | 很适合 multi-agent / retry | 集成成本高于单机缓存 |
| TGI/BentoML cache | 通常是较浅层 prefix / response cache | request/prefix | 可做补充 | 对 agent 价值有限 |

判断：

- 你们如果自托管，短期最值得看的工程栈是 `vLLM + LMCache` 或 `SGLang + radix attention + shared cache`。
- 如果主要走 provider API，这些框架不能直接落地，但它们揭示了 runtime 应该怎样重构。

### 4.3 更值得关注的论文方向

| 工作 | 核心思想 | 更适合 code agent 的点 | 不适合的点 |
| --- | --- | --- | --- |
| Prompt Cache | 把 prompt 拆成模块，按模块重用 attention states | 很适合 layered prompt | 论文设置比真实 agent 更静态 |
| CacheBlend | 复用相同 chunk 的 KV，再做重组融合 | 适合 retrieval / repo chunk 复用 | tool observation 场景适配差 |
| RAGCache | 针对 RAG 的缓存与检索协同 | 适合 repo retrieval | 不覆盖 tool-heavy agent 主循环 |
| Preble | prefix-aware scheduling / locality-aware routing | 很适合 workflow 级调度 | 依赖自控 serving 栈 |
| KVFlow | workflow-aware KV 管理 | 很适合 agent DAG | 工程复杂度较高 |
| TokenDance | 多 agent / 多 request 协同减少 KV 交换与重复 | 很适合 multi-agent 分支 | 更偏高性能 serving 研究 |
| SideQuest | 把 KV 管理变成后台并行优化问题 | 适合长链路 agent | correctness / 工程复杂度高 |
| LazyLLM | 延迟/分层管理长上下文的激活状态 | 对 deep research agent 有前景 | 仍偏 research |
| YOCO | 从模型结构层面改变 cache 使用方式 | 长期方向 | 不是短中期可落地方案 |

### 4.4 Code agent 系统里最值得借鉴的公开做法

| 系统 | 值得借鉴的点 | 局限 |
| --- | --- | --- |
| Aider | repo map、prompt caching、read dedup | 单 agent 为主，branch-aware 不强 |
| OpenHands | condenser / rolling window / memory layering | 更偏 context survival，不等于高 cache locality |
| SWE-agent | 轨迹记录、可 replay、任务边界清晰 | 公开实现更多是 benchmark agent，不是生产级 cache runtime |
| Cursor / Claude Code | 背景 agent、长会话、工具编排 | 公开机制不足，多数只能推断 |
| RepoCoder / RepoPrompt | retrieval / repo context 组织 | 更偏 code RAG，不覆盖全 agent loop |

## 5. 结合 innerCC/context_dev 源码的结构性判断

### 5.1 已经做对的事情

`innerCC/context_dev` 不是“完全没有 cache 意识”，相反，已经有很多正确基础设施：

- tools 列表为了 prompt cache 稳定性做了排序，并强调 built-ins 必须保持连续前缀：[src/tools.ts](/home/wt/sss_repos/innerCC_context_dev/src/tools.ts:350)
- system prompt 被显式切成 static / dynamic 边界：[src/constants/prompts.ts](/home/wt/sss_repos/innerCC_context_dev/src/constants/prompts.ts:114)
- API 层会按 cache scope 构造 system prompt blocks：[src/utils/api.ts](/home/wt/sss_repos/innerCC_context_dev/src/utils/api.ts:304)
- fork child 会尽量继承 parent 的 rendered system prompt 与 exact tools，以保 prefix 一致：[src/tools/AgentTool/AgentTool.tsx](/home/wt/sss_repos/innerCC_context_dev/src/tools/AgentTool/AgentTool.tsx:486)
- fork path 甚至明确写了“cache-identical API request prefixes”的目标：[src/tools/AgentTool/forkSubagent.ts](/home/wt/sss_repos/innerCC_context_dev/src/tools/AgentTool/forkSubagent.ts:56)
- 有 prompt cache break detection，用于识别 system/tool/cache-control 漂移：[src/services/api/promptCacheBreakDetection.ts](/home/wt/sss_repos/innerCC_context_dev/src/services/api/promptCacheBreakDetection.ts:246)
- 有 tool result budget / persisted preview / replacement state，减少大 observation 重发：[src/utils/toolResultStorage.ts](/home/wt/sss_repos/innerCC_context_dev/src/utils/toolResultStorage.ts:924)
- 有 cached microcompact / cache_edits，试图不改本地消息、只在 API 层发删除提示：[src/services/compact/microCompact.ts](/home/wt/sss_repos/innerCC_context_dev/src/services/compact/microCompact.ts:296)
- `Read` 已经做了 unchanged stub，避免同文件重复大段重发：[src/tools/FileReadTool/FileReadTool.ts](/home/wt/sss_repos/innerCC_context_dev/src/tools/FileReadTool/FileReadTool.ts:520)

这些点说明：你们已经从“无 cache 设计”跨到了“有意识地稳 prefix”。

### 5.2 当前仍然存在的主要 miss 源

#### A. system / session 层仍有动态注入点

- query 每轮都会重新 `appendSystemContext`、`prependUserContext`：[src/query.ts](/home/wt/sss_repos/innerCC_context_dev/src/query.ts:451) [src/query.ts](/home/wt/sss_repos/innerCC_context_dev/src/query.ts:661)
- `getUserContext` / `getSystemContext` 虽然做了 memoize，但内容里仍有 `gitStatus`、`currentDate`、`CLAUDE.md`、memory 等动态成分：[src/context.ts](/home/wt/sss_repos/innerCC_context_dev/src/context.ts:116) [src/context.ts](/home/wt/sss_repos/innerCC_context_dev/src/context.ts:155)
- `currentDate` 是典型的 tiny diff cache buster：[src/context.ts](/home/wt/sss_repos/innerCC_context_dev/src/context.ts:186)

#### B. 仍然保留了会 cache-break 的 dynamic system section

- MCP instructions 仍可能通过 `DANGEROUS_uncachedSystemPromptSection` 注入：[src/constants/prompts.ts](/home/wt/sss_repos/innerCC_context_dev/src/constants/prompts.ts:513)
- 这类“晚连接、晚发现、晚注入”的动态信息会直接打断 system prompt 复用链

#### C. 主循环还是 transcript-oriented，而不是 checkpoint / branch-oriented

- `queryLoop` 每轮仍然以 `messagesForQuery` 为中心来做预算、compact、重试：[src/query.ts](/home/wt/sss_repos/innerCC_context_dev/src/query.ts:380) [src/query.ts](/home/wt/sss_repos/innerCC_context_dev/src/query.ts:424)
- 这意味着 retry / branch 主要是在重放 transcript，而不是从结构化 checkpoint 恢复

#### D. tool_result 仍然是最大熵源

- 现在的主策略仍是“大了就落盘或清空”，而不是默认 artifact handle 化
- `cached microcompact` 的核心仍是删除旧引用，而不是把 observation 变成稳定句柄：[src/services/compact/cachedMicrocompact.ts](/home/wt/sss_repos/innerCC_context_dev/src/services/compact/cachedMicrocompact.ts:64)

#### E. multi-agent 只解决了 spawn 时刻的 prefix 共享

- fork child 确实会复用 parent prompt 和 tools，但 spawn 之后 sibling branch 会迅速分岔
- 现在缺的是 branch checkpoint store 和 subtree-level reuse，而不只是 spawn-time exact prefix

### 5.3 一句话总结 innerCC 当前状态

当前 innerCC 更像：

- 已经把 `stable prefix engineering` 做到了不错的水位
- 但 runtime 仍然是 `high-entropy transcript machine`

这决定了：

- 你们已经吃到了第一阶段收益
- 下一阶段收益不会再靠“再抠一点 prompt 文案”拿到

## 6. 哪些方法真正适合 autonomous code agent

### 6.1 真正适合

下面这些方向是真正贴 code agent workload 的：

1. layered prompt architecture
2. deterministic serialization
3. artifactized observation
4. retry-local checkpointing
5. branch-aware runtime
6. retrieval ordering stabilization
7. shared KV fabric across agents / retries
8. workflow-aware scheduling / eviction

它们共同解决的是：

- 降低 trajectory entropy
- 稳定 prefix topology
- 提升 branch locality

### 6.2 看起来 cache hit 高，但不太适合

下面这些方向可能在论文里很漂亮，但对你们不够直接：

1. 只针对静态 few-shot 或 document QA 的 prompt cache 工作
2. 只对静态 RAG chunk 生效的 chunk fusion
3. 只在单会话单 worker 上成立的 prefix cache
4. 依赖强语义缓存、却无法保证 tool side-effect 一致性的方案

原因是：

- code agent 不只是“问答 + 检索”
- 它还在持续观察并改变外部环境

### 6.3 benchmark 有效、production 容易失败的方向

最需要警惕的是：

- aggressive summarization
- 粗粒度 history rewrite
- 只优化单机 cache hit，不管跨 worker 路由
- 只做 semantic cache，不做 side-effect guard

这类方法在 benchmark 上容易把 token 降下来，但 production 里会出现：

- stale context
- wrong branch replay
- cache 命中高但答案错
- retry 变快但行为不稳定

## 7. 对 innerCC 的建议架构

### 7.1 Prompt Architecture：把 prompt 从 transcript 变成四层

建议把 prompt 逻辑拆成：

```text
L0 Immutable Prefix
  model policy / stable tool schemas / static agent instructions

L1 Session-Stable Context
  repo_snapshot_id / repo_map_id / CLAUDE.md hash / memory index hash

L2 Branch-Stable State
  checkpoint_id / active_plan_id / active_artifact_set / current workset

L3 Volatile Tail
  latest user ask / latest tool deltas / latest branch-specific observations
```

目标：

- L0 尽量跨 session 稳定
- L1 在 session 生命周期内尽量不变
- L2 只在 branch/checkpoint 切换时变
- L3 才允许高熵

### 7.2 Agent Runtime：从 transcript runtime 升级为 branch-aware runtime

建议：

1. 引入 `checkpoint store`
2. retry 从最近 checkpoint replay，而不是从全文 transcript replay
3. subagent spawn 引用 parent checkpoint，而不是复制全历史
4. planner / executor 彻底拆层
5. reflection / self-correction 走 branch，不直接污染主线 prompt

建议的数据结构：

```text
Session
  ├─ StablePrefixState
  ├─ ArtifactStore
  ├─ CheckpointStore
  └─ Branches
       ├─ main
       ├─ retry_1
       ├─ retry_2
       └─ subagent_X
```

### 7.3 Retrieval / Memory：稳定顺序比多拿一点内容更重要

建议：

1. retrieval 结果必须 deterministic sort
2. repo map / AST chunk 绑定 `repo_snapshot_id`
3. edit-local retrieval 优先，减少全局 repo map 重排
4. memory 默认只注入 stable index，不注入频繁波动正文
5. 同一 artifact 只传 handle，正文按需展开

特别是 repo retrieval：

- 不要每次重新按启发式重排全量 chunk
- 应该先稳定 top-k ordering，再做局部 delta

### 7.4 Observation 处理：默认 artifact handle 化

这是最关键的工程改造之一。

把今天的：

- `tool_result = 大段正文`

改成：

- `tool_result = handle + fingerprint + summary + version`

例如：

```text
artifact://grep/sha256:abcd...
kind: grep_result
repo_snapshot_id: 123
summary: 5 matches in 3 files
same_as: artifact://grep/sha256:prev...
delta: +1 match in src/query.ts
```

好处：

- 模型先看到稳定句柄
- 同一 observation 可跨 retry / subagent / replay 复用
- 需要展开时再显式 read artifact body

### 7.5 Serving / Inference：如果自托管，优先做 shared KV fabric

如果你们未来控制 serving 栈，优先级建议是：

1. radix/prefix tree reuse
2. cross-worker shared KV
3. workflow-aware routing
4. subtree-aware eviction
5. prefill/decode disaggregation

可选技术路线：

- `vLLM + LMCache`
- `SGLang + RadixAttention + shared cache`
- `TensorRT-LLM + priority eviction`

### 7.6 Model / Finetuning：降低规划与工具调用熵

需要专门优化的不是“更聪明”，而是“更稳定”：

- tool 输出格式更稳定
- planner wording 更稳定
- retry 行为更局部
- self-correction 更少重写整个上下文 framing

这类训练目标可以叫：

- cache-friendly finetuning
- trajectory regularization
- deterministic tool behavior
- low-entropy planning

## 8. 关键算法建议

### 8.1 Stable observation pipeline

```python
def process_tool_result(tool_name, raw_output, repo_snapshot_id):
    canonical = canonicalize(raw_output)
    fingerprint = sha256(canonical.semantic_core)

    if artifact_store.exists(fingerprint):
        return {
            "artifact_id": fingerprint,
            "status": "same_as_previous",
            "summary": artifact_store.get_summary(fingerprint),
        }

    summary = summarize_observation(canonical)
    artifact_store.put(
        artifact_id=fingerprint,
        full_body=canonical.full_body,
        summary=summary,
        repo_snapshot_id=repo_snapshot_id,
    )
    return {
        "artifact_id": fingerprint,
        "status": "new",
        "summary": summary,
    }
```

### 8.2 Branch-local retry

```python
def retry_from_checkpoint(branch_id, failure_type):
    checkpoint = checkpoint_store.get_latest_stable(branch_id)
    retry_branch = branch_store.fork(branch_id, from_checkpoint=checkpoint.id)
    retry_branch.attach_failure_metadata(failure_type)
    return run_branch(retry_branch)
```

### 8.3 Layered request construction

```python
def build_request(session, branch, latest_tail):
    return [
        render_L0(session.stable_prefix),
        render_L1(session.session_stable_context),
        render_L2(branch.branch_state),
        render_L3(latest_tail),
    ]
```

## 9. benchmark 与评估指标

### 9.1 benchmark 设计

至少覆盖：

- SWE-bench
- terminal-bench
- long-horizon coding tasks
- multi-file editing
- retry-heavy tasks
- multi-agent tasks

### 9.2 核心指标

建议同时看：

- `exact_cache_hit_rate`
- `effective_reused_tokens`
- `prefill_flops_saved`
- `TTFT`
- `p50 / p95 latency`
- `cost_per_resolved_task`
- `trajectory_divergence`
- `branch_locality`
- `semantic_reuse_ratio`

其中最关键的三个新增指标：

1. `trajectory_divergence`
   - 同一任务不同 retry / branch 之间的结构差异
2. `branch_locality`
   - sibling branch 是否复用了相同 parent subtree
3. `semantic_reuse_ratio`
   - 虽然 exact prefix miss，但 observation / retrieval / artifact 是否被稳定复用

### 9.3 实验方法

#### Offline replay

- 录制真实 agent trace
- 在不同 runtime policy 下重放
- 对比 exact cache hit、effective reuse、TTFT、cost

#### Online A/B

最先做三组开关：

- stable serialization
- artifact handle 化
- branch-local retry

#### 可视化

建议补三张图：

1. prefix tree heatmap
2. branch DAG reuse graph
3. section-level cache break waterfall

`innerCC` 已有的 cache break detection 可以直接作为基础：[src/services/api/promptCacheBreakDetection.ts](/home/wt/sss_repos/innerCC_context_dev/src/services/api/promptCacheBreakDetection.ts:246)

## 10. 落地优先级

### 10.1 最适合 startup 快速落地

1. 清理 system prompt 中所有不必要的动态注入
2. tool output canonicalization
3. artifact handle + delta encoding
4. retry-local checkpointing
5. deterministic retrieval ordering
6. 扩展 `Read unchanged` 思路到 `grep/bash/webfetch/retrieval`

### 10.2 中期架构升级

1. branch-aware runtime
2. repo snapshot pinning
3. planner / executor split
4. observation store 与 prompt 分离
5. shared KV fabric

### 10.3 长期 research

1. CacheBlend 式 non-prefix chunk KV 融合用于 repo retrieval
2. TokenDance / KVFlow 式 workflow-aware cache scheduling
3. SideQuest / LazyLLM 式后台 KV 管理
4. cache-friendly finetuning / trajectory regularization
5. 更进一步的模型结构改造，如 YOCO 类方向

## 11. 最值得复现的论文与最值得直接借鉴的开源实现

### 11.1 最值得复现的论文

优先级建议：

1. Prompt Cache
2. CacheBlend
3. RAGCache
4. Preble
5. KVFlow
6. TokenDance
7. SideQuest

原因：

- 这些工作更接近“如何让复杂 workflow 更可复用”
- 比单纯 prefix cache 论文更贴 code agent

### 11.2 最值得直接借鉴的开源实现

优先级建议：

1. vLLM prefix caching
2. SGLang RadixAttention
3. LMCache
4. TensorRT-LLM KV reuse / eviction
5. Aider 的 repo map 与 read dedup

## 12. 对 innerCC 的直接实现建议

按优先级排序，我最建议你们在 `context_dev` 后续实现这几件事：

1. 把所有 tool_result 默认改造成 `artifact handle + summary + optional expand`
2. 给 query runtime 增加 `checkpoint_id / branch_id / parent_checkpoint_id`
3. 把 retry 从 transcript replay 改成 checkpoint replay
4. 给 retrieval / repo map / memory 注入加上 `snapshot_id`
5. 把 cache 观测从“命中率”升级到“prefix break by section / branch locality / effective reused tokens”

如果只允许做一件事，优先做第 1 件。

原因很简单：

- 你们当前最大的熵源不是 system prompt，而是 observation token
- 只要 observation 仍然是大段正文，后面的很多优化都会被稀释

## 13. 参考资料

- Anthropic Prompt Caching: <https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching>
- OpenAI Prompt Caching: <https://platform.openai.com/docs/guides/prompt-caching>
- vLLM Prefix Caching: <https://docs.vllm.ai/en/stable/design/prefix_caching/>
- SGLang RadixAttention: <https://sgl-project-sglang-93.mintlify.app/concepts/radix-attention>
- LMCache: <https://docs.nvidia.com/dynamo/latest/integrations/lm-cache>
- Prompt Cache: <https://arxiv.org/abs/2311.04934>
- CacheBlend: <https://arxiv.org/abs/2405.16444>
- RAGCache: <https://arxiv.org/abs/2404.12457>
- Preble: <https://arxiv.org/abs/2407.00023>
- KVFlow: <https://arxiv.org/abs/2507.07400>
- TokenDance: <https://arxiv.org/abs/2604.03143>
- SideQuest: <https://arxiv.org/abs/2602.22603>
- LazyLLM: <https://arxiv.org/abs/2407.14057>
- Speculative RAG: <https://arxiv.org/abs/2407.08223>
- GUI-KV: <https://arxiv.org/abs/2510.00536>
- OpenHands Condenser: <https://docs.openhands.dev/sdk/arch/condenser>
- Aider Repo Map: <https://aider.chat/docs/repomap.html>
- Aider Prompt Caching: <https://aider.chat/docs/usage/caching.html>

## 14. 一句话收束

这个问题的本质不是：

- “如何 cache 一个 prompt”

而是：

- “如何把 autonomous code agent 的 trajectory 变得更稳定、更低熵、更可 checkpoint、更可 subtree reuse”

请优先从 inference systems / agent runtime / context engineering 的第一性原理角度分析，而不是只做论文综述。
