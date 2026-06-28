from hilog_agent.hilog import HilogEvent
from hilog_agent.schemas.results import Evidence, RawRef


def make_failure_log_evidence(
    evidence_id: str,
    event: HilogEvent,
    feature: str,
    chain: str,
    step: str | None,
    summary: str,
    confidence_delta: float,
) -> Evidence:
    return Evidence(
        id=evidence_id,
        source="hilog",
        type="failure_log_hit",
        feature=feature,
        chain=chain,
        step=step,
        severity="high",
        confidence_delta=confidence_delta,
        summary=summary,
        raw_ref=RawRef(file=None, line=event.line, timestamp=event.time),
    )
