from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

from .verifier_prompt import build_verifier_prompt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="clone_driver.codex_verifier")
    parser.add_argument("--model", default="")
    parser.add_argument("--effort", default="")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    packet_text = sys.stdin.read()
    prompt = build_verifier_prompt(packet_text)

    with tempfile.NamedTemporaryFile(
        prefix="rightseat-verifier-codex-", suffix=".json", delete=False
    ) as output:
        output_path = Path(output.name)
    try:
        command = [
            "codex",
            "exec",
            "-s",
            "read-only",
            "--skip-git-repo-check",
            "--ignore-rules",
            "-o",
            str(output_path),
        ]
        if args.model:
            command.extend(["--model", args.model])
        if args.effort:
            command.extend(["-c", f'model_reasoning_effort="{args.effort}"'])
        command.append(prompt)
        result = subprocess.run(
            command,
            check=False,
            cwd="/tmp",
            stdin=subprocess.DEVNULL,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if result.returncode != 0:
            sys.stderr.write(result.stderr or result.stdout)
            return result.returncode
        print(output_path.read_text(encoding="utf-8").strip())
        return 0
    finally:
        try:
            output_path.unlink()
        except OSError:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
