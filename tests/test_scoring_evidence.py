from pydantic import ValidationError

from hilog_agent.evidence import make_failure_log_evidence
from hilog_agent.hilog import HilogEvent
from hilog_agent.scoring import confidence_label, score_feature_keywords
from hilog_agent.schemas.results import (
    AnalysisResult,
    AnalysisStats,
    ChainStepStatus,
    Conclusion,
    Evidence,
    RootCause,
)


def test_score_feature_keywords_counts_question_hits():
    score = score_feature_keywords("拍照不出图", ["拍照", "录像"], ["拍照不出图"])
    assert score == 6


def test_confidence_label():
    assert confidence_label(80) == "high"
    assert confidence_label(45) == "medium"
    assert confidence_label(10) == "low"


def test_make_failure_log_evidence():
    event = HilogEvent(
        time="2026-06-28 14:35:03.500",
        pid="1234",
        tid="5678",
        level="E",
        tag="CameraService",
        message="Capture failed",
        raw="raw",
        line=3,
    )
    evidence = make_failure_log_evidence(
        evidence_id="ev_001",
        event=event,
        feature="camera_capture",
        chain="normal_capture",
        step="capture_request",
        summary="命中 Capture failed",
        confidence_delta=5,
    )
    assert evidence.id == "ev_001"
    assert evidence.source == "hilog"
    assert evidence.type == "failure_log_hit"
    assert evidence.raw_ref.line == 3
    assert evidence.raw_ref.timestamp == "2026-06-28 14:35:03.500"


def test_analysis_result_validates_root_cause_evidence_references():
    evidence = Evidence(
        id="ev_001",
        source="hilog",
        type="failure_log_hit",
        summary="failure found",
    )

    result = AnalysisResult(
        feature="camera_capture",
        conclusion=Conclusion(summary="failed", confidence="medium"),
        root_causes=[
            RootCause(
                title="Capture failed",
                confidence="medium",
                supporting_evidence=["ev_001"],
                gaps=[],
                next_actions=[],
            )
        ],
        chain_status=[],
        evidence=[evidence],
        stats=AnalysisStats(),
    )

    assert result.root_causes[0].supporting_evidence == ["ev_001"]

    try:
        AnalysisResult(
            feature="camera_capture",
            conclusion=Conclusion(summary="failed", confidence="medium"),
            root_causes=[
                RootCause(
                    title="Capture failed",
                    confidence="medium",
                    supporting_evidence=["missing"],
                    gaps=[],
                    next_actions=[],
                )
            ],
            chain_status=[],
            evidence=[evidence],
            stats=AnalysisStats(),
        )
    except ValidationError as exc:
        assert "root cause references unknown evidence" in str(exc)
    else:
        raise AssertionError("expected validation error")


def test_analysis_result_validates_chain_status_evidence_references():
    evidence = Evidence(
        id="ev_001",
        source="hilog",
        type="failure_log_hit",
        summary="failure found",
    )

    result = AnalysisResult(
        feature="camera_capture",
        conclusion=Conclusion(summary="failed", confidence="medium"),
        root_causes=[],
        chain_status=[
            ChainStepStatus(
                step="capture_request",
                status="abnormal",
                evidence=["ev_001"],
                summary="failed",
            )
        ],
        evidence=[evidence],
        stats=AnalysisStats(),
    )

    assert result.chain_status[0].evidence == ["ev_001"]

    try:
        AnalysisResult(
            feature="camera_capture",
            conclusion=Conclusion(summary="failed", confidence="medium"),
            root_causes=[],
            chain_status=[
                ChainStepStatus(
                    step="capture_request",
                    status="abnormal",
                    evidence=["missing"],
                    summary="failed",
                )
            ],
            evidence=[evidence],
            stats=AnalysisStats(),
        )
    except ValidationError as exc:
        assert "chain status references unknown evidence" in str(exc)
    else:
        raise AssertionError("expected validation error")


def test_analysis_result_rejects_duplicate_evidence_ids():
    evidence = Evidence(
        id="ev_001",
        source="hilog",
        type="failure_log_hit",
        summary="failure found",
    )
    duplicate = Evidence(
        id="ev_001",
        source="hilog",
        type="expected_log_hit",
        summary="same id",
    )

    try:
        AnalysisResult(
            feature="camera_capture",
            conclusion=Conclusion(summary="failed", confidence="medium"),
            root_causes=[],
            chain_status=[],
            evidence=[evidence, duplicate],
            stats=AnalysisStats(),
        )
    except ValidationError as exc:
        assert "duplicate evidence id" in str(exc)
    else:
        raise AssertionError("expected validation error")
