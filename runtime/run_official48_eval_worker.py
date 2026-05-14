from __future__ import annotations

from _pyc_fallback import export_public, load_pyc_sibling


_MODULE = load_pyc_sibling(__file__, "run_official48_eval_worker")
export_public(_MODULE, globals())


if __name__ == "__main__":
    _MODULE.main()

