#!/usr/bin/env python3
"""Format files to match pre-commit hook requirements."""

import subprocess
import sys
from pathlib import Path

repo = Path("/home/mcs/Projects/lost-hiker")


def run(cmd, **kwargs):
    """Run command and show output."""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, **kwargs)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result


# Step 1: Format with ruff format
print("=== Formatting with ruff format ===")
run(["uv", "run", "ruff", "format", "."])

# Step 2: Format with black
print("\n=== Formatting with black ===")
run(["uv", "run", "black", "."])

# Step 3: Run pre-commit hooks to see what they change
print("\n=== Running pre-commit hooks ===")
result = run(
    ["uv", "run", "pre-commit", "run", "ruff-format", "black", "--all-files"],
    check=False,
)

# Step 4: If hooks modified files, format again
if result.returncode != 0:
    print("\n=== Hooks modified files, formatting again ===")
    run(["uv", "run", "ruff", "format", "."])
    run(["uv", "run", "black", "."])

# Step 5: Verify ruff check
print("\n=== Verifying ruff check ===")
result = run(["uv", "run", "ruff", "check", "src/lost_hiker"], check=False)
if result.returncode != 0:
    print("ERROR: ruff check failed!")
    sys.exit(1)

# Step 6: Stage all changes
print("\n=== Staging all changes ===")
run(["git", "add", "-A"])

print("\n=== Done! Files are formatted and staged. ===")
