from __future__ import annotations

import argparse
import subprocess
import sys

from .verifier_prompt import build_verifier_prompt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="clone_driver.claude_verifier")
    parser.add_argument("--model", default="")
    parser.add_argument("--effort", default="")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    packet_text = sys.stdin.read()
    prompt = build_verifier_prompt(packet_text)
    command = ["claude", "-p"]
    if args.model:
        command.extend(["--model", args.model])
    if args.effort:
        command.extend(["--effort", args.effort])
    command.append(prompt)
    result = subprocess.run(
        command,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        return result.returncode
    print(result.stdout.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
