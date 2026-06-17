from __future__ import annotations

import argparse
import json
import shlex
import sys
import time
from pathlib import Path
from typing import TextIO

from . import __version__
from .artifacts import ArtifactCollector
from .attach import AttachConfig, AttachLoop
from .attach_profile import load_attach_profile
from .advisor_backend import build_advisor_backend
from .backend_doctor import check_cli_available
from .decision import decide_next_input
from .ledger import JsonlLedger, read_jsonl_records, summarize_record
from .packet import PacketBuilder
from .pair import PairConfig, PairLauncher
from .run_control import write_control_state
from .session import TmuxSessionManager
from .supervisor import SupervisorConfig, SupervisorLoop
from .target_registry import (
    RightSeatSession,
    canonical_tmux_target,
    default_run_paths,
    kill_rightseat_pane,
    list_rightseat_sessions,
    list_tmux_targets,
    show_tmux_pane,
)
from .terminal import NudgeRunner, TmuxTerminalBroker
from .verifier import ExternalVerifier


DEFAULT_READY_REGEX = "READY|질문|Q[0-9]+:"
DEFAULT_QUESTION_REGEX = r"질문[:：]\s*(.+)|Q[0-9]+[:：]\s*(.+)|([^\n]+\?)"
RIGHTSEAT_DEFAULT_MODEL = "gpt-5.4-mini"
RIGHTSEAT_DEFAULT_EFFORT = "low"
RIGHTSEAT_DEFAULT_MAX_TURNS = "20"
RIGHTSEAT_DEFAULT_TIMEOUT = "3600"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _default_profile() -> Path:
    return _repo_root() / "docs" / "examples" / "default-profile.md"


def _default_answer_policy() -> Path:
    return _repo_root() / "docs" / "examples" / "answer-policy.md"


def _advisor_command(backend: str) -> list[str]:
    if backend == "fake":
        return [sys.executable, "-m", "clone_driver.fake_advisor"]
    if backend == "codex":
        return [sys.executable, "-m", "clone_driver.codex_advisor"]
    if backend == "claude":
        return [sys.executable, "-m", "clone_driver.claude_advisor"]
    raise ValueError(f"unsupported backend: {backend}")


def _print_attach_result(status: str, ledger_path: Path, tail: int = 20) -> None:
    print(status)
    print(f"ledger={ledger_path}")
    records = read_jsonl_records(ledger_path)
    print(f"events={len(records)}")
    for record in records[-tail:]:
        if record.get("event") == "attach_turn":
            print(
                "attach_turn "
                f"target={record.get('target', '')} "
                f"canonical={record.get('canonical_target', '')} "
                f"injected={record.get('injected', '')} "
                f"enter_sent={record.get('enter_sent', '')} "
                f"readback={record.get('readback_status', '')}"
            )
        else:
            print(summarize_record(record))


def _print_supervise_result(status: str, ledger_path: Path, tail: int = 50) -> None:
    print(status)
    print(f"ledger={ledger_path}")
    records = read_jsonl_records(ledger_path)
    print(f"events={len(records)}")
    for record in records[-tail:]:
        print(summarize_record(record))


def _run_supervisor(
    *,
    worker_command: list[str],
    advisor_command: list[str],
    ledger_path: Path,
    profile_path: Path,
    answer_policy_path: Path,
    ready_regex: str,
    question_regex: str,
    max_turns: int,
    read_timeout_seconds: float,
) -> dict[str, object]:
    config = SupervisorConfig(
        worker_command=worker_command,
        advisor_command=advisor_command,
        ledger_path=ledger_path,
        profile_path=profile_path,
        answer_policy_path=answer_policy_path,
        ready_regex=ready_regex,
        question_regex=question_regex,
        max_turns=max_turns,
        read_timeout_seconds=read_timeout_seconds,
    )
    return SupervisorLoop(config).run()


def _profile_value(
    values: dict[str, object],
    key: str,
    cli_value: object,
    default_value: object,
) -> object:
    if cli_value == default_value and key in values:
        return values[key]
    return cli_value


def _string_path(value: object) -> Path | None:
    text = str(value or "")
    return Path(text) if text else None


def _list_value(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, str) and value:
        return [value]
    return []


def _append_flag(args: list[str], name: str, value: object, default: object = "") -> None:
    if value != default and value not in {None, ""}:
        args.extend([name, str(value)])


