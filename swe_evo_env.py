from __future__ import annotations

import os
import shlex
import shutil
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
CONFIG_ROOT = REPO_ROOT / "config"
DEFAULT_MODEL_NAME = "MiniMax-M2.5-highspeed"
DEFAULT_AGENT_NAME = "innercc-cli"
DEFAULT_ROUTER_API_BASE = "http://127.0.0.1:18783"


def _dedupe_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        key = str(path)
        if key in seen:
            continue
        seen.add(key)
        unique.append(path)
    return unique


def first_existing_path(paths: list[Path]) -> Path:
    for path in paths:
        if path.exists():
            return path
    return paths[0]


def default_deps_path() -> Path:
    return Path(os.environ.get("SWE_EVO_DEPS_PATH", REPO_ROOT / ".deps")).expanduser()


def pythonpath_entries(*extra_paths: str | Path) -> list[str]:
    entries: list[str] = []
    deps_path = default_deps_path()
    if os.environ.get("SWE_EVO_DEPS_PATH") or deps_path.exists():
        entries.append(str(deps_path))
    for path in extra_paths:
        if not path:
            continue
        entries.append(str(Path(path).expanduser()))
    return list(dict.fromkeys(entries))


def prepend_pythonpath(env: dict[str, str], *extra_paths: str | Path) -> dict[str, str]:
    updated_env = dict(env)
    entries = pythonpath_entries(*extra_paths)
    if not entries:
        return updated_env
    current = updated_env.get("PYTHONPATH", "")
    updated_env["PYTHONPATH"] = os.pathsep.join(entries + ([current] if current else []))
    return updated_env


def shell_quote(value: str | Path) -> str:
    return shlex.quote(str(value))


def shell_join(parts: list[str | Path | int]) -> str:
    return " ".join(shell_quote(str(part)) for part in parts)


def shell_python_env_prefix(*extra_paths: str | Path) -> str:
    entries = pythonpath_entries(*extra_paths)
    if not entries:
        return ""
    return f"PYTHONPATH={shell_quote(os.pathsep.join(entries))} "


def cli_bin_candidates() -> list[Path]:
    candidates: list[Path] = []
    env_value = os.environ.get("INNERCC_CLI_BIN")
    if env_value:
        candidates.append(Path(env_value).expanduser())
    candidates.extend(
        [
            REPO_ROOT.parent / "innerCC" / "cli",
            REPO_ROOT.parent.parent / "innerCC" / "cli",
            Path.home() / "repo" / "innerCC" / "cli",
            Path.home() / "sss_repos" / "innerCC" / "cli",
        ]
    )
    for command_name in ("innercc", "claude"):
        resolved = shutil.which(command_name)
        if resolved:
            candidates.append(Path(resolved))
    candidates.extend([Path("innercc"), Path("claude")])
    return _dedupe_paths(candidates)


def cli_binary_available(path: Path) -> bool:
    return path.exists() or shutil.which(str(path)) is not None


def default_cli_bin_path() -> Path:
    candidates = cli_bin_candidates()
    for candidate in candidates:
        if cli_binary_available(candidate):
            return candidate
    return candidates[0]


def settings_path_candidates() -> list[Path]:
    candidates: list[Path] = []
    env_value = os.environ.get("INNERCC_SETTINGS_PATH")
    if env_value:
        candidates.append(Path(env_value).expanduser())
    candidates.extend(
        [
            CONFIG_ROOT / "claude.settings.json",
            Path.home() / ".claude" / "settings.json",
        ]
    )
    return _dedupe_paths(candidates)


def default_settings_path() -> Path:
    return first_existing_path(settings_path_candidates())


def env_file_candidates() -> list[Path]:
    candidates: list[Path] = []
    env_value = os.environ.get("INNERCC_ENV_FILE")
    if env_value:
        candidates.append(Path(env_value).expanduser())
    candidates.extend(
        [
            CONFIG_ROOT / "swe-evo.env",
            Path.home() / ".config" / "swe-evo" / "minimax.env",
        ]
    )
    return _dedupe_paths(candidates)


def default_env_file() -> Path:
    return first_existing_path(env_file_candidates())


def default_model_name() -> str:
    return os.environ.get("INNERCC_MODEL", DEFAULT_MODEL_NAME)


def default_agent_name() -> str:
    return os.environ.get("INNERCC_AGENT_NAME", DEFAULT_AGENT_NAME)


def router_root_candidates() -> list[Path]:
    candidates: list[Path] = []
    env_value = os.environ.get("LLM_ROUTER_ROOT")
    if env_value:
        candidates.append(Path(env_value).expanduser())
    candidates.extend(
        [
            REPO_ROOT.parent / "llm_router",
            REPO_ROOT.parent.parent / "llm_router",
            Path.home() / "sss_repos" / "sss_auto" / "llm_router",
        ]
    )
    return _dedupe_paths(candidates)


def default_router_root() -> Path:
    return first_existing_path(router_root_candidates())


def default_router_db_path() -> Path:
    env_value = os.environ.get("SWE_EVO_ROUTER_DB_PATH")
    if env_value:
        return Path(env_value).expanduser()
    return default_router_root() / "proxy" / "data" / "traces.db"


def default_router_api_base() -> str:
    return os.environ.get("SWE_EVO_ROUTER_API_BASE", DEFAULT_ROUTER_API_BASE)


def default_official48_source_root() -> Path:
    return Path(os.environ.get("OFFICIAL48_SOURCE_ROOT", REPO_ROOT / "official48_source")).expanduser()
