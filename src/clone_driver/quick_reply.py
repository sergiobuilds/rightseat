from __future__ import annotations

import re


def quick_skippable(*, transcript: str, quick_regex: str) -> bool:
    """Return only whether the screen matches a quick reject/pass rule.

    Quick rules must not author text or keys. Input content is generated only
    by the advisor path with a loaded contract.
    """
    if not quick_regex:
        return False
    return bool(re.search(quick_regex, transcript))