def _build_pair_attach_args(args: argparse.Namespace) -> list[str]:
    attach_args: list[str] = []
    _append_flag(attach_args, "--config", args.config)
    attach_args.extend(["--backend", args.backend])
    _append_flag(attach_args, "--advisor-cmd", args.advisor_cmd)
    _append_flag(attach_args, "--advisor-model", args.advisor_model)
    _append_flag(attach_args, "--advisor-effort", args.advisor_effort)
    _append_flag(attach_args, "--profile", args.profile, str(_default_profile()))
    _append_flag(attach_args, "--answer-policy", args.answer_policy, str(_default_answer_policy()))
    _append_flag(attach_args, "--question-regex", args.question_regex, DEFAULT_QUESTION_REGEX)
    _append_flag(attach_args, "--quick-regex", args.quick_regex)
    _append_flag(attach_args, "--quick-reply", args.quick_reply)
    for key in args.quick_keys:
        attach_args.extend(["--quick-keys", key])
    _append_flag(attach_args, "--mode", args.mode, "auto")
    _append_flag(attach_args, "--confirm-timeout", args.confirm_timeout, 30.0)
    _append_flag(attach_args, "--target-fingerprint", args.target_fingerprint)
    _append_flag(attach_args, "--advisor-timeout", args.advisor_timeout, 60.0)
    _append_flag(attach_args, "--seed", args.seed)
    _append_flag(attach_args, "--wiw", args.wiw)
    _append_flag(attach_args, "--not-to-do", args.not_to_do)
    _append_flag(attach_args, "--final-artifact", args.final_artifact)
    for regex in args.redact_regex:
        attach_args.extend(["--redact-regex", regex])
    if args.allow_missing_contract:
        attach_args.append("--allow-missing-contract")
    if args.steal_lock:
        attach_args.append("--steal-lock")
    if args.skip_doctor:
        attach_args.append("--skip-doctor")
    _append_flag(attach_args, "--max-turns", args.max_turns, 1)
    _append_flag(attach_args, "--poll-interval", args.poll_interval, 1.0)
    _append_flag(attach_args, "--timeout", args.timeout, 300.0)
    return attach_args


def _rightseat_help() -> str:
    return "\n".join(
        [
            "RightSeat runs a visible AI operator beside your AI worker.",
            "",
            "Usage:",
            "  rightseat           start the visible side operator",
            "  rightseat off       stop only the RightSeat pane",
            "  rightseat reset     remove stale RightSeat panes",
            "  rightseat pause     pause RightSeat input",
            "  rightseat resume    resume RightSeat input",
            "  rightseat status    show active RightSeat sessions",
            "  rightseat log --log PATH",
            "  rightseat doctor --backend codex",
            "",
            "Common options:",
            "  --backend codex|claude|fake|custom",
            "  --model MODEL",
            "  --effort low|medium|high",
            "  --log PATH",
            "  --mode auto|confirm|suggest|paused",
            "",
            "Target selection:",
            "  rightseat targets   list worker panes",
            "  rightseat %0        sit beside pane %0",
            "",
            "Advanced clone-driver commands still exist for compatibility.",
        ]
    )


def _rightseat_public_aliases(args: list[str]) -> list[str]:
    aliases = {
        "--model": "--advisor-model",
        "--effort": "--advisor-effort",
        "--log": "--ledger",
    }
    translated: list[str] = []
    for arg in args:
        if arg in aliases:
            translated.append(aliases[arg])
            continue
        if "=" in arg:
            name, value = arg.split("=", 1)
            if name in aliases:
                translated.append(f"{aliases[name]}={value}")
                continue
        translated.append(arg)
    return translated


def _print_rightseat_targets(candidates: list[object]) -> None:
    print("RightSeat worker choices")
    if not candidates:
        print("")
        print("No tmux worker pane found.")
        print("Start a worker inside tmux, then run: rightseat")
        return
    for index, target in enumerate(candidates, 1):
        preview = " ".join(str(getattr(target, "preview", "")).split())
        pane_ref = str(getattr(target, "pane_ref", ""))
        worker = pane_ref.split(":", 1)[0] or str(getattr(target, "pane_id", ""))
        command = str(getattr(target, "command", ""))
        pane_id = str(getattr(target, "pane_id", ""))
        locked = bool(getattr(target, "locked", False))
        print(
            f"\n[{index}] {worker}\n"
            f"    app: {command or 'unknown'}\n"
            f"    pane: {pane_id}\n"
            f"    locked: {locked}\n"
            f"    preview: {preview[:80] or 'none'}\n"
            f"    run: rightseat {pane_id}"
        )


def _select_rightseat_target(input_stream: TextIO | None = None) -> str:
    candidates = list_tmux_targets()
    if not candidates:
        _print_rightseat_targets(candidates)
        raise SystemExit(2)

    _print_rightseat_targets(candidates)
    stream = input_stream or sys.stdin
    if not stream.isatty():
        print("")
        print("Run rightseat in a terminal and choose by number.")
        print("Or name a worker explicitly, for example: rightseat %0")
        raise SystemExit(2)
    print("Number: ", end="", flush=True)
    selected = stream.readline().strip()
    try:
        index = int(selected)
    except ValueError:
        print("Invalid number.")
        raise SystemExit(2)
    if index < 1 or index > len(candidates):
        print("Invalid number.")
        raise SystemExit(2)
    return candidates[index - 1].pane_id


