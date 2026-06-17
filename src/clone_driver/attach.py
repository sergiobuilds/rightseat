from __future__ import annotations

import select
import sys
import time
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import TextIO
from types import SimpleNamespace

from .advisor import AdvisorRequest, ExternalAdvisor
from .advisor_display import AdvisorDisplay
from .input_action import InputAction
from .ledger import JsonlLedger
from .operator_decision import OperatorDecision
from .policy_gate import DOWNGRADE_SUGGEST, ESCALATE, GateContext, evaluate_policy_gate
from .prompt_classifier import classify_prompt
from .redaction import redact_screen
from .run_control import read_control_state
from .screen_model import analyze_screen
from .target_registry import TargetLock, fingerprint_transcript
from .task_contract import TaskContract, load_task_contract
from .terminal import TerminalBroker, TmuxTerminalBroker


@dataclass(frozen=True)
class AttachConfig:
    target: str
    advisor_command: list[str]
    ledger_path: Path
    profile_path: Path
    answer_policy_path: Path
    question_regex: str
    max_turns: int = 1
    poll_interval_seconds: float = 1.0
    timeout_seconds: float = 300.0
    backend_name: str = "codex"
    backend_model: str = ""
    backend_effort: str = ""
    backend_source: str = "builtin"
    quick_regex: str = ""
    quick_reply: str = ""
    quick_keys: list[str] | None = None
    mode: str = "auto"
    run_id: str = ""
    control_path: Path | None = None
    lock_root: Path | None = Path("runtime/attach-locks")
    steal_lock: bool = False
    target_fingerprint: str = ""
    advisor_timeout_seconds: float = 60.0
    seed_path: Path | None = None
    wiw_path: Path | None = None
    not_to_do_path: Path | None = None
    final_artifact_path: Path | None = None
    allow_missing_contract: bool = False
    redact_regex: list[str] | None = None
    advisor_display: str = "inline"
    advisor_display_target: str = ""
    advisor_transcript_path: Path | None = None
    profile_id: str = ""
    config_hash: str = ""
    confirm_timeout_seconds: float = 30.0


def _load_optional_contract(config: AttachConfig) -> TaskContract | None:
    paths = [
        config.seed_path,
        config.wiw_path,
        config.not_to_do_path,
        config.final_artifact_path,
    ]
    if all(paths):
        return load_task_contract(
            config.seed_path,  # type: ignore[arg-type]
            config.wiw_path,  # type: ignore[arg-type]
            config.not_to_do_path,  # type: ignore[arg-type]
            config.final_artifact_path,  # type: ignore[arg-type]
        )
    if any(paths) or not config.allow_missing_contract:
        raise ValueError(
            "seed, wiw, not-to-do, and final artifact paths are required "
            "unless allow_missing_contract is set"
        )
    return None


def _input_action_from_response(response: object) -> InputAction | None:
    action_name = str(getattr(response, "action", ""))
    if action_name == "ANSWER":
        return InputAction.from_parts(
            mode=str(getattr(response, "input_mode", "text") or "text"),
            text=str(getattr(response, "answer", "") or ""),
            keys=list(getattr(response, "keys", []) or []),
            choice_label=str(getattr(response, "choice_label", "") or ""),
            source=str(getattr(response, "answer_source", "llm") or "llm"),
        )
    if action_name in {"TYPE", "SUBMIT", "KEYS"}:
        decision = OperatorDecision(
            action=action_name,
            text=str(getattr(response, "text", getattr(response, "answer", "")) or ""),
            keys=list(getattr(response, "keys", []) or []),
            reason=str(getattr(response, "reason", "") or ""),
            confidence=str(getattr(response, "confidence", "low") or "low"),
        )
        if not decision.executable_in_auto:
            return None
        return decision.to_input_action()
    return None


def _interaction_signature(transcript: str, question_regex: str) -> str:
    screen = analyze_screen(transcript)
    if screen.state != "unknown":
        return f"{screen.adapter}:{screen.state}:{screen.current_input or screen.question}"
    prompt = classify_prompt(transcript, question_regex=question_regex)
    return f"generic:{prompt.prompt_class}:{prompt.question}"


