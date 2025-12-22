<h1 align="center">SWE-EVO</h1>

<p align="center">
  <strong>Benchmarking Coding Agents in Long-Horizon Software Evolution Scenarios</strong>
</p>

<p align="center">
Evaluate AI agents on realistic software evolution • Multi-step planning and adaptation • Long-horizon reasoning challenges
</p>

<p align="center">
  <a href="https://arxiv.org/abs/XXXX.XXXXX"><img alt="Paper" src="https://img.shields.io/badge/arXiv-XXXX.XXXXX-b31b1b.svg?style=flat-square" /></a>
  <a href="./LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square" /></a>
  <a href="https://www.python.org/downloads/"><img alt="Python" src="https://img.shields.io/badge/python-%3E%3D3.10-blue.svg?style=flat-square" /></a>
  <a href="https://github.com/FSoft-AI4Code/SWE-EVO/issues"><img alt="Issues" src="https://img.shields.io/github/issues/FSoft-AI4Code/SWE-EVO?style=flat-square" /></a>
  <a href="https://github.com/FSoft-AI4Code/SWE-EVO/stargazers"><img alt="Stars" src="https://img.shields.io/github/stars/FSoft-AI4Code/SWE-EVO?style=flat-square" /></a>
</p>

<p align="center">
  <a href="#introduction"><strong>Introduction</strong></a> •
  <a href="#quick-start"><strong>Quick Start</strong></a> •
  <a href="#how-it-works"><strong>How It Works</strong></a> •
  <a href="#evaluation"><strong>Evaluation</strong></a> •
  <a href="#acknowledgements"><strong>Acknowledgements</strong></a>
</p>

---

## Introduction

SWE-EVO is a benchmark designed to evaluate AI coding agents in **autonomous software evolution** tasks. Unlike benchmarks that focus on isolated coding problems, SWE-EVO simulates realistic scenarios where agents must iteratively evolve complex codebases according to high-level software requirement specifications (SRS).

Using versioned histories from real Python open-source projects (such as **Django** and **NumPy**), SWE-EVO challenges agents to:

- **Interpret** high-level software requirement specifications
- **Plan** and implement multi-step changes
- **Navigate** large-scale repositories with thousands of files
- **Produce** correct changes across multiple versions

### The Research Question

> *Given an existing codebase and evolving requirements, can AI agents autonomously perform sustained planning, adaptation, and evolution over long interactions?*

---

## Key Features

| Feature | Description |
|---------|-------------|
| **Realistic Tasks** | Derived from authentic project evolution histories, emphasizing change over time |
| **Multi-Step Evaluation** | Agents must plan, update, and validate changes across versions |
| **Modular Scaffolds** | Supports evaluation via [OpenHands](https://github.com/All-Hands-AI/OpenHands) and [SWE-agent](https://github.com/princeton-nlp/SWE-agent) |
| **Public Dataset** | Curated instances with tools for reproducible evaluation |
| **Long-Horizon Focus** | Challenges AI systems with iterative evolution and sustained reasoning |

---

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/FSoft-AI4Code/SWE-EVO.git
cd SWE-EVO
```

### 2. Install Dependencies

```bash
pip install -e .
```

### 3. Run Evaluation

```bash
python SWE-bench/evaluate_instance.py \
  --trajectories_path <path-to-your-trajectories> \
  --max_workers <num_workers> \
  --scaffold <scaffold_name>
```

---

## How It Works

<p align="center">
  <img src="img/evolution_process.png" alt="Software Evolution Model" width="700"/>
</p>

<p align="center">
  <em>Conceptual model of software evolution in SWE-EVO: from base system to evolved system through requirement interpretation and change execution.</em>
</p>

### Evolution Process

```
┌──────────────────┐
│   Base Codebase  │  Initial state of the repository
└────────┬─────────┘
         │
         ↓
┌──────────────────┐
│   SRS Document   │  High-level requirements specification
└────────┬─────────┘
         │
         ↓
┌──────────────────┐
│   AI Agent       │  Plans and implements changes
└────────┬─────────┘
         │
         ↓
┌──────────────────┐
│ Evolved Codebase │  Updated repository matching requirements
└──────────────────┘
```

---

## Evaluation

### Using OpenHands Scaffold

```bash
python SWE-bench/evaluate_instance.py \
  --trajectories_path /path/to/openhands/outputs \
  --max_workers 8 \
  --scaffold OpenHands
```

### Using SWE-agent Scaffold

```bash
python SWE-bench/evaluate_instance.py \
  --trajectories_path /path/to/sweagent/outputs \
  --max_workers 8 \
  --scaffold SWE-agent
```

### Parameters

| Parameter | Description |
|-----------|-------------|
| `--trajectories_path` | Path to your agent trajectory outputs |
| `--max_workers` | Number of parallel workers for evaluation |
| `--scaffold` | Scaffold name (`OpenHands` or `SWE-agent`) |

---

## Requirements

- Python 3.10+
- Compatible scaffold installation ([OpenHands](https://github.com/All-Hands-AI/OpenHands) or [SWE-agent](https://github.com/princeton-nlp/SWE-agent))

---

## Contributing

Contributions are welcome! Please feel free to submit issues or pull requests.

---

## Acknowledgements

SWE-EVO builds on the original [SWE-bench](https://www.swebench.com/) benchmark. We are grateful to the SWE-bench team for their foundational work in software engineering evaluation.

Special thanks to:

- **[SWE-bench](https://www.swebench.com/)** for pioneering software engineering benchmarks for AI
- **[OpenHands](https://github.com/All-Hands-AI/OpenHands)** for their open-source AI agent framework
- **[SWE-agent](https://github.com/princeton-nlp/SWE-agent)** for their agent scaffold and tooling
- The open-source community behind **Django**, **NumPy**, and other projects used in this benchmark

---

## License

MIT License - See [LICENSE](./LICENSE) for details.

---

## Citation

```bibtex
@article{sweevo2024,
  title={SWE-EVO: Benchmarking Coding Agents in Long-Horizon Software Evolution Scenarios},
  author={...},
  journal={arXiv preprint arXiv:XXXX.XXXXX},
  year={2024}
}
```

---

<p align="center">
  <a href="https://github.com/FSoft-AI4Code/SWE-EVO">GitHub</a> •
  <a href="https://arxiv.org/abs/XXXX.XXXXX">Paper</a> •
  <a href="https://github.com/FSoft-AI4Code/SWE-EVO/issues">Issues</a>
</p>