def _select_rightseat_session(
    sessions: list[RightSeatSession],
    input_stream: TextIO | None = None,
) -> RightSeatSession:
    if not sessions:
        print("No active RightSeat session.")
        print("Start one with: rightseat")
        raise SystemExit(2)
    if len(sessions) == 1:
        return sessions[0]

    print("RightSeat active sessions")
    for index, session in enumerate(sessions, 1):
        print(
            f"\n[{index}] {session.run_id}\n"
            f"    worker: {session.worker_target}\n"
            f"    seat: {session.advisor_target}\n"
            f"    mode: {session.mode}"
        )
    stream = input_stream or sys.stdin
    if not stream.isatty():
        print("")
        print("Run again with a specific session after checking: rightseat status")
        raise SystemExit(2)
    selected = input("Number: ").strip()
    try:
        index = int(selected)
    except ValueError:
        print("Invalid number.")
        raise SystemExit(2)
    if index < 1 or index > len(sessions):
        print("Invalid number.")
        raise SystemExit(2)
    return sessions[index - 1]


def _print_rightseat_status(sessions: list[RightSeatSession]) -> None:
    print("RightSeat status")
    if not sessions:
        print("state: off")
        print("start: rightseat")
        return
    for session in sessions:
        print("")
        print(f"run: {session.run_id}")
        print(f"worker: {session.worker_target}")
        print(f"seat: {session.advisor_target}")
        print(f"mode: {session.mode}")
        print(f"log: {session.ledger_path}")
    print("")
    print("off: rightseat off")
    print("reset: rightseat reset")
    print("pause: rightseat pause")
    print("resume: rightseat resume")


def _stop_rightseat_sessions(
    sessions: list[RightSeatSession],
    *,
    label: str,
) -> int:
    if not sessions:
        print("No active RightSeat session.")
        print("Workers kept.")
        return 0
    stopped = 0
    failed: list[str] = []
    workers = sorted({session.worker_target for session in sessions})
    for session in sessions:
        if kill_rightseat_pane(session.advisor_target):
            stopped += 1
        else:
            failed.append(session.advisor_target)
    print(label)
    print(f"stopped={stopped}")
    print("workers kept: " + ", ".join(workers))
    if failed:
        print("failed seats: " + ", ".join(failed))
        return 8
    return 0


def _stop_rightseat_for_worker(worker_target: str) -> None:
    canonical_worker = canonical_tmux_target(worker_target)
    sessions = [
        session
        for session in list_rightseat_sessions()
        if session.worker_target in {worker_target, canonical_worker}
    ]
    for session in sessions:
        kill_rightseat_pane(session.advisor_target)


def _rightseat_control(
    command: str,
    *,
    input_stream: TextIO | None = None,
) -> int:
    sessions = list_rightseat_sessions()
    if command == "status":
        _print_rightseat_status(sessions)
        return 0
    if command == "off":
        return _stop_rightseat_sessions(sessions, label="RightSeat off")
    if command == "reset":
        return _stop_rightseat_sessions(sessions, label="RightSeat reset")
    if command == "pause":
        if not sessions:
            print("No active RightSeat session.")
            return 0
        for active in sessions:
            write_control_state(active.control_path, mode="paused")
        print("RightSeat paused")
        print(f"sessions={len(sessions)}")
        return 0
    if command == "resume":
        if not sessions:
            print("No active RightSeat session.")
            return 0
        for active in sessions:
            write_control_state(active.control_path, mode="auto")
        print("RightSeat resumed")
        print(f"sessions={len(sessions)}")
        return 0
    print(f"unknown rightseat command: {command}")
    return 2


def _rightseat_pair_argv(target: str, rest: list[str]) -> list[str]:
    return [
        "pair",
        "--target",
        target,
        "--show",
        "--allow-missing-contract",
        "--advisor-model",
        RIGHTSEAT_DEFAULT_MODEL,
        "--advisor-effort",
        RIGHTSEAT_DEFAULT_EFFORT,
        "--max-turns",
        RIGHTSEAT_DEFAULT_MAX_TURNS,
        "--timeout",
        RIGHTSEAT_DEFAULT_TIMEOUT,
        *rest,
    ]


