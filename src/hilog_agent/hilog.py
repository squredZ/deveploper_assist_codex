from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
from pathlib import Path
import re

logger = logging.getLogger(__name__)

HILOG_RE = re.compile(
    r"^(?P<time>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{1,6})\s+"
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
    logger.info("parsing hilog file path=%s", path)
    events: list[HilogEvent] = []
    total = 0
    for line_no, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        total += 1
        match = HILOG_RE.match(raw_line)
        if match is None:
            continue
        events.append(HilogEvent(raw=raw_line, line=line_no, **match.groupdict()))
    parsed = ParsedHilog(
        events=events,
        total_lines=total,
        parsed_lines=len(events),
        unparsed_lines=total - len(events),
    )
    logger.info(
        "parsed hilog file path=%s total_lines=%d parsed_lines=%d unparsed_lines=%d",
        path,
        parsed.total_lines,
        parsed.parsed_lines,
        parsed.unparsed_lines,
    )
    return parsed


def filter_events_by_time(
    events: list[HilogEvent],
    center_time: datetime,
    window_seconds: int,
) -> list[HilogEvent]:
    start = center_time - timedelta(seconds=window_seconds)
    end = center_time + timedelta(seconds=window_seconds)
    filtered = [event for event in events if start <= event.timestamp <= end]
    logger.info(
        "filtered hilog events center_time=%s window_seconds=%d input_events=%d output_events=%d",
        center_time,
        window_seconds,
        len(events),
        len(filtered),
    )
    return filtered
