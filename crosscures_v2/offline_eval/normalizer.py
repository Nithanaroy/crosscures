"""Normalize raw questions to (domain, concept, target_slot) triples."""
import json
from openai import OpenAI
from offline_eval.config import LLMConfig, DEFAULT_CONFIG
from offline_eval.models import RawQuestion, NormalizedQuestion, NormalizedQuestionList, HistoryTarget


NORMALIZE_PROMPT = """\
You are a clinical NLP system. Map each patient follow-up question to the BEST matching target from the list below.

VALID TARGETS (pick one per question):
{targets_text}

For each question, pick the single best matching target. If no target fits, use "other" for all fields.

Rules:
- Use EXACT domain/concept/target_slot strings from the list above
- "grounded" = true if the question relates to information in the clinical notes"""


def normalize_questions(questions: list[RawQuestion], gold_targets: list[HistoryTarget],
                        case_domain: str, config: LLMConfig = None) -> list[NormalizedQuestion]:
    """Map raw questions to domain/concept/target_slot triples via LLM."""
    config = config or DEFAULT_CONFIG

    # Build the valid targets text for the prompt
    targets_text = "\n".join(
        f"  {t.case_domain} / {t.concept} / {t.target_slot}"
        for t in gold_targets
    )
    questions_text = "\n".join(f"{q.rank}. {q.raw}" for q in questions)

    client = OpenAI(base_url=config.normalizer_base_url, api_key=config.normalizer_api_key)
    response = client.chat.completions.create(
        model=config.normalizer_model,
        messages=[
            {"role": "system", "content": NORMALIZE_PROMPT.format(targets_text=targets_text)},
            {"role": "user", "content": questions_text},
        ],
        max_tokens=config.max_tokens,
        temperature=0.1,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "normalized_questions",
                "strict": True,
                "schema": NormalizedQuestionList.model_json_schema(),
            },
        },
    )

    raw_output = response.choices[0].message.content.strip()
    parsed = NormalizedQuestionList.model_validate(json.loads(raw_output))

    # Index by rank for lookup
    llm_by_rank = {item.rank: item for item in parsed.questions}
    valid_slots = {t.target_slot for t in gold_targets}

    normalized = []
    for q in questions:
        llm_item = llm_by_rank.get(q.rank)

        if llm_item and llm_item.target_slot in valid_slots:
            normalized.append(NormalizedQuestion(
                rank=q.rank,
                raw=q.raw,
                domain=llm_item.domain,
                concept=llm_item.concept,
                target_slot=llm_item.target_slot,
                grounded=llm_item.grounded,
            ))
        else:
            normalized.append(NormalizedQuestion(
                rank=q.rank,
                raw=q.raw,
                domain=case_domain,
                concept="other",
                target_slot="other",
                grounded=False,
            ))

    return normalized