def rightseat_main(
    argv: list[str] | None = None,
    *,
    input_stream: TextIO | None = None,
) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] in {"-h", "--help", "help"}:
        print(_rightseat_help())
        return 0
    if args and args[0] == "--version":
        print(f"rightseat {__version__}")
        return 0
    if args and args[0] in {"targets", "list"}:
        _print_rightseat_targets(list_tmux_targets())
        return 0
    if args and args[0] in {"off", "reset", "pause", "resume", "status"}:
        return _rightseat_control(args[0], input_stream=input_stream)
    if args and args[0] in {"log", "logs", "ledger"}:
        return main(["ledger", *_rightseat_public_aliases(args[1:])])
    if args and args[0] in {"doctor", "runs", "control"}:
        return main([args[0], *_rightseat_public_aliases(args[1:])])
    if args and args[0] in {"go", "pair"}:
        args = args[1:]

    target = ""
    rest = args
    if args and not args[0].startswith("-"):
        target = args[0]
        rest = args[1:]
    rest = _rightseat_public_aliases(rest)
    if not target:
        try:
            target = _select_rightseat_target(input_stream)
        except SystemExit as error:
            return int(error.code or 0)
    _stop_rightseat_for_worker(target)
    return main(_rightseat_pair_argv(target, rest))


