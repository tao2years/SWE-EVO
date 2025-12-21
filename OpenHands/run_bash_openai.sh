#!/usr/bin/env bash
set -euo pipefail

# # Template
# ./evaluation/benchmarks/swe_bench/scripts/run_infer.sh \
#   llm.openai_o3-2025-04-16 \ # Your model
#   HEAD \
#   CodeActAgent \
#   52 100 3 \
#   hf_data_path \
#   test \
#   1 \

#0
./evaluation/benchmarks/swe_bench/scripts/run_infer.sh \
  llm.openai_gpt-5-pro-2025-10-06 \
  HEAD \
  CodeActAgent \
  52 100 3 \
  /mnt/data/swe_world_2/SWE-EVO/hf_out/hf_jsonl \
  test \
  1 \
  swe

#1
./evaluation/benchmarks/swe_bench/scripts/run_infer.sh \
  llm.openai_gpt-5-nano-2025-08-07 \
  HEAD \
  CodeActAgent \
  52 100 3 \
  /mnt/data/swe_world_2/SWE-EVO/hf_out/hf_jsonl \
  test \
  1 \
  swe

#2
./evaluation/benchmarks/swe_bench/scripts/run_infer.sh \
  llm.openai_gpt-5-mini-2025-08-07 \
  HEAD \
  CodeActAgent \
  52 100 3 \
  /mnt/data/swe_world_2/SWE-EVO/hf_out/hf_jsonl \
  test \
  1 \
  swe

#3
./evaluation/benchmarks/swe_bench/scripts/run_infer.sh \
  llm.openai_gpt-5-2025-08-07 \
  HEAD \
  CodeActAgent \
  52 100 3 \
  /mnt/data/swe_world_2/SWE-EVO/hf_out/hf_jsonl \
  test \
  1 \
  swe

#4
./evaluation/benchmarks/swe_bench/scripts/run_infer.sh \
  llm.openai_gpt-4_1-2025-04-14 \
  HEAD \
  CodeActAgent \
  52 100 3 \
  /mnt/data/swe_world_2/SWE-EVO/hf_out/hf_jsonl \
  test \
  1 \
  swe

#5
./evaluation/benchmarks/swe_bench/scripts/run_infer.sh \
  llm.openai_gpt-4o-2024-11-20 \
  HEAD \
  CodeActAgent \
  52 100 3 \
  /mnt/data/swe_world_2/SWE-EVO/hf_out/hf_jsonl \
  test \
  1 \
  swe

#6
./evaluation/benchmarks/swe_bench/scripts/run_infer.sh \
  llm.openai_o3-2025-04-16 \
  HEAD \
  CodeActAgent \
  52 100 3 \
  /mnt/data/swe_world_2/SWE-EVO/hf_out/hf_jsonl \
  test \
  1 \