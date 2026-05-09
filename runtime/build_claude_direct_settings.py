#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from urllib.parse import urlparse

from swe_evo_env import default_env_file, default_model_name


DEFAULT_DIRECT_ANTHROPIC_BASE_URL = "https://api.minimaxi.com/anthropic"


def load_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped[len("export ") :]
        if "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        env[key.strip()] = value.strip().strip("'").strip('"')
    return env


def looks_local_url(value: str) -> bool:
    try:
        hostname = urlparse(value).hostname
    except Exception:
        return False
    return hostname in {"127.0.0.1", "localhost"}


def choose_token(env: dict[str, str]) -> str | None:
    for key in (
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_API_KEY",
        "ENTERPRISE_API_KEY",
        "OPENAI_API_KEY",
    ):
        value = env.get(key)
        if value:
            return value
    return None


def choose_base_url(env: dict[str, str]) -> str:
    for key in ("ENTERPRISE_ANTHROPIC_BASE_URL", "ANTHROPIC_BASE_URL"):
        value = env.get(key)
        if value and not looks_local_url(value):
            return value
    return DEFAULT_DIRECT_ANTHROPIC_BASE_URL


def choose_model(env: dict[str, str], model_override: str | None) -> str:
    if model_override:
        return model_override
    for key in ("ANTHROPIC_MODEL", "SWE_AGENT_MODEL", "INNERCC_MODEL"):
        value = env.get(key)
        if value:
            return value
    return default_model_name()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--env-file", default=str(default_env_file()))
    parser.add_argument("--model", default="")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    env_file = Path(args.env_file).expanduser().resolve()
    if not env_file.exists():
        raise FileNotFoundError(env_file)

    output_path = Path(args.output).expanduser().resolve()
    if output_path.exists() and not args.overwrite:
        raise SystemExit(f"output already exists: {output_path}")

    env = load_env_file(env_file)
    token = choose_token(env)
    if not token:
        raise SystemExit(f"could not find API token in {env_file}")

    payload = {
        "$schema": "https://json.schemastore.org/claude-code-settings.json",
        "autoUpdatesChannel": "latest",
        "skipDangerousModePermissionPrompt": True,
        "env": {
            "ANTHROPIC_BASE_URL": choose_base_url(env),
            "ANTHROPIC_MODEL": choose_model(env, args.model or None),
            "ANTHROPIC_AUTH_TOKEN": token,
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output_path),
                "env_file": str(env_file),
                "model": payload["env"]["ANTHROPIC_MODEL"],
                "base_url": payload["env"]["ANTHROPIC_BASE_URL"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
