from __future__ import annotations


def format_attach_status(
    *,
    run_id: str,
    target: str,
    mode: str,
    backend: str,
    model: str,
    effort: str,
    answer_source: str,
    input_mode: str,
    status: str,
) -> str:
    return (
        f"run={run_id} target={target} mode={mode} "
        f"backend={backend} model={model} effort={effort} "
        f"source={answer_source} input_mode={input_mode} status={status}"
    )
