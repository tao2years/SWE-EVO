# cache trace 对照：dask__dask_2024.3.1_2024.4.0

## 选 case 依据

- 选择原因: picked by max historical cache-hit gap between Claude Code and innercc context rerun
- 历史命中率: Claude=0.7379, innercc=0.0988, gap=0.6392

## 关键结论

- 两边共享完全相同的请求前缀 trace 数: 0。
- Claude 总 trace 数: 30，innercc 总 trace 数: 33。
- Claude 首次 request shrink / msg reset: None；innercc 首次 request shrink / msg reset: None。
- Claude 最大 input_tokens: 18179；innercc 最大 input_tokens: 25719。
- Claude 最大 request body: 173601；innercc 最大 request body: 122521。
- 首轮 cache_create 对比: Claude=24142；innercc=876。
- 首轮 cache_read 对比: Claude=0；innercc=4016。

## 对比判断

- 两边从第 0 轮开始就不是同一个精确前缀，说明 live run 下还存在 prompt 构造层面的前缀不一致。
- live run 下更明显的现象是 innercc 首轮可缓存前缀更小，后续每轮 cache_read 也显著低于 Claude。
- innercc 后续又继续跑了更多轮，使新增输入 token 持续累积，进一步摊薄 cache_read 的贡献。

