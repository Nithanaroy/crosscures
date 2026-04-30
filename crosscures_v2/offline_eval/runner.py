"""Run the full eval pipeline across all cases."""
import argparse
from datetime import datetime

from offline_eval.config import LLMConfig, RESULTS_DIR
from offline_eval.assembler import assemble_input, get_all_case_ids
from offline_eval.generator import generate_questions
from offline_eval.scorer import get_gold_targets, match_questions, aggregate_scores
from offline_eval.normalizer import normalize_questions
from offline_eval.models import CaseResult, PipelineConfig, PipelineOutput


def run_eval(config: LLMConfig, case_ids: list = None, dry_run: bool = False):
    """Run eval pipeline for all (or specified) cases."""
    case_ids = case_ids or get_all_case_ids()
    print(f"[INFO] Running eval on {len(case_ids)} cases with model={config.model} ({config.provider})")

    all_results: list[CaseResult] = []

    for case_id in case_ids:
        print(f"\n{'='*60}")
        print(f"[CASE] {case_id}")
        print(f"{'='*60}")

        # Step 1: Assemble input
        case_input = assemble_input(case_id)
        print(f"  Domain:     {case_input.case_domain}")
        print(f"  Case:       {case_input.case_name}")
        print(f"  Notes:      {case_input.note_count} ({case_input.char_count:,} chars)")

        if dry_run:
            print(f"  [DRY RUN] Skipping LLM calls")
            continue

        # Step 2: Generate questions
        print(f"  Generating questions...")
        questions, gen_meta = generate_questions(
            case_input.notes_text,
            case_domain=case_input.case_domain,
            config=config,
        )
        print(f"  Generated {len(questions)} questions")
        for q in questions[:5]:
            print(f"    {q.rank}. {q.raw[:80]}")
        if len(questions) > 5:
            print(f"    ... and {len(questions) - 5} more")

        # Step 3: Normalize
        gold_targets = get_gold_targets(case_id)
        print(f"  Gold targets: {len(gold_targets)}")
        print(f"  Normalizing questions...")
        normalized = normalize_questions(
            questions, gold_targets,
            case_domain=case_input.case_domain,
            config=config,
        )
        print(f"  Normalized {len(normalized)} questions")

        # Step 4: Score
        result = match_questions(normalized, gold_targets)
        scores = result.scores
        print(f"  Scores:")
        print(f"    coverage:           {scores.coverage:.1%} ({scores.matched_count}/{scores.total_targets})")
        print(f"    weighted_coverage:  {scores.weighted_coverage:.1%}")
        print(f"    grounded_precision: {scores.grounded_precision:.1%}")
        print(f"    top_5_coverage:     {scores.top_5_coverage:.1%}")
        print(f"    top_10_coverage:    {scores.top_10_coverage:.1%}")

        # Missed targets
        missed = [t for t in result.target_detail if not t.hit]
        if missed:
            print(f"  Missed targets ({len(missed)}):")
            for t in missed:
                print(f"    [{t.severity}/{t.weight}] {t.concept}/{t.target_slot}")

        case_result = CaseResult(
            case_id=case_id,
            case_domain=case_input.case_domain,
            case_name=case_input.case_name,
            note_count=case_input.note_count,
            char_count=case_input.char_count,
            generated_questions=normalized,
            scores=scores,
            target_detail=result.target_detail,
            unmatched_questions=result.unmatched_questions,
            gen_meta=gen_meta,
        )
        all_results.append(case_result)

    if dry_run:
        print("\n[DONE] Dry run complete. No LLM calls made.")
        return

    # Aggregate
    agg = aggregate_scores(all_results)
    print(f"\n{'='*60}")
    print(f"[AGGREGATE] {agg.total_cases} cases, {agg.total_matched}/{agg.total_targets} targets matched")
    print(f"  coverage:           {agg.coverage:.1%}")
    print(f"  weighted_coverage:  {agg.weighted_coverage:.1%}")
    print(f"  grounded_precision: {agg.grounded_precision:.1%}")
    print(f"  top_5_coverage:     {agg.top_5_coverage:.1%}")
    print(f"  top_10_coverage:    {agg.top_10_coverage:.1%}")

    # Save results
    RESULTS_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = RESULTS_DIR / f"eval_{config.provider}_{config.model}_{ts}.json"
    output = PipelineOutput(
        run_timestamp=ts,
        config=PipelineConfig(
            provider=config.provider,
            model=config.model,
            normalizer_model=config.normalizer_model,
            temperature=config.temperature,
        ),
        aggregate_scores=agg,
        case_results=all_results,
    )
    out_path.write_text(output.model_dump_json(indent=2))
    print(f"\n[SAVED] {out_path}")


def main():
    parser = argparse.ArgumentParser(description="CrossCures history-taking eval pipeline")
    # Generator LLM
    parser.add_argument("--provider", choices=["openai", "ollama"], default="ollama")
    parser.add_argument("--model", default="llama3")
    parser.add_argument("--base-url", default="", help="Custom API base URL for generator")
    parser.add_argument("--api-key", default="", help="API key for generator (or set OPENAI_API_KEY)")

    # Normalizer LLM (defaults to generator settings if not specified)
    parser.add_argument("--normalizer-provider", choices=["openai", "ollama"], default="",
                        help="Provider for normalizer (default: same as --provider)")
    parser.add_argument("--normalizer-model", default="",
                        help="Model for normalization (default: same as --model)")
    parser.add_argument("--normalizer-base-url", default="", help="Custom API base URL for normalizer")
    parser.add_argument("--normalizer-api-key", default="", help="API key for normalizer")

    parser.add_argument("--cases", nargs="*", help="Specific case IDs to run (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="Assemble inputs only, no LLM calls")
    parser.add_argument("--temperature", type=float, default=0.3)
    args = parser.parse_args()

    config = LLMConfig(
        provider=args.provider,
        model=args.model,
        temperature=args.temperature,
        normalizer_provider=args.normalizer_provider,
        normalizer_model=args.normalizer_model,
        normalizer_base_url=args.normalizer_base_url,
        normalizer_api_key=args.normalizer_api_key,
    )
    if args.base_url:
        config.base_url = args.base_url
    if args.api_key:
        config.api_key = args.api_key

    run_eval(config, case_ids=args.cases, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
