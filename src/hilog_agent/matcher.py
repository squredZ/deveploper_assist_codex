from dataclasses import dataclass
import re
from typing import Literal

from hilog_agent.hilog import HilogEvent


@dataclass(frozen=True)
class LogPattern:
    tag: str
    pattern: str
    match_type: Literal["substring", "regex"] = "substring"
    level: str | None = None


@dataclass(frozen=True)
class LogMatch:
    event: HilogEvent
    pattern: LogPattern


def event_matches_pattern(event: HilogEvent, pattern: LogPattern) -> bool:
    if event.tag != pattern.tag:
        return False
    if pattern.level and event.level != pattern.level:
        return False
    if pattern.match_type == "regex":
        return re.search(pattern.pattern, event.message) is not None
    return pattern.pattern in event.message


def match_events(events: list[HilogEvent], patterns: list[LogPattern]) -> list[LogMatch]:
    matches: list[LogMatch] = []
    for event in events:
        for pattern in patterns:
            if event_matches_pattern(event, pattern):
                matches.append(LogMatch(event=event, pattern=pattern))
    return matches
