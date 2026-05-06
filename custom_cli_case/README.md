# Custom CLI Benchmark Flow

This directory contains a minimal end-to-end flow for evaluating a custom CLI code agent against one SWE-EVO instance.

## What This Flow Does

1. Reads one benchmark instance from `custom_cli_case/output_final/<instance>.json`.
2. Creates a local git workspace checked out to the benchmark `base_commit`.
3. Runs the custom CLI agent in non-interactive mode.
4. Captures the resulting `git diff` as `preds.json`.
5. Builds the SWE-bench harness environment locally and evaluates that prediction.

The current starter case is:

- `psf__requests_v2.27.0_v2.27.1`

## Files

- `run_custom_cli_case.py`: generic Python driver
- `run_requests_case.sh`: one-command launcher for the starter case
- `output_final/`: per-instance benchmark inputs
- `hf_dataset/`: single-instance dataset snapshot
- `workspace/`: materialized git workspaces
- `run/<instance>/`: agent output, patch, predictions, and summary

## Required External Inputs

- Custom CLI binary:
  `INNERCC_CLI_BIN=/path/to/your/cli`
- Claude-style settings file:
  `config/claude.settings.json` or `INNERCC_SETTINGS_PATH`
- Provider credentials file:
  `config/swe-evo.env` or `INNERCC_ENV_FILE`

The driver uses:

- `ANTHROPIC_API_KEY=$OPENAI_API_KEY`
- `ANTHROPIC_BASE_URL=https://api.minimaxi.com/anthropic`

and runs the CLI in:

- `--bare`
- `-p`
- `--output-format json`
- `--dangerously-skip-permissions`

## Run

```bash
bash ./custom_cli_case/run_requests_case.sh
```

You can also override the CLI path explicitly:

```bash
INNERCC_CLI_BIN=/path/to/your/cli \
  bash ./custom_cli_case/run_requests_case.sh
```

## Main Outputs

For one instance, outputs land under:

`custom_cli_case/run/<instance_id>/`

Important files:

- `cli_result.json`: parsed final CLI JSON result
- `cli_stdout.log`: raw stdout from the CLI, including any extra log lines
- `cli_stderr.log`: stderr from the CLI
- `patch.diff`: patch captured from `git diff`
- `preds.json`: SWE-agent-compatible prediction file
- `summary.json`: quick pointers to key outputs

Evaluation outputs land under:

- `logs/run_evaluation/<run_id>/<run_id>/<instance_id>/`

Important files there:

- `report.json`
- `test_output.txt`
- `run_instance.log`

## Notes

- This flow does not depend on the built-in SWE-agent or OpenHands inference loop.
- It reuses only the benchmark instance format and the existing SWE-bench evaluation harness.
- Evaluation is done via local harness image builds, not by pulling the benchmark's prebuilt instance image.
- The prompt explicitly tells the custom CLI agent not to modify tests.
- `SWE-bench/evaluate_instance.py` now accepts `--scaffold CustomCLI` for `preds.json`-style outputs.
