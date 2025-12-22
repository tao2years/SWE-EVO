<center>

# SWE-EVO: A Frontier Benchmark for Coding Agents in Autonomous Software Evolution

</center>

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![GitHub Issues](https://img.shields.io/github/issues/FSoft-AI4Code/SWE-World.svg)](https://github.com/FSoft-AI4Code/SWE-World/issues)
[![GitHub Stars](https://img.shields.io/github/stars/FSoft-AI4Code/SWE-World.svg?style=social)](https://github.com/FSoft-AI4Code/SWE-World/stargazers)

## Overview

SWE-EVO is a cutting-edge benchmark designed to evaluate the capabilities of AI coding agents in autonomous software evolution. Unlike traditional benchmarks like SWE-Bench, which focus on resolving isolated GitHub issues, SWE-EVO simulates real-world software engineering scenarios where agents must iteratively evolve large-scale, legacy codebases in alignment with high-level Software Requirement Specifications (SRS).

By leveraging release notes, commit histories, and versioned snapshots from popular open-source Python projects (e.g., Django, NumPy), SWE-EVO challenges coding agents to:
- Interpret SRS and plan multi-step modifications.
- Navigate complex repositories with thousands of files.
- Implement iterative changes across multiple versions while ensuring compatibility and functionality.

This benchmark addresses a critical research question: *Given an existing codebase, can multi-agent LLM systems autonomously evolve the system in response to dynamic input requirements, demonstrating sustained planning, adaptability, and innovation across long-horizon tasks?*

SWE-EVO sets a new standard for assessing long-term reasoning, multi-agent collaboration, and codebase-scale performance in AI-driven software engineering.

**Paper**: [SWE-EVO: A Frontier Benchmark for Coding Agents in Autonomous Software Evolution](https://arxiv.org/abs/XXXX.XXXXX)

## Key Features

- **Realistic Evolution Scenarios**: Tasks derived from actual open-source project histories, emphasizing maintenance and enhancement (which constitute up to 80% of SE efforts).
- **Multi-Step Tasks**: Agents must handle SRS interpretation, impact analysis, change identification, and evolution processes (see conceptual model below).
- **Scalable Evaluation**: Supports baseline agents like GPT-4, CodeLlama, and multi-agent frameworks (e.g., HyperAgent).
- **Public Dataset**: Includes curated instances from Python OSS projects, with tools for reproducibility and extension.
- **Metrics**: Success rates, code quality (via linting/tests), efficiency, and qualitative analysis of failure modes.

![Software Evolution Model](img/evolution_process.png)  
*Conceptual model of software evolution in SWE-EVO, illustrating the cycle from existing system to new system through change identification, impact analysis, and the evolution process.*

## Setup

- Python >= 3.10
- pip install -e .

## Evaluation

python SWE-bench/evaluate_instance.py \
  --trajectories_path <path-to-your-trajectories> \
  --max_workers <num_workers> \
  --scaffold <scaffold_name>

Example with Openhands scaffold and model is gpt-5-2025-08-07:

python SWE-bench/evaluate_instance.py \
  --trajectories_path /workspace/tue/swe_world_2/OpenHands/evaluation/evaluation_outputs/outputs/__mnt__data__swe_world_2__SWE-EVO__hf_out__hf_jsonl-test/CodeActAgent/gpt-5-2025-08-07_maxiter_100_N_v0.58.0-no-hint-run_1 \
  --max_workers 8 \
  --scaffold OpenHands

## Acknowledgements
SWE-EVO builds on the original [SWE-bench](https://www.swebench.com/) benchmark, and we acknowledge the SWE-bench team for their foundational contribution to software-engineering evaluation.
