"""Score normalized questions against gold-standard history targets."""
import duckdb
from offline_eval.config import DUCKDB_PATH
from offline_eval.models import (
    HistoryTarget, NormalizedQuestion, CaseScores, TargetDetail,
    UnmatchedQuestion, MatchResult, AggregateScores,
)


def get_gold_targets(case_id: str, db_path: str = None) -> list[HistoryTarget]:
    """Fetch gold-standard history targets for a case."""
    db_path = db_path or str(DUCKDB_PATH)
    con = duckdb.connect(db_path, read_only=True)
    rows = con.execute("""
        SELECT target_id, case_domain, concept, target_slot, severity, weight
        FROM history_targets
        WHERE case_id = ?
    """, [case_id]).fetchall()
    con.close()
    return [
        HistoryTarget(
            target_id=r[0], case_id=case_id, patient_id=0,
            case_domain=r[1], concept=r[2], target_slot=r[3],
            severity=r[4], weight=r[5],
        )
        for r in rows
    ]


def match_questions(normalized_questions: list[NormalizedQuestion],
                    gold_targets: list[HistoryTarget]) -> MatchResult:
    """Match normalized questions against gold targets and compute scores.

    A question matches a target if domain, concept, and target_slot all match.
    Each target can be matched at most once (first match wins by rank).
    """
    matched_targets: dict[str, NormalizedQuestion] = {}
    unmatched_questions: list[NormalizedQuestion] = []

    # Build target lookup: (domain, concept, slot) -> target
    target_lookup: dict[tuple[str, str, str], HistoryTarget] = {}
    for t in gold_targets:
        key = (t.case_domain, t.concept, t.target_slot)
        if key not in target_lookup:
            target_lookup[key] = t

    # Match in rank order
    for q in sorted(normalized_questions, key=lambda x: x.rank):
        key = (q.domain, q.concept, q.target_slot)
        target = target_lookup.get(key)
        if target and target.target_id not in matched_targets:
            matched_targets[target.target_id] = q
            q.matched_target_id = target.target_id
        else:
            q.matched_target_id = None
            unmatched_questions.append(q)

    # Compute scores
    total_targets = len(gold_targets)
    matched_count = len(matched_targets)
    total_weight = sum(t.weight for t in gold_targets)
    matched_weight = sum(
        t.weight for t in gold_targets if t.target_id in matched_targets
    )
    total_generated = len(normalized_questions)
    grounded_and_matched = sum(
        1 for q in normalized_questions
        if q.matched_target_id and q.grounded
    )

    coverage = matched_count / total_targets if total_targets > 0 else 0.0
    weighted_coverage = matched_weight / total_weight if total_weight > 0 else 0.0
    grounded_precision = grounded_and_matched / total_generated if total_generated > 0 else 0.0

    # Top-K coverage
    def top_k_coverage(k: int) -> float:
        top_k = sorted(normalized_questions, key=lambda x: x.rank)[:k]
        top_k_matched: set[str] = set()
        for q in top_k:
            key = (q.domain, q.concept, q.target_slot)
            target = target_lookup.get(key)
            if target:
                top_k_matched.add(target.target_id)
        return len(top_k_matched) / total_targets if total_targets > 0 else 0.0

    scores = CaseScores(
        coverage=round(coverage, 4),
        weighted_coverage=round(weighted_coverage, 4),
        grounded_precision=round(grounded_precision, 4),
        top_5_coverage=round(top_k_coverage(5), 4),
        top_10_coverage=round(top_k_coverage(10), 4),
        matched_count=matched_count,
        total_targets=total_targets,
        total_generated=total_generated,
    )

    # Per-target detail: which targets were hit vs missed
    target_detail = []
    for t in gold_targets:
        hit = t.target_id in matched_targets
        detail = TargetDetail(
            target_id=t.target_id,
            concept=t.concept,
            target_slot=t.target_slot,
            severity=t.severity,
            weight=t.weight,
            hit=hit,
            matched_by=matched_targets[t.target_id].raw if hit else None,
            matched_rank=matched_targets[t.target_id].rank if hit else None,
        )
        target_detail.append(detail)

    return MatchResult(
        scores=scores,
        target_detail=target_detail,
        unmatched_questions=[
            UnmatchedQuestion(
                rank=q.rank, raw=q.raw, domain=q.domain,
                concept=q.concept, target_slot=q.target_slot,
            )
            for q in unmatched_questions
        ],
    )


def aggregate_scores(case_results: list) -> AggregateScores:
    """Aggregate scores across multiple cases."""
    if not case_results:
        return AggregateScores()

    metrics = ["coverage", "weighted_coverage", "grounded_precision",
               "top_5_coverage", "top_10_coverage"]
    agg: dict[str, float | int] = {}
    for m in metrics:
        values = [getattr(r.scores, m) for r in case_results]
        agg[m] = round(sum(values) / len(values), 4) if values else 0.0

    agg["total_cases"] = len(case_results)
    agg["total_targets"] = sum(r.scores.total_targets for r in case_results)
    agg["total_matched"] = sum(r.scores.matched_count for r in case_results)
    return AggregateScores(**agg)
