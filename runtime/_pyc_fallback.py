from __future__ import annotations

from importlib.machinery import SourcelessFileLoader
from importlib.util import module_from_spec, spec_from_loader
from pathlib import Path
from types import ModuleType


def load_pyc_sibling(py_file: str, module_name: str) -> ModuleType:
    py_path = Path(py_file).resolve()
    pyc_name = f"{py_path.stem}.cpython-312.pyc"
    pyc_path = py_path.with_name("__pycache__") / pyc_name
    if not pyc_path.is_file():
        raise FileNotFoundError(f"Missing fallback bytecode: {pyc_path}")

    loader = SourcelessFileLoader(f"_{module_name}_bytecode", str(pyc_path))
    spec = spec_from_loader(loader.name, loader)
    if spec is None:
        raise ImportError(f"Unable to create import spec for {pyc_path}")

    module = module_from_spec(spec)
    loader.exec_module(module)
    return module


def export_public(module: ModuleType, target_globals: dict) -> None:
    for key, value in vars(module).items():
        if key in {"__builtins__", "__cached__", "__file__", "__loader__", "__name__", "__package__", "__spec__"}:
            continue
        target_globals[key] = value

