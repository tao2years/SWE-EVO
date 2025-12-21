#!/usr/bin/env bash
set -euo pipefail

#1
./evaluation/benchmarks/swe_bench/scripts/run_infer.sh \
  llm.fireworks_gpt-oss-120b \
  HEAD \
  CodeActAgent \
  52 100 3 \
  /mnt/data/swe_world_2/SWE-EVO/hf_out/hf_jsonl \
  test \
  1 \
  swe

#2
./evaluation/benchmarks/swe_bench/scripts/run_infer.sh \
  llm.fireworks_kimi \
  HEAD \
  CodeActAgent \
  52 100 3 \
  /mnt/data/swe_world_2/SWE-EVO/hf_out/hf_jsonl \
  test \
  1 \
  swe

#2
./evaluation/benchmarks/swe_bench/scripts/run_infer.sh \
  llm.fireworks_qwen3_480 \
  HEAD \
  CodeActAgent \
  52 100 3 \
  /mnt/data/swe_world_2/SWE-EVO/hf_out/hf_jsonl \
  test \
  1 \
  swe

#4
./evaluation/benchmarks/swe_bench/scripts/run_infer.sh \
  llm.fireworks_glm-4p5 \
  HEAD \
  CodeActAgent \
  52 100 3 \
  /mnt/data/swe_world_2/SWE-EVO/hf_out/hf_jsonl \
  test \
  1 \
  swe

#5
./evaluation/benchmarks/swe_bench/scripts/run_infer.sh \
  llm.fireworks_deepseek-r1-0528 \
  HEAD \
  CodeActAgent \
  52 100 3 \
  /mnt/data/swe_world_2/SWE-EVO/hf_out/hf_jsonl \
  test \
  1 \
  swe