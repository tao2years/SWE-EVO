# Repository Guidelines

## Project Structure & Module Organization
The repository has two main layers. Root-level Python scripts drive SWE-EVO workflows such as single-case validation, `official48` inference, monitoring, and evaluation. The reusable benchmark package lives in `SWE-bench/swebench/`, with tests in both `tests/` and `SWE-bench/tests/`. The Next.js dashboard is under `app/` and `components/`; static dashboard assets live in `dashboard/`. Configuration templates are in `config/`, docs are in `docs/`, and sample or generated benchmark data lives under `official48_source/` and `custom_cli_case/`.

## Build, Test, and Development Commands
Run `bash ./bootstrap_env.sh` to create `.venv`, install Python dependencies, and run `npm ci`. Activate the environment with `source .venv/bin/activate`.

Use `pytest tests -q` for the root regression suite. If you touch harness internals in `SWE-bench/swebench/`, also run `pytest SWE-bench/tests -q`. Start the dashboard locally with `npm run dashboard:dev`; build production assets with `npm run build` and serve them with `npm run dashboard:start`. For script discovery, prefer `python3 run_innercc_infer_official48.py --help` or `python3 run_official48_eval_worker.py --help`.

## Coding Style & Naming Conventions
Follow existing style instead of reformatting unrelated files. Python uses 4-space indentation, standard-library-first imports, and descriptive snake_case names; prefer `pathlib.Path` for filesystem work and keep helper functions small. Frontend code in `app/` and `components/` uses functional React components, 2-space indentation, and lower-case route filenames such as `app/dashboard/page.js`.

Run `pre-commit run --all-files` before opening a PR. The configured hooks run `ruff` linting and `ruff-format`.

## Testing Guidelines
Add or update `test_*.py` files alongside the area you change. Keep tests focused on command behavior, data transforms, and failure handling; existing suites mix `pytest` functions with `unittest.TestCase`, so match the surrounding file. For CLI-facing changes, include at least one smoke path and one edge case.

## Commit & Pull Request Guidelines
Recent history favors short, imperative commit subjects such as `Add init instructions for subset workspace` and scoped variants like `docs: expand official48 suite and failure analysis notes`. Keep commits focused and explain operational impact in the body when changing run pipelines.

PRs should include a concise summary, linked issue or task when available, commands you ran, and screenshots for dashboard UI changes. Do not commit secrets or local overrides such as `config/claude.settings.json`, `config/swe-evo.env`, or run artifacts under `official48_runs/`.
