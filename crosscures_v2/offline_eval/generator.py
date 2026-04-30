"""Generate follow-up questions from clinical notes via LLM."""
import json
from openai import OpenAI
from offline_eval.config import LLMConfig, DEFAULT_CONFIG
from offline_eval.models import GeneratedQuestions, RawQuestion, GenerationMeta, UsageInfo


SYSTEM_PROMPT = """\
You are a physician reviewing a patient chart before their next visit.
Based only on the clinical notes below, generate 10-15 follow-up history
questions you would ask this patient, ordered by clinical priority
(most important first). Ask only questions a patient can answer from
their own experience -- not questions requiring lab results, imaging,
or clinical examination."""


def generate_questions(notes_text: str, case_domain: str = None,
                       config: LLMConfig = None) -> tuple[list[RawQuestion], GenerationMeta]:
    """Send notes to LLM and return a list of generated questions.

    Returns tuple of (questions, generation metadata).
    """
    config = config or DEFAULT_CONFIG

    client = OpenAI(base_url=config.base_url, api_key=config.api_key)

    domain_hint = ""
    if case_domain:
        domain_hint = f"\n\nThis patient's primary concern falls under: {case_domain}."

    user_prompt = notes_text + domain_hint

    response = client.chat.completions.create(
        model=config.model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=config.max_tokens,
        temperature=config.temperature,
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "generated_questions",
                "strict": True,
                "schema": GeneratedQuestions.model_json_schema(),
            },
        },
    )

    raw_output = response.choices[0].message.content.strip()
    parsed = GeneratedQuestions.model_validate(json.loads(raw_output))

    questions = [
        RawQuestion(rank=i + 1, raw=q)
        for i, q in enumerate(parsed.questions)
    ]

    meta = GenerationMeta(
        model=config.model,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
        raw_output=raw_output,
        input_chars=len(notes_text),
        usage=UsageInfo(
            prompt_tokens=getattr(response.usage, "prompt_tokens", None),
            completion_tokens=getattr(response.usage, "completion_tokens", None),
        ),
    )
    return questions, meta
