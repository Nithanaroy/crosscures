"""LLM interface wrapping Anthropic Claude with audit logging."""
import uuid
import time
from datetime import datetime
from typing import List
import anthropic

from app.config import get_settings
from app.db_models import AuditEntryDB
from sqlalchemy.orm import Session

class LLMResponse:
    def __init__(self, content: str, model: str, input_tokens: int, output_tokens: int, latency_ms: int, call_id: str):
        self.content = content
        self.model = model
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.latency_ms = latency_ms
        self.call_id = call_id


class LLMUnavailableError(Exception):
    def __init__(self, cause: str):
        self.cause = cause
        self.retryable = False
        super().__init__(f"LLM unavailable: {cause}")


def get_client() -> anthropic.Anthropic:
    api_key = get_settings().anthropic_api_key
    if not api_key:
        raise LLMUnavailableError(cause="ANTHROPIC_API_KEY is not configured")
    return anthropic.Anthropic(api_key=api_key)


def call_llm(
    system_prompt: str,
    messages: List[dict],
    patient_id: str,
    purpose: str,
    db: Session,
    max_tokens: int = 2048,
    model: str = "claude-sonnet-4-6",
) -> LLMResponse:
    call_id = str(uuid.uuid4())
    client = get_client()

    last_error = None
    delays = [1.0, 2.0, 4.0]

    for attempt, delay in enumerate(delays):
        try:
            start = time.time()
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system_prompt,
                messages=messages,
            )
            latency_ms = int((time.time() - start) * 1000)

            content = response.content[0].text if response.content else ""

            llm_resp = LLMResponse(
                content=content,
                model=response.model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                latency_ms=latency_ms,
                call_id=call_id,
            )

            # Audit log
            _write_audit(db, patient_id, call_id, purpose, system_prompt, messages, llm_resp)
            return llm_resp

        except anthropic.RateLimitError as e:
            last_error = str(e)
            if attempt < len(delays) - 1:
                time.sleep(delay)
        except anthropic.APIConnectionError as e:
            last_error = str(e)
            if attempt < len(delays) - 1:
                time.sleep(delay)
        except Exception as e:
            last_error = str(e)
            break

    raise LLMUnavailableError(cause=last_error or "Unknown error")


def _write_audit(db: Session, patient_id: str, call_id: str, purpose: str, system_prompt: str, messages: list, resp: LLMResponse):
    try:
        entry = AuditEntryDB(
            id=str(uuid.uuid4()),
            patient_id=patient_id,
            event_type="llm_call",
            occurred_at=datetime.utcnow(),
            payload={
                "call_id": call_id,
                "purpose": purpose,
                "model": resp.model,
                "input_tokens": resp.input_tokens,
                "output_tokens": resp.output_tokens,
                "latency_ms": resp.latency_ms,
                "system_prompt_preview": system_prompt[:500],
                "completion_preview": resp.content[:500],
            },
            actor="agent",
            session_id=None,
        )
        db.add(entry)
        db.commit()
    except Exception:
        pass
