"""Cross-platform offline quality runner; no downloads, models, or credentials."""

import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
for arguments in [("ruff", "check", "."), ("ruff", "format", "--check", "."), ("pytest",)]:
    subprocess.run([sys.executable, "-m", *arguments], cwd=root, check=True)
print("Offline quality checks passed.")