def _doctor_backend(backend: str, advisor_cmd: str) -> tuple[str, str]:
    if backend == "codex":
        return "codex", ""
    if backend == "claude":
        return "claude", ""
    if backend == "fake":
        return sys.executable, ""
    command = shlex.split(advisor_cmd)
    if not command:
        return "", "--advisor-cmd is required when --backend custom"
    return command[0], ""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="clone-driver")
    parser.add_argument("--version", action="store_true")
    subparsers = parser.add_subparsers(dest="command")

    packet = subparsers.add_parser("packet")
    packet.add_argument("--seed", required=True)
    packet.add_argument("--wiw", required=True)
    packet.add_argument("--not-to-do", required=True)
    packet.add_argument("--final-artifact", required=True)
    packet.add_argument("--diff")
    packet.add_argument("--test-output")
    packet.add_argument("--artifact-manifest")
    packet.add_argument("--out", required=True)
    nudge = subparsers.add_parser("nudge")
    nudge.add_argument("--session", required=True)
    nudge.add_argument("--message", required=True)
    nudge.add_argument("--ledger", required=True)
    nudge.add_argument("--idle-marker", default="")
    nudge.add_argument("--idle-regex", default="")
    gate = subparsers.add_parser("gate")
    gate.add_argument("--packet", required=True)
    gate.add_argument("--ledger", required=True)
    gate.add_argument("--verifier-cmd", required=True)
    gate.add_argument("--session")
    gate.add_argument("--idle-marker", default="")
    gate.add_argument("--idle-regex", default="")
    gate.add_argument("--dry-run", action="store_true")
    run = subparsers.add_parser("run")
    run.add_argument("--session", required=True)
    run.add_argument("--ledger", required=True)
    run.add_argument("worker_command", nargs=argparse.REMAINDER)
    probe = subparsers.add_parser("probe")
    probe.add_argument("--target", required=True)
    probe.add_argument("--ledger", required=True)
    collect = subparsers.add_parser("collect")
    collect.add_argument("--workdir", required=True)
    collect.add_argument("--out-dir", required=True)
    collect.add_argument("--test-cmd", required=True)
    ledger = subparsers.add_parser("ledger")
    ledger.add_argument("--ledger", required=True)
    ledger.add_argument("--tail", type=int, default=20)
    supervise = subparsers.add_parser("supervise")
    supervise.add_argument("--ledger", required=True)
    supervise.add_argument("--profile", required=True)
    supervise.add_argument("--answer-policy", required=True)
    supervise.add_argument("--advisor-cmd", required=True)
    supervise.add_argument("--ready-regex", required=True)
    supervise.add_argument("--question-regex", required=True)
    supervise.add_argument("--max-turns", type=int, default=10)
    supervise.add_argument("--read-timeout", type=float, default=5.0)
    supervise.add_argument("worker_command", nargs=argparse.REMAINDER)
    try_cmd = subparsers.add_parser("try")
    try_cmd.add_argument("--backend", choices=["fake", "codex", "claude"], default="fake")
    try_cmd.add_argument("--ledger", default="runtime/clone-driver-try.jsonl")
    try_cmd.add_argument("--max-turns", type=int, default=3)
    try_cmd.add_argument("--read-timeout", type=float, default=5.0)
    drive = subparsers.add_parser("drive")
    drive.add_argument("--backend", choices=["codex", "claude", "fake"], default="codex")
    drive.add_argument("--ledger", default="runtime/advisor-loop.jsonl")
    drive.add_argument("--profile", default=str(_default_profile()))
    drive.add_argument("--answer-policy", default=str(_default_answer_policy()))
    drive.add_argument("--ready-regex", default=DEFAULT_READY_REGEX)
    drive.add_argument("--question-regex", default=DEFAULT_QUESTION_REGEX)
    drive.add_argument("--max-turns", type=int, default=10)
    drive.add_argument("--read-timeout", type=float, default=5.0)
    drive.add_argument("worker_command", nargs=argparse.REMAINDER)
    attach = subparsers.add_parser("attach")
    attach.add_argument("--target", required=True)
    attach.add_argument("--config", default="")
    attach.add_argument("--backend", choices=["codex", "claude", "fake", "custom"], default="codex")
    attach.add_argument("--advisor-cmd", default="")
    attach.add_argument("--advisor-model", default="")
    attach.add_argument("--advisor-effort", default="")
    attach.add_argument("--advisor-display", choices=["inline", "tmux", "hidden"], default="inline")
    attach.add_argument("--advisor-display-target", default="")
    attach.add_argument("--advisor-transcript", default="")
    attach.add_argument("--ledger", default="")
    attach.add_argument("--profile", default=str(_default_profile()))
    attach.add_argument("--answer-policy", default=str(_default_answer_policy()))
    attach.add_argument("--question-regex", default=DEFAULT_QUESTION_REGEX)
    attach.add_argument("--quick-regex", default="")
    attach.add_argument("--quick-reply", default="")
    attach.add_argument("--quick-keys", action="append", default=[])
    attach.add_argument("--mode", choices=["auto", "confirm", "suggest", "paused"], default="auto")
    attach.add_argument("--confirm-timeout", type=float, default=30.0)
    attach.add_argument("--run-id", default="")
    attach.add_argument("--target-fingerprint", default="")
    attach.add_argument("--advisor-timeout", type=float, default=60.0)
    attach.add_argument("--seed", default="")
    attach.add_argument("--wiw", default="")
    attach.add_argument("--not-to-do", default="")
    attach.add_argument("--final-artifact", default="")
    attach.add_argument("--allow-missing-contract", action="store_true")
    attach.add_argument("--redact-regex", action="append", default=[])
    attach.add_argument("--steal-lock", action="store_true")
    attach.add_argument("--skip-doctor", action="store_true")
    attach.add_argument("--max-turns", type=int, default=1)
    attach.add_argument("--poll-interval", type=float, default=1.0)
    attach.add_argument("--timeout", type=float, default=300.0)
    pair = subparsers.add_parser("pair")
    pair.add_argument("--target", required=True)
    pair.add_argument("--show", action="store_true")
    pair.add_argument("--config", default="")
    pair.add_argument("--backend", choices=["codex", "claude", "fake", "custom"], default="codex")
    pair.add_argument("--advisor-cmd", default="")
    pair.add_argument("--advisor-model", default="")
    pair.add_argument("--advisor-effort", default="")
    pair.add_argument("--ledger", default="")
    pair.add_argument("--profile", default=str(_default_profile()))
    pair.add_argument("--answer-policy", default=str(_default_answer_policy()))
    pair.add_argument("--question-regex", default=DEFAULT_QUESTION_REGEX)
    pair.add_argument("--quick-regex", default="")
    pair.add_argument("--quick-reply", default="")
    pair.add_argument("--quick-keys", action="append", default=[])
    pair.add_argument("--mode", choices=["auto", "confirm", "suggest", "paused"], default="auto")
    pair.add_argument("--confirm-timeout", type=float, default=30.0)
    pair.add_argument("--run-id", default="")
    pair.add_argument("--target-fingerprint", default="")
    pair.add_argument("--advisor-timeout", type=float, default=60.0)
    pair.add_argument("--seed", default="")
    pair.add_argument("--wiw", default="")
    pair.add_argument("--not-to-do", default="")
    pair.add_argument("--final-artifact", default="")
    pair.add_argument("--allow-missing-contract", action="store_true")
    pair.add_argument("--redact-regex", action="append", default=[])
    pair.add_argument("--steal-lock", action="store_true")
    pair.add_argument("--skip-doctor", action="store_true")
    pair.add_argument("--max-turns", type=int, default=1)
    pair.add_argument("--poll-interval", type=float, default=1.0)
    pair.add_argument("--timeout", type=float, default=300.0)
    targets = subparsers.add_parser("targets")
    targets.add_argument("--lock-root", default="runtime/attach-locks")
    runs = subparsers.add_parser("runs")
    runs.add_argument("--runtime-root", default="runtime/attach-runs")
    control = subparsers.add_parser("control")
    control.add_argument("--run-id", required=True)
    control.add_argument("--mode", choices=["auto", "confirm", "suggest", "paused"], required=True)
    doctor = subparsers.add_parser("doctor")
    doctor.add_argument("--backend", choices=["codex", "claude", "fake", "custom"], default="codex")
    doctor.add_argument("--advisor-cmd", default="")
    doctor.add_argument("--advisor-model", default="")
    doctor.add_argument("--advisor-effort", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.version:
        print(f"clone-driver {__version__}")
        return 0
    if args.command == "packet":
        required = [args.seed, args.wiw, args.not_to_do, args.final_artifact]
        if any(not Path(path).exists() for path in required):
            return 2
        builder = PacketBuilder()
        packet = builder.build(
            seed=Path(args.seed),
            wiw=Path(args.wiw),
            not_to_do=Path(args.not_to_do),
            final_artifact=Path(args.final_artifact),
            diff=Path(args.diff) if args.diff else None,
            test_output=Path(args.test_output) if args.test_output else None,
            artifact_manifest=Path(args.artifact_manifest)
            if args.artifact_manifest
            else None,
        )
        builder.write(packet, Path(args.out))
        return 0
    if args.command == "nudge":
        runner = NudgeRunner(
            terminal=TmuxTerminalBroker(
                idle_marker=args.idle_marker,
                idle_regex=args.idle_regex,
            ),
            ledger=JsonlLedger(Path(args.ledger)),
        )
        result = runner.run(session=args.session, message=args.message)
        print(result["status"])
        if result.get("enter_sent") is True:
            return 0
        return 3 if result["status"] == "not_idle" else 6
    if args.command == "gate":
        ledger = JsonlLedger(Path(args.ledger))
        verifier = ExternalVerifier(shlex.split(args.verifier_cmd))
        try:
            verdict = verifier.verify(Path(args.packet))
        except (RuntimeError, OSError) as error:
            ledger.write(
                "verifier_error",
                {
                    "status": "verifier_error",
                    "error": str(error),
                },
            )
            print("verifier_error")
            return 7
        except json.JSONDecodeError as error:
            ledger.write(
                "invalid_verdict",
                {
                    "status": "invalid_verdict",
                    "error": str(error),
                },
            )
            print("invalid_verdict")
            return 7
        except ValueError as error:
            ledger.write(
                "invalid_verdict",
                {
                    "status": "invalid_verdict",
                    "error": str(error),
                },
            )
            print("invalid_verdict")
            return 7
        action = decide_next_input(verdict)
        ledger.write(
            "gate",
            {
                "verdict": verdict.status,
                "reason": verdict.reason,
                "action": action.status,
            },
        )
        if action.status in {"stop", "escalate"}:
            print("escalated")
            return 4
        if action.status == "hold":
            print("hold")
            return 0
        if not args.dry_run:
            if not args.session:
                print("missing --session for non-dry-run gate")
                return 2
            result = NudgeRunner(
                terminal=TmuxTerminalBroker(
                    idle_marker=args.idle_marker,
                    idle_regex=args.idle_regex,
                ),
                ledger=ledger,
            ).run(session=args.session, message=action.message, event="gate_injection")
            if not result["enter_sent"]:
                print(result["status"])
                return 3 if result["status"] == "not_idle" else 6
        print(action.status)
        return 0
    if args.command == "run":
        command = args.worker_command[1:] if args.worker_command[:1] == ["--"] else args.worker_command
        if not command:
            print("missing worker command")
            return 2
        manager = TmuxSessionManager()
        target = manager.start(session=args.session, command=command)
        JsonlLedger(Path(args.ledger)).write(
            "session_started",
            {
                "session": target.session,
                "target": target.target,
                "canonical_target": target.canonical_target,
            },
        )
        print(target.target)
        return 0
    if args.command == "probe":
        probe_result = TmuxSessionManager().probe(target=args.target)
        JsonlLedger(Path(args.ledger)).write(
            "session_probe",
            {
                "target": args.target,
                "canonical_target": probe_result.canonical_target,
                "available": probe_result.available,
                "stderr": probe_result.stderr,
            },
        )
        print("available" if probe_result.available else "unsupported_target")
        return 0 if probe_result.available else 5
    if args.command == "collect":
        manifest = ArtifactCollector().collect(
            workdir=Path(args.workdir),
            out_dir=Path(args.out_dir),
            test_cmd=shlex.split(args.test_cmd),
        )
        print(manifest)
        return 0
    if args.command == "ledger":
        records = read_jsonl_records(Path(args.ledger))
        print(f"events={len(records)}")
        for record in records[-args.tail :]:
            print(summarize_record(record))
        return 0
    if args.command == "targets":
        for target in list_tmux_targets(Path(args.lock_root)):
            preview = " ".join(target.preview.splitlines()[-2:])
            print(
                f"{target.pane_id} {target.pane_ref} {target.command} "
                f"locked={target.locked} fingerprint={target.fingerprint} "
                f"title={target.title} preview={preview[:120]}"
            )
        return 0
    if args.command == "runs":
        root = Path(args.runtime_root)
        if not root.exists():
            return 0
        for path in sorted(root.glob("*/ledger.jsonl")):
            print(path.parent.name)
        return 0
    if args.command == "control":
        control_path = Path("runtime") / "attach-runs" / args.run_id / "control.json"
        write_control_state(control_path, mode=args.mode)
        print(f"{args.run_id} mode={args.mode}")
        return 0
    if args.command == "doctor":
        command, error = _doctor_backend(args.backend, args.advisor_cmd)
        if error:
            print(error)
            return 2
        result = check_cli_available(command)
        if result.status != "ok":
            print(f"{args.backend} {result.status}")
            return 8
        print("doctor ok")
        return 0
    if args.command == "pair":
        requested_run_id = args.run_id or f"pair-{int(time.time())}"
        run_paths = default_run_paths(requested_run_id)
        ledger_path = Path(args.ledger) if args.ledger else run_paths.ledger_path
        transcript_path = ledger_path.parent / "advisor-transcript.jsonl"
        config = PairConfig(
            target=args.target,
            run_id=run_paths.run_id,
            ledger_path=ledger_path,
            advisor_transcript_path=transcript_path,
            attach_args=_build_pair_attach_args(args),
        )
        result = PairLauncher(config).launch()
        print(result.status)
        print(f"worker={result.worker_target}")
        print(f"advisor={result.advisor_target}")
        print(f"run_id={result.run_id}")
        print(f"log={result.ledger_path}")
        print(f"ledger={result.ledger_path}")
        if result.error:
            print(f"error={result.error}")
        if result.status == "started" and args.show:
            if show_tmux_pane(result.advisor_target):
                print("shown=true")
            else:
                print("shown=false")
        return 0 if result.status == "started" else 8
    if args.command == "attach":
        profile_values: dict[str, object] = {}
        profile_id = ""
        config_hash = ""
        if args.config:
            profile = load_attach_profile(Path(args.config))
            profile_values = profile.values
            profile_id = str(profile.values.get("profile_id", ""))
            config_hash = profile.config_hash

        backend_name = str(_profile_value(profile_values, "backend", args.backend, "codex"))
        advisor_model = str(_profile_value(profile_values, "advisor_model", args.advisor_model, ""))
        advisor_effort = str(_profile_value(profile_values, "advisor_effort", args.advisor_effort, ""))
        advisor_cmd = str(_profile_value(profile_values, "advisor_cmd", args.advisor_cmd, ""))
        quick_regex = str(_profile_value(profile_values, "quick_regex", args.quick_regex, ""))
        quick_reply = str(_profile_value(profile_values, "quick_reply", args.quick_reply, ""))
        mode = str(_profile_value(profile_values, "mode", args.mode, "auto"))
        advisor_display = str(
            _profile_value(profile_values, "advisor_display", args.advisor_display, "inline")
        )
        advisor_display_target = str(
            _profile_value(
                profile_values,
                "advisor_display_target",
                args.advisor_display_target,
                "",
            )
        )
        confirm_timeout = float(
            _profile_value(profile_values, "confirm_timeout", args.confirm_timeout, 30.0)
        )
        advisor_timeout = float(
            _profile_value(profile_values, "advisor_timeout", args.advisor_timeout, 60.0)
        )
        quick_keys = args.quick_keys or _list_value(profile_values.get("quick_keys", []))
        redact_regex = args.redact_regex or _list_value(profile_values.get("redact_regex", []))

        try:
            backend = build_advisor_backend(
                backend=backend_name,
                model=advisor_model,
                effort=advisor_effort,
                custom_command=advisor_cmd,
            )
        except ValueError as error:
            print(str(error))
            return 2

        if not args.skip_doctor and backend.name in {"codex", "claude", "custom"}:
            command, error = _doctor_backend(backend.name, advisor_cmd)
            if error:
                print(error)
                return 2
            doctor_result = check_cli_available(command)
            if doctor_result.status != "ok":
                print(f"{backend.name} {doctor_result.status}")
                return 8

        requested_run_id = str(_profile_value(profile_values, "run_id", args.run_id, ""))
        run_id = requested_run_id or f"attach-{int(time.time())}"
        run_paths = default_run_paths(run_id)
        ledger_path = Path(
            str(_profile_value(profile_values, "ledger", args.ledger, ""))
        ) if args.ledger or "ledger" in profile_values else run_paths.ledger_path
        control_path = run_paths.control_path
        lock_root = ledger_path.parent / "locks" if args.ledger else run_paths.lock_root

        config = AttachConfig(
            target=args.target,
            advisor_command=backend.command,
            ledger_path=ledger_path,
            profile_path=Path(str(_profile_value(profile_values, "profile", args.profile, str(_default_profile())))),
            answer_policy_path=Path(
                str(
                    _profile_value(
                        profile_values,
                        "answer_policy",
                        args.answer_policy,
                        str(_default_answer_policy()),
                    )
                )
            ),
            question_regex=str(
                _profile_value(
                    profile_values,
                    "question_regex",
                    args.question_regex,
                    DEFAULT_QUESTION_REGEX,
                )
            ),
            backend_name=backend.name,
            backend_model=backend.model,
            backend_effort=backend.effort,
            backend_source=backend.source,
            quick_regex=quick_regex,
            quick_reply=quick_reply,
            quick_keys=quick_keys,
            mode=mode,
            confirm_timeout_seconds=confirm_timeout,
            run_id=run_paths.run_id,
            control_path=control_path,
            lock_root=lock_root,
            target_fingerprint=args.target_fingerprint,
            advisor_timeout_seconds=advisor_timeout,
            seed_path=_string_path(_profile_value(profile_values, "seed", args.seed, "")),
            wiw_path=_string_path(_profile_value(profile_values, "wiw", args.wiw, "")),
            not_to_do_path=_string_path(
                _profile_value(profile_values, "not_to_do", args.not_to_do, "")
            ),
            final_artifact_path=_string_path(
                _profile_value(profile_values, "final_artifact", args.final_artifact, "")
            ),
            allow_missing_contract=args.allow_missing_contract,
            redact_regex=redact_regex,
            steal_lock=args.steal_lock,
            advisor_display=advisor_display,
            advisor_display_target=advisor_display_target,
            advisor_transcript_path=_string_path(
                _profile_value(
                    profile_values,
                    "advisor_transcript",
                    args.advisor_transcript,
                    "",
                )
            ),
            profile_id=profile_id,
            config_hash=config_hash,
            max_turns=args.max_turns,
            poll_interval_seconds=args.poll_interval,
            timeout_seconds=args.timeout,
        )
        result = AttachLoop(config, terminal=TmuxTerminalBroker()).run()
        status = str(result["status"])
        _print_attach_result(status, ledger_path)
        return 0 if status == "completed" else 8
    if args.command == "supervise":
        command = args.worker_command[1:] if args.worker_command[:1] == ["--"] else args.worker_command
        if not command:
            print("missing worker command")
            return 2
        result = _run_supervisor(
            worker_command=command,
            advisor_command=shlex.split(args.advisor_cmd),
            ledger_path=Path(args.ledger),
            profile_path=Path(args.profile),
            answer_policy_path=Path(args.answer_policy),
            ready_regex=args.ready_regex,
            question_regex=args.question_regex,
            max_turns=args.max_turns,
            read_timeout_seconds=args.read_timeout,
        )
        print(result["status"])
        return 0 if result["status"] == "completed" else 8
    if args.command == "try":
        ledger_path = Path(args.ledger)
        result = _run_supervisor(
            worker_command=[sys.executable, "-m", "clone_driver.demo_worker"],
            advisor_command=_advisor_command(args.backend),
            ledger_path=ledger_path,
            profile_path=_default_profile(),
            answer_policy_path=_default_answer_policy(),
            ready_regex=DEFAULT_READY_REGEX,
            question_regex=DEFAULT_QUESTION_REGEX,
            max_turns=args.max_turns,
            read_timeout_seconds=args.read_timeout,
        )
        _print_supervise_result(str(result["status"]), ledger_path)
        return 0 if result["status"] == "completed" else 8
    if args.command == "drive":
        command = args.worker_command[1:] if args.worker_command[:1] == ["--"] else args.worker_command
        if not command:
            print("missing worker command")
            return 2
        ledger_path = Path(args.ledger)
        result = _run_supervisor(
            worker_command=command,
            advisor_command=_advisor_command(args.backend),
            ledger_path=ledger_path,
            profile_path=Path(args.profile),
            answer_policy_path=Path(args.answer_policy),
            ready_regex=args.ready_regex,
            question_regex=args.question_regex,
            max_turns=args.max_turns,
            read_timeout_seconds=args.read_timeout,
        )
        _print_supervise_result(str(result["status"]), ledger_path)
        return 0 if result["status"] == "completed" else 8
    parser.print_help()
    return 0


def entrypoint() -> int:
    return main()


def rightseat_entrypoint() -> int:
    return rightseat_main()
