# cache trace 对照：dask__dask_2024.3.1_2024.4.0

## 选 case 依据

- 选择原因: picked by max historical cache-hit gap between Claude Code and innercc context rerun
- 历史命中率: Claude=0.7379, innercc=0.0988, gap=0.6392

## 关键结论

- 两边共享完全相同的请求前缀 trace 数: 33。
- Claude 总 trace 数: 33，innercc 总 trace 数: 133。
- Claude 首次 request shrink / msg reset: None；innercc 首次 request shrink / msg reset: 33。
- Claude 最大 input_tokens: 16058；innercc 最大 input_tokens: 76706。
- Claude 最大 request body: 168837；innercc 最大 request body: 333151。

## innercc 关键转折点

- innercc 在 turn 33 出现 request shrink，body bytes 变为 20604，msg_count 变为 1，cache_read_input_tokens 变为 3840。
- 该 turn 相对上一轮 body bytes 变化: -148233
- 该 turn 相对上一轮 msg_count 变化: -64

## 对比判断

- 前半段共享长前缀，说明不是首轮 prompt 大小差异导致命中率差。
- innercc 中途发生 history rewrite / compact 风格的 request shrink，而 Claude 没有，这通常会打断已建立的 cache 前缀。
- innercc 后续又继续跑了更多轮，使新增输入 token 持续累积，进一步摊薄 cache_read 的贡献。

