from datetime import datetime
from pathlib import Path

from hilog_agent.hilog import filter_events_by_time, parse_hilog_file


def test_parse_hilog_counts_unparsed_lines():
    parsed = parse_hilog_file(Path("tests/fixtures/hilog/camera_capture.log"))
    assert parsed.total_lines == 4
    assert parsed.parsed_lines == 3
    assert parsed.unparsed_lines == 1
    assert parsed.events[0].tag == "CameraUI"


def test_hilog_event_has_timestamp_property():
    parsed = parse_hilog_file(Path("tests/fixtures/hilog/camera_capture.log"))
    assert parsed.events[0].timestamp == datetime(2026, 6, 28, 14, 35, 1, 120000)


def test_parse_hilog_accepts_variable_fractional_seconds(tmp_path: Path):
    log_path = tmp_path / "variable_fraction.log"
    log_path.write_text(
        "2026-06-28 14:35:01.1  1234  5678 I CameraUI: click capture\n",
        encoding="utf-8",
    )

    parsed = parse_hilog_file(log_path)

    assert parsed.parsed_lines == 1
    assert parsed.events[0].timestamp == datetime(2026, 6, 28, 14, 35, 1, 100000)


def test_filter_events_by_time():
    parsed = parse_hilog_file(Path("tests/fixtures/hilog/camera_capture.log"))
    events = filter_events_by_time(
        parsed.events,
        datetime(2026, 6, 28, 14, 35, 1),
        1,
    )
    assert [event.tag for event in events] == ["CameraUI", "CameraService"]