def _tier_for_mode(mode: str) -> str:
    if mode == "suggest":
        return "SUGGEST"
    if mode == "paused":
        return "OBSERVE"
    return "ACT_BROAD"


def _gate_action_kind(action: InputAction, response: object | None) -> str:
    response_action = str(getattr(response, "action", "") or "")
    if response_action in {"TYPE", "SUBMIT", "KEYS"}:
        return response_action
    if action.mode == "keys":
        return "KEYS"
    return "TYPE"


def _gate_action_source(source: str) -> str:
    return "quick" if source == "quick_reply" else source


def _risk_for_screen(screen: object) -> str:
    if bool(getattr(screen, "hard_stop", False)):
        return "high"
    if str(getattr(screen, "worker_claim", "none")) != "none":
        return "med"
    return "low"


def _detected_state(screen: object, prompt: object) -> str:
    state = str(getattr(screen, "state", "unknown") or "unknown")
    if state != "unknown":
        return state
    return str(getattr(prompt, "prompt_class", "unknown") or "unknown")


class AttachLoop:
    def __init__(
        self,
        config: AttachConfig,
        terminal: TerminalBroker | None = None,
        input_stream: TextIO | None = sys.stdin,
        output_stream: TextIO | None = sys.stdout,
    ):
        self.config = config
        self.terminal = terminal or TmuxTerminalBroker()
        self.ledger = JsonlLedger(config.ledger_path)
        self.input_stream = input_stream
        self.output_stream = output_stream

    def _current_mode(self) -> str:
        if self.config.control_path is None:
            return self.config.mode
        return read_control_state(self.config.control_path).mode

    def _run_id(self) -> str:
        return self.config.run_id or "attach"

    def _base_event(self, canonical_target: str) -> dict[str, object]:
        return {
            "target": self.config.target,
            "canonical_target": canonical_target,
            "run_id": self._run_id(),
            "profile_id": self.config.profile_id,
            "config_hash": self.config.config_hash,
        }

    def _record_display(
        self,
        *,
        canonical_target: str,
        prompt_class: str,
        reason: str,
        proposed_input: str,
        input_mode: str,
    ) -> None:
        if self.config.advisor_transcript_path is None:
            return
        display = AdvisorDisplay(
            mode=self.config.advisor_display,
            transcript_path=self.config.advisor_transcript_path,
            tmux_target=self.config.advisor_display_target,
        )
        display.record_decision(
            run_id=self._run_id(),
            target=canonical_target,
            prompt_class=prompt_class,
            backend=self.config.backend_name,
            model=self.config.backend_model,
            effort=self.config.backend_effort,
            reason=reason,
            proposed_input=proposed_input,
            input_mode=input_mode,
        )

    def _record_status(
        self,
        *,
        canonical_target: str,
        status: str,
        prompt_class: str = "",
        message: str = "",
        **payload: object,
    ) -> None:
        if self.config.advisor_transcript_path is None:
            return
        display = AdvisorDisplay(
            mode=self.config.advisor_display,
            transcript_path=self.config.advisor_transcript_path,
            tmux_target=self.config.advisor_display_target,
        )
        display.record_status(
            run_id=self._run_id(),
            target=canonical_target,
            status=status,
            prompt_class=prompt_class,
            message=message,
            backend=self.config.backend_name,
            model=self.config.backend_model,
            effort=self.config.backend_effort,
            **payload,
        )

    def _confirm(
        self,
        *,
        canonical_target: str,
        prompt_class: str,
        reason: str,
        proposed_input: str,
        input_mode: str,
    ) -> str:
        if self.input_stream is None or not self.input_stream.isatty():
            self.ledger.write(
                "confirm_unavailable",
                {
                    **self._base_event(canonical_target),
                    "prompt_class": prompt_class,
                    "reason": reason,
                    "proposed_input": proposed_input,
                    "input_mode": input_mode,
                    "injected": False,
                },
            )
            return "confirm_unavailable"

        if self.output_stream is not None:
            self.output_stream.write(
                f"Inject into {canonical_target}? "
                f"class={prompt_class} input_mode={input_mode} "
                f"reason={reason} input={proposed_input} [y/N] "
            )
            self.output_stream.flush()

        try:
            ready, _, _ = select.select(
                [self.input_stream],
                [],
                [],
                self.config.confirm_timeout_seconds,
            )
        except (OSError, ValueError):
            ready = []

        if not ready:
            self.ledger.write(
                "confirm_timeout",
                {
                    **self._base_event(canonical_target),
                    "prompt_class": prompt_class,
                    "proposed_input": proposed_input,
                    "input_mode": input_mode,
                    "injected": False,
                },
            )
            return "confirm_timeout"

        answer = self.input_stream.readline().strip().lower()
        if answer in {"y", "yes"}:
            self.ledger.write(
                "confirm_accepted",
                {
                    **self._base_event(canonical_target),
                    "prompt_class": prompt_class,
                    "proposed_input": proposed_input,
                    "input_mode": input_mode,
                    "injected": False,
                },
            )
            return "confirm_accepted"

        self.ledger.write(
            "confirm_rejected",
            {
                **self._base_event(canonical_target),
                "prompt_class": prompt_class,
                "proposed_input": proposed_input,
                "input_mode": input_mode,
                "injected": False,
            },
        )
        return "confirm_rejected"

    def run(self) -> dict[str, object]:
        profile = self.config.profile_path.read_text(encoding="utf-8")
        answer_policy = self.config.answer_policy_path.read_text(encoding="utf-8")
        advisor = ExternalAdvisor(self.config.advisor_command)
        answered_questions: set[str] = set()
        target_lock: TargetLock | None = None
        turns = 0
        deadline = time.monotonic() + self.config.timeout_seconds

        self.ledger.write(
            "attach_started",
            {
                "target": self.config.target,
                "run_id": self._run_id(),
                "advisor_command": self.config.advisor_command,
                "backend": self.config.backend_name,
                "backend_model": self.config.backend_model,
                "backend_effort": self.config.backend_effort,
                "backend_source": self.config.backend_source,
                "question_regex": self.config.question_regex,
                "max_turns": self.config.max_turns,
                "timeout_seconds": self.config.timeout_seconds,
                "advisor_timeout_seconds": self.config.advisor_timeout_seconds,
                "mode": self.config.mode,
                "profile_id": self.config.profile_id,
                "config_hash": self.config.config_hash,
            },
        )
        self._record_status(
            canonical_target=self.config.target,
            status="watching",
            message=f"watching {self.config.target}",
        )

        try:
            while turns < self.config.max_turns and time.monotonic() < deadline:
                capture = self.terminal.capture(self.config.target)
                if capture.status != "captured":
                    self.ledger.write(
                        "attach_observed",
                        {
                            "target": self.config.target,
                            "canonical_target": capture.canonical_target,
                            "run_id": self._run_id(),
                            "status": capture.status,
                            "error": capture.error,
                        },
                    )
                    return {"status": capture.status, "turns": turns}

                if target_lock is None and self.config.lock_root is not None:
                    target_lock = TargetLock(
                        self.config.lock_root,
                        capture.canonical_target,
                        run_id=self._run_id(),
                    )
                    if not target_lock.acquire(steal=self.config.steal_lock):
                        self.ledger.write(
                            "target_locked",
                            {
                                **self._base_event(capture.canonical_target),
                                "injected": False,
                            },
                        )
                        return {"status": "target_locked", "turns": turns}

                original_screen_hash = fingerprint_transcript(capture.transcript)
                original_interaction_signature = _interaction_signature(
                    capture.transcript,
                    self.config.question_regex,
                )
                if (
                    self.config.target_fingerprint
                    and self.config.target_fingerprint != original_screen_hash
                ):
                    self.ledger.write(
                        "target_fingerprint_mismatch",
                        {
                            **self._base_event(capture.canonical_target),
                            "expected_fingerprint": self.config.target_fingerprint,
                            "actual_fingerprint": original_screen_hash,
                            "injected": False,
                        },
                    )
                    return {"status": "target_fingerprint_mismatch", "turns": turns}

                mode = self._current_mode()
                if mode == "paused":
                    self.ledger.write(
                        "attach_observed",
                        {
                            **self._base_event(capture.canonical_target),
                            "status": "paused",
                            "turns": turns,
                        },
                    )
                    time.sleep(self.config.poll_interval_seconds)
                    continue

                screen = analyze_screen(capture.transcript)
                if screen.state != "unknown":
                    prompt = SimpleNamespace(
                        prompt_class=screen.state,
                        question=screen.question,
                    )
                else:
                    prompt = classify_prompt(
                        capture.transcript,
                        question_regex=self.config.question_regex,
                    )
                self._record_status(
                    canonical_target=capture.canonical_target,
                    status="prompt_observed",
                    prompt_class=prompt.prompt_class,
                    message=(
                        screen.current_input
                        or prompt.question
                        or capture.transcript.splitlines()[-1]
                        if capture.transcript.splitlines()
                        else ""
                    ),
                )
                action = None
                response = None
                contract: TaskContract | None = None
                redacted = redact_screen(
                    screen.visible_tail[-4000:] if screen.visible_tail else capture.transcript[-4000:],
                    self.config.redact_regex,
                )

                actionable_classes = {"question", "question_waiting", "choice_waiting", "draft_ready"}
                if action is None and prompt.prompt_class not in actionable_classes:
                    self.ledger.write(
                        "attach_observed",
                        {
                            **self._base_event(capture.canonical_target),
                            "status": "no_actionable_prompt",
                            "prompt_class": prompt.prompt_class,
                            "turns": turns,
                        },
                    )
                    self._record_status(
                        canonical_target=capture.canonical_target,
                        status="waiting",
                        prompt_class=prompt.prompt_class,
                        message="no actionable prompt",
                    )
                    time.sleep(self.config.poll_interval_seconds)
                    continue

                question_key = (
                    f"{prompt.prompt_class}:{screen.current_input or prompt.question}"
                    if screen.state != "unknown"
                    else prompt.question or capture.transcript[-4000:]
                )
                if question_key in answered_questions:
                    self.ledger.write(
                        "attach_finished",
                        {
                            "target": self.config.target,
                            "run_id": self._run_id(),
                            "status": "stalled",
                            "turns": turns,
                        },
                    )
                    return {"status": "stalled", "turns": turns}

                if action is None:
                    try:
                        contract = _load_optional_contract(self.config)
                        request = AdvisorRequest(
                            question=prompt.question or "",
                            screen_tail=redacted.text,
                            profile=profile,
                            answer_policy=answer_policy,
                            turn_index=turns + 1,
                            screen_state=screen.state,
                            current_input=screen.current_input,
                            screen_adapter=screen.adapter,
                            seed=contract.seed if contract else "",
                            wiw=contract.wiw if contract else "",
                            not_to_do=contract.not_to_do if contract else "",
                            final_artifact=contract.final_artifact if contract else "",
                            contract_hashes=contract.hashes if contract else {},
                            redacted_screen_hash=redacted.hash,
                            redaction_count=redacted.count,
                        )
                        response = advisor.ask(
                            request,
                            timeout_seconds=self.config.advisor_timeout_seconds,
                        )
                    except TimeoutError as error:
                        self.ledger.write(
                            "advisor_timeout",
                            {
                                **self._base_event(capture.canonical_target),
                                "error": str(error),
                                "injected": False,
                            },
                        )
                        return {"status": "advisor_timeout", "turns": turns}
                    except (RuntimeError, ValueError) as error:
                        self.ledger.write(
                            "advisor_error",
                            {
                                **self._base_event(capture.canonical_target),
                                "error": str(error),
                                "injected": False,
                            },
                        )
                        return {"status": "advisor_error", "turns": turns}

                    if response.action == "WAIT":
                        self.ledger.write(
                            "attach_observed",
                            {
                                **self._base_event(capture.canonical_target),
                                "status": "advisor_wait",
                                "prompt_class": prompt.prompt_class,
                                "reason": response.reason,
                                "confidence": response.confidence,
                                "injected": False,
                            },
                        )
                        time.sleep(self.config.poll_interval_seconds)
                        continue
                    if response.action == "ESCALATE":
                        self.ledger.write(
                            "attach_escalated",
                            {
                                **self._base_event(capture.canonical_target),
                                "question": prompt.question,
                                "prompt_class": prompt.prompt_class,
                                "reason": response.reason,
                                "confidence": response.confidence,
                                "backend": self.config.backend_name,
                                "backend_model": self.config.backend_model,
                                "backend_effort": self.config.backend_effort,
                                "injected": False,
                                "redacted_screen_hash": redacted.hash,
                                "redaction_count": redacted.count,
                                "contract_hashes": contract.hashes if contract else {},
                            },
                        )
                        return {"status": "escalated", "turns": turns}
                    action = _input_action_from_response(response)
                    if action is None:
                        self.ledger.write(
                            "attach_escalated",
                            {
                                **self._base_event(capture.canonical_target),
                                "question": prompt.question,
                                "prompt_class": prompt.prompt_class,
                                "reason": response.reason,
                                "confidence": response.confidence,
                                "backend": self.config.backend_name,
                                "backend_model": self.config.backend_model,
                                "backend_effort": self.config.backend_effort,
                                "injected": False,
                                "redacted_screen_hash": redacted.hash,
                                "redaction_count": redacted.count,
                                "contract_hashes": contract.hashes if contract else {},
                            },
                        )
                        return {"status": "escalated", "turns": turns}

                proposed_input = action.text if action.mode == "text" else " ".join(action.keys)
                reason = response.reason if response else "quick_reply"
                self._record_display(
                    canonical_target=capture.canonical_target,
                    prompt_class=prompt.prompt_class,
                    reason=reason,
                    proposed_input=proposed_input,
                    input_mode=action.mode,
                )

                mode = self._current_mode()
                gate_result = evaluate_policy_gate(
                    GateContext(
                        action_kind=_gate_action_kind(action, response),
                        action_source=_gate_action_source(action.source),
                        contract_loaded=contract is not None,
                        seed_measurable=contract is not None,
                        tier=_tier_for_mode(mode),
                        draft_author=screen.draft_author,
                        worker_claim=screen.worker_claim,
                        hard_stop=screen.hard_stop,
                        readback_capable=True,
                    )
                )
                if gate_result.decision == ESCALATE:
                    self.ledger.write(
                        "attach_escalated",
                        {
                            **self._base_event(capture.canonical_target),
                            "question": prompt.question,
                            "prompt_class": prompt.prompt_class,
                            "reason": gate_result.reason,
                            "confidence": response.confidence if response else "high",
                            "backend": self.config.backend_name,
                            "backend_model": self.config.backend_model,
                            "backend_effort": self.config.backend_effort,
                            "injected": False,
                            "redacted_screen_hash": redacted.hash,
                            "redaction_count": redacted.count,
                            "contract_hashes": contract.hashes if contract else {},
                            "policy_gate_decision": gate_result.decision,
                            "detected_state": _detected_state(screen, prompt),
                            "contract_clause": gate_result.reason,
                            "risk": _risk_for_screen(screen),
                        },
                    )
                    return {"status": "escalated", "turns": turns}
                if gate_result.decision == DOWNGRADE_SUGGEST:
                    mode = "suggest"

                if mode == "confirm":
                    confirm_status = self._confirm(
                        canonical_target=capture.canonical_target,
                        prompt_class=prompt.prompt_class,
                        reason=reason,
                        proposed_input=proposed_input,
                        input_mode=action.mode,
                    )
                    if confirm_status != "confirm_accepted":
                        return {"status": confirm_status, "turns": turns}

                if mode == "suggest":
                    injected = False
                    enter_sent = False
                    readback_status = "suggest_only"
                    canonical_target = capture.canonical_target
                    injection_status = "suggested"
                else:
                    latest = self.terminal.capture(self.config.target)
                    latest_hash = (
                        fingerprint_transcript(latest.transcript)
                        if latest.status == "captured"
                        else ""
                    )
                    latest_interaction_signature = (
                        _interaction_signature(
                            latest.transcript,
                            self.config.question_regex,
                        )
                        if latest.status == "captured"
                        else ""
                    )
                    if (
                        latest.status != "captured"
                        or latest_interaction_signature != original_interaction_signature
                    ):
                        self.ledger.write(
                            "stale_screen",
                            {
                                **self._base_event(capture.canonical_target),
                                "original_screen_hash": original_screen_hash,
                                "latest_screen_hash": latest_hash,
                                "original_interaction_signature": original_interaction_signature,
                                "latest_interaction_signature": latest_interaction_signature,
                                "latest_status": latest.status,
                                "injected": False,
                            },
                        )
                        self._record_status(
                            canonical_target=capture.canonical_target,
                            status="stale_screen",
                            prompt_class=prompt.prompt_class,
                            message="screen changed before injection",
                        )
                        return {"status": "stale_screen", "turns": turns}

                    if action.mode == "text":
                        injection = self.terminal.send(capture.canonical_target, action.text)
                        injected = injection.enter_sent and injection.status == "sent"
                        enter_sent = injection.enter_sent
                        readback_status = injection.readback_status
                        canonical_target = injection.canonical_target
                        injection_status = injection.status
                    else:
                        injection = self.terminal.send_keys(
                            capture.canonical_target,
                            action.keys,
                        )
                        injected = injection.status == "sent"
                        enter_sent = injection.enter_sent
                        readback_status = injection.readback_status
                        canonical_target = injection.canonical_target
                        injection_status = injection.status

                turns += 1
                self._record_status(
                    canonical_target=canonical_target,
                    status="injection_result",
                    prompt_class=prompt.prompt_class,
                    message=f"injected={injected} enter_sent={enter_sent} readback={readback_status}",
                    injected=injected,
                    enter_sent=enter_sent,
                    readback_status=readback_status,
                )
                answered_questions.add(question_key)
                self.ledger.write(
                    "attach_turn",
                    {
                        **self._base_event(canonical_target),
                        "turn_index": turns,
                        "question": prompt.question,
                        "action": response.action if response else "ANSWER",
                        "confidence": response.confidence if response else "high",
                        "reason": reason,
                        "answer_hash": sha256(proposed_input.encode("utf-8")).hexdigest(),
                        "answer_preview": proposed_input[:120],
                        "screen_tail_hash": sha256(
                            capture.transcript[-4000:].encode("utf-8")
                        ).hexdigest(),
                        "original_screen_hash": original_screen_hash,
                        "redacted_screen_hash": redacted.hash,
                        "redaction_count": redacted.count,
                        "contract_hashes": contract.hashes if contract else {},
                        "readback_status": readback_status,
                        "enter_sent": enter_sent,
                        "injected": injected,
                        "backend": self.config.backend_name,
                        "backend_model": self.config.backend_model,
                        "backend_effort": self.config.backend_effort,
                        "backend_source": self.config.backend_source,
                        "answer_source": action.source,
                        "prompt_class": prompt.prompt_class,
                        "input_mode": action.mode,
                        "keys": action.keys,
                        "choice_label": action.choice_label,
                        "mode": mode,
                        "detected_state": _detected_state(screen, prompt),
                        "contract_clause": gate_result.reason,
                        "risk": _risk_for_screen(screen),
                        "policy_gate_decision": gate_result.decision,
                    },
                )
                if not injected and mode != "suggest":
                    return {"status": injection_status, "turns": turns}

            status = "completed" if turns > 0 else "timeout"
            self.ledger.write(
                "attach_finished",
                {"target": self.config.target, "run_id": self._run_id(), "status": status, "turns": turns},
            )
            return {"status": status, "turns": turns}
        finally:
            if target_lock is not None:
                target_lock.release()
