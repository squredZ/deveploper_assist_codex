from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import re


HILOG_RE = re.compile(
    r"^(?P<time>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3})\s+"
    r"(?P<pid>\d+)\s+(?P<tid>\d+)\s+"
    r"(?P<level>[A-Z])\s+"
    r"(?P<tag>[^:]+):\s*(?P<message>.*)$"
)


@dataclass(frozen=True)
class HilogEvent:
    time: str
    pid: str
    tid: str
    level: str
    tag: str
    message: str
    raw: str
    line: int

    @property
    def timestamp(self) -> datetime:
        return datetime.strptime(self.time, "%Y-%m-%d %H:%M:%S.%f")


@dataclass(frozen=True)
class ParsedHilog:
    events: list[HilogEvent]
    total_lines: int
    parsed_lines: int
    unparsed_lines: int


def parse_hilog_file(path: Path) -> ParsedHilog:
    events: list[HilogEvent] = []
    total = 0
    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        total += 1
        match = HILOG_RE.match(raw_line)
        if match is None:
            continue
        events.append(HilogEvent(raw=raw_line, line=line_no, **match.groupdict()))
    return ParsedHilog(
        events=events,
        total_lines=total,
        parsed_lines=len(events),
        unparsed_lines=total - len(events),
    )


def filter_events_by_time(
    events: list[HilogEvent],
    center_time: datetime,
    window_seconds: int,
) -> list[HilogEvent]:
    start = center_time - timedelta(seconds=window_seconds)
    end = center_time + timedelta(seconds=window_seconds)
    return [event for event in events if start <= event.timestamp <= end]
