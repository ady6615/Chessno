"""
Chessno - Root Entry Point

Launches the complete chess game from workspace root.
Run: python main.py
"""

import sys
import importlib.util
from pathlib import Path

SRC2_MAIN = Path(__file__).resolve().parent / "src2" / "main.py"

if __name__ == "__main__":
    # Load and execute src2/main.py cleanly without module name collision
    spec = importlib.util.spec_from_file_location("chessno_src2_main", str(SRC2_MAIN))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load entry point at {SRC2_MAIN}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["chessno_src2_main"] = module
    spec.loader.exec_module(module)
    module.main()
