from hilog_agent.hilog import HilogEvent
from hilog_agent.matcher import LogPattern, event_matches_pattern, match_events


def test_substring_match_is_case_sensitive():
    event = HilogEvent(
        time="2026-06-28 14:35:01.350",
        pid="1234",
        tid="5678",
        level="I",
        tag="CameraService",
        message="Start capture",
        raw="raw",
        line=1,
    )
    matches = match_events(
        [event],
        [LogPattern(tag="CameraService", pattern="Start capture", match_type="substring")],
    )
    assert len(matches) == 1
    assert not event_matches_pattern(
        event,
        LogPattern(tag="CameraService", pattern="start capture", match_type="substring"),
    )


def test_regex_match():
    event = HilogEvent(
        time="2026-06-28 14:35:03.500",
        pid="1234",
        tid="5678",
        level="E",
        tag="CameraService",
        message="Capture failed err=-1",
        raw="raw",
        line=1,
    )
    matches = match_events(
        [event],
        [LogPattern(tag="CameraService", pattern=r"err=-\d+", match_type="regex")],
    )
    assert len(matches) == 1


def test_match_is_tag_and_level_sensitive():
    event = HilogEvent(
        time="2026-06-28 14:35:03.500",
        pid="1234",
        tid="5678",
        level="E",
        tag="CameraService",
        message="Capture failed",
        raw="raw",
        line=1,
    )
    assert not event_matches_pattern(
        event,
        LogPattern(tag="CameraUI", pattern="Capture failed", match_type="substring"),
    )
    assert not event_matches_pattern(
        event,
        LogPattern(
            tag="CameraService",
            pattern="Capture failed",
            match_type="substring",
            level="I",
        ),
    )


def test_word_level_error_matches_single_letter_event_level():
    event = HilogEvent(
        time="2026-06-28 14:35:03.500",
        pid="1234",
        tid="5678",
        level="E",
        tag="CameraService",
        message="Capture failed",
        raw="raw",
        line=1,
    )

    assert event_matches_pattern(
        event,
        LogPattern(
            tag="CameraService",
            pattern="Capture failed",
            match_type="substring",
            level="ERROR",
        ),
    )


def test_word_level_info_matches_single_letter_event_level():
    event = HilogEvent(
        time="2026-06-28 14:35:01.350",
        pid="1234",
        tid="5678",
        level="I",
        tag="CameraService",
        message="Start capture",
        raw="raw",
        line=1,
    )

    assert event_matches_pattern(
        event,
        LogPattern(
            tag="CameraService",
            pattern="Start capture",
            match_type="substring",
            level="INFO",
        ),
    )
