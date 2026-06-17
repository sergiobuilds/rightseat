from __future__ import annotations

import json
import subprocess
from pathlib import Path


class ArtifactCollector:
    def collect(self, *, workdir: Path, out_dir: Path, test_cmd: list[str]) -> Path:
        out_dir.mkdir(parents=True, exist_ok=True)
        diff_path = out_dir / "git-diff.txt"
        staged_diff_path = out_dir / "git-diff-staged.txt"
        status_path = out_dir / "git-status.txt"
        untracked_path = out_dir / "untracked-files.txt"
        stdout_path = out_dir / "test-stdout.txt"
        stderr_path = out_dir / "test-stderr.txt"
        manifest_path = out_dir / "manifest.json"

        diff = subprocess.run(
            ["git", "-C", str(workdir), "diff"],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        diff_path.write_text(diff.stdout + diff.stderr, encoding="utf-8")

        staged = subprocess.run(
            ["git", "-C", str(workdir), "diff", "--cached"],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        staged_diff_path.write_text(staged.stdout + staged.stderr, encoding="utf-8")

        status = subprocess.run(
            ["git", "-C", str(workdir), "status", "--short"],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        status_path.write_text(status.stdout + status.stderr, encoding="utf-8")

        untracked = subprocess.run(
            ["git", "-C", str(workdir), "ls-files", "--others", "--exclude-standard"],
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        untracked_path.write_text(untracked.stdout + untracked.stderr, encoding="utf-8")

        test = subprocess.run(
            test_cmd,
            cwd=workdir,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout_path.write_text(test.stdout, encoding="utf-8")
        stderr_path.write_text(test.stderr, encoding="utf-8")

        manifest = {
            "schema": "clone-driver.artifacts.v1",
            "workdir": str(workdir),
            "git_diff": str(diff_path),
            "git_diff_staged": str(staged_diff_path),
            "git_status": str(status_path),
            "untracked_files": str(untracked_path),
            "test_stdout": str(stdout_path),
            "test_stderr": str(stderr_path),
            "test_exit_code": test.returncode,
        }
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return manifest_path
