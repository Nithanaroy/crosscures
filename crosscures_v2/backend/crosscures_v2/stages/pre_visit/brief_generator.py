"""Pre-visit brief generator — creates physician briefs 72h before appointment."""
import uuid
import json
from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy.orm import Session

from crosscures_v2.db_models import AppointmentDB, PhysicianBriefDB, SymptomLogDB, HealthRecordDB, WearableSampleDB, PrescriptionDB, UserDB
from crosscures_v2.consent.models import ConsentAction
from crosscures_v2.consent.store import ConsentStore
from crosscures_v2.agent.llm import call_llm, LLMUnavailableError
from crosscures_v2.agent.context import assemble_context
from crosscures_v2.events import bus as event_bus
from crosscures_v2.events.models import EventType, EventSource


BRIEF_SYSTEM_PROMPT = """You are CrossCures, a clinical AI assistant. Generate a concise, structured pre-visit physician brief based on the patient data provided.

A numbered Source Index is included below the patient data. Annotate every clinical claim with its source ref inline, e.g. "HbA1c 8.2% [S3]". Use only refs from the provided index.

Output ONLY valid JSON with this exact structure:
{
  "patient_snapshot": "3-5 bullet points about chronic conditions, active medications, known allergies — annotate each fact with its source ref, e.g. [S1]",
  "symptom_trends": "14-day symptom trajectory with source refs, e.g. '...reported worsening fatigue [S5]'",
  "wearable_highlights": "HRV, sleep, SpO2 anomalies with source refs if available, otherwise null",
  "medication_adherence": "Adherence rate per medication with source refs as reported by patient",
  "patient_concerns": "Verbatim high-priority patient-reported concerns with source refs",
  "suggested_discussion_points": ["Point 1 [S2]", "Point 2 [S4]", "Point 3"],
  "citations": ["S1", "S3", "S5"]
}

The \"citations\" array must list every source ref used anywhere in the brief.

Rules:
- Do NOT make diagnostic conclusions
- Do NOT recommend dose changes
- All claims must be traceable to the provided data
- Use plain clinical English
- If data is missing for a section, say \"No data available for this period\"
"""


def generate_brief(patient_id: str, appointment_id: str, db: Session, force_regenerate: bool = False) -> dict:
    """Generate a pre-visit physician brief."""
    consent_store = ConsentStore(db)
    consent_store.require(patient_id, ConsentAction.PHYSICIAN_BRIEF_SHARING)
    consent_store.require(patient_id, ConsentAction.LLM_INFERENCE)

    # Check for existing brief
    appointment = db.query(AppointmentDB).filter(
        AppointmentDB.id == appointment_id,
        AppointmentDB.patient_id == patient_id,
    ).first()

    existing_brief = None
    if appointment and appointment.brief_id:
        existing_brief = db.query(PhysicianBriefDB).filter(
            PhysicianBriefDB.id == appointment.brief_id,
            PhysicianBriefDB.patient_id == patient_id,
        ).first()
    if not existing_brief:
        existing_brief = db.query(PhysicianBriefDB).filter(
            PhysicianBriefDB.appointment_id == appointment_id,
            PhysicianBriefDB.patient_id == patient_id,
        ).order_by(PhysicianBriefDB.generated_at.desc()).first()

    if appointment and appointment.brief_generated and not force_regenerate and existing_brief:
        return _brief_to_dict(existing_brief)

    # Assemble context
    ctx = assemble_context(patient_id, db)

    # Get recent symptom logs
    since_14d = datetime.utcnow() - timedelta(days=14)
    sources, source_index_text = _build_source_catalog(patient_id, db, since_14d)
    symptom_logs = db.query(SymptomLogDB).filter(
        SymptomLogDB.patient_id == patient_id,
        SymptomLogDB.submitted_at >= since_14d,
    ).order_by(SymptomLogDB.session_date.desc()).all()

    symptom_summary = "No check-ins in the last 14 days."
    if symptom_logs:
        log_summaries = []
        for log in symptom_logs:
            responses_text = []
            for resp in (log.responses or []):
                if resp.get("value") is not None:
                    responses_text.append(f"{resp.get('question_id')}: {resp.get('value')}")
            if responses_text:
                log_summaries.append(f"[{log.session_date}] " + "; ".join(responses_text[:4]))
        symptom_summary = "\n".join(log_summaries)

    patient_summary_for_physician = _build_patient_summary_for_physician(patient_id, appointment, symptom_logs, db)

    user_message = f"""Patient context:
{ctx['patient_summary']}

Symptom logs (last 14 days):
{symptom_summary}

Wearable data:
{ctx['wearable_summary']}

Active prescriptions:
{json.dumps(ctx['prescriptions'], indent=2)}

Memory highlights:
{ctx['memory_highlights']}

{source_index_text}

Generate the pre-visit brief as structured JSON."""

    try:
        llm_resp = call_llm(
            system_prompt=BRIEF_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
            patient_id=patient_id,
            purpose="pre_visit_brief",
            db=db,
            max_tokens=2000,
        )

        # Parse the JSON sections
        try:
            sections = json.loads(llm_resp.content)
        except json.JSONDecodeError:
            # Try to extract JSON from the response
            import re
            match = re.search(r'\{.*\}', llm_resp.content, re.DOTALL)
            sections = json.loads(match.group()) if match else {}
    except LLMUnavailableError as e:
        print(f"[WARN] Brief generation LLM call failed: {e.cause}")
        sections = {
            "patient_snapshot": ctx["patient_summary"],
            "symptom_trends": symptom_summary,
            "wearable_highlights": ctx["wearable_summary"],
            "medication_adherence": "Unable to generate — LLM unavailable",
            "patient_concerns": "Unable to generate — LLM unavailable",
            "suggested_discussion_points": ["Review recent symptom logs", "Check medication adherence"],
        }

    # Normalize multi-ref brackets like [S1, S2] → [S1][S2] in all section text
    # so the frontend split regex and the auto-scan both see only single-ref tokens.
    if isinstance(sections, dict):
        sections = _normalize_sections(sections)

    # Extract and resolve citations from LLM response
    raw_citation_refs = sections.pop("citations", []) if isinstance(sections, dict) else []
    ref_index = {s["ref"]: s for s in sources}
    if isinstance(raw_citation_refs, list):
        resolved_citations = [ref_index[r] for r in raw_citation_refs if r in ref_index]
    else:
        resolved_citations = []

    # Auto-collect any [Sn] refs inlined in text but omitted from the LLM citations array
    import re as _re
    seen_refs = {c["ref"] for c in resolved_citations}
    for section_value in (sections.values() if isinstance(sections, dict) else []):
        texts = section_value if isinstance(section_value, list) else [section_value]
        for text in texts:
            if not isinstance(text, str):
                continue
            for ref in _re.findall(r'\[S(\d+)\]', text):
                key = f"S{ref}"
                if key not in seen_refs and key in ref_index:
                    resolved_citations.append(ref_index[key])
                    seen_refs.add(key)

    sections = {
        "patient_summary": patient_summary_for_physician,
        **(sections or {}),
    }

    if force_regenerate and existing_brief:
        brief = existing_brief
        brief.generated_at = datetime.utcnow()
        brief.sections = sections
        brief.citations = resolved_citations
        brief.delivery_status = "queued"
        brief.delivered_at = None
        brief.acknowledged_at = None
    else:
        brief = PhysicianBriefDB(
            id=str(uuid.uuid4()),
            patient_id=patient_id,
            appointment_id=appointment_id,
            generated_at=datetime.utcnow(),
            sections=sections,
            citations=resolved_citations,
            delivery_status="queued",
        )
        db.add(brief)

    if appointment:
        appointment.brief_generated = True
        appointment.brief_id = brief.id

    db.commit()
    db.refresh(brief)

    event_bus.emit(
        event_bus.make_event(
            EventType.BRIEF_GENERATED,
            patient_id=patient_id,
            source=EventSource.AGENT,
            payload={"brief_id": brief.id, "appointment_id": appointment_id},
        ),
        db,
    )

    return _brief_to_dict(brief)


def _brief_to_dict(brief: PhysicianBriefDB) -> dict:
    return {
        "brief_id": brief.id,
        "patient_id": brief.patient_id,
        "appointment_id": brief.appointment_id,
        "generated_at": brief.generated_at.isoformat(),
        "sections": brief.sections,
        "citations": brief.citations or [],
        "delivery_status": brief.delivery_status,
    }


def _normalize_inline_refs(text: str) -> str:
    """Expand multi-ref brackets into sequential single-ref tokens.

    Examples:
      '[S1, S2]'   -> '[S1][S2]'
      '[S3,S4,S5]' -> '[S3][S4][S5]'
      '[S1]'       -> '[S1]'  (unchanged)
    """
    import re
    def _expand(m: re.Match) -> str:
        parts = re.split(r'[,;]\s*', m.group(1))
        valid = [p.strip() for p in parts if re.fullmatch(r'S\d+', p.strip())]
        return ''.join(f'[{p}]' for p in valid) if valid else m.group(0)
    # Match brackets containing one or more comma/semicolon-separated Sn refs
    return re.sub(r'\[(S\d+(?:[,;]\s*S\d+)+)\]', _expand, text)


def _normalize_sections(sections: dict) -> dict:
    """Apply _normalize_inline_refs to every string value in the sections dict."""
    out = {}
    for k, v in sections.items():
        if isinstance(v, list):
            out[k] = [_normalize_inline_refs(item) if isinstance(item, str) else item for item in v]
        elif isinstance(v, str):
            out[k] = _normalize_inline_refs(v)
        else:
            out[k] = v
    return out


def _build_source_catalog(patient_id: str, db: Session, since_14d: datetime) -> tuple:
    """Build a numbered source catalog for citation anchoring in the LLM prompt.

    Returns (sources_list, source_index_text). Each entry in sources_list is a dict
    with a 'ref' key (e.g. 'S1') and full provenance metadata. The source_index_text
    is formatted for inclusion in the LLM user message.
    """
    sources = []
    idx = 1

    # Health records — conditions, notes, labs, meds (up to 30 most recent)
    records = db.query(HealthRecordDB).filter(
        HealthRecordDB.patient_id == patient_id,
    ).order_by(HealthRecordDB.occurred_at.desc(), HealthRecordDB.created_at.desc()).limit(30).all()

    for r in records:
        ref = f"S{idx}"
        if r.occurred_at:
            date_str = r.occurred_at.strftime("%Y-%m-%d")
        elif r.created_at:
            date_str = r.created_at.strftime("%Y-%m-%d")
        else:
            date_str = "unknown date"
        source_label = r.source_name or "EHR"
        sources.append({
            "ref": ref,
            "type": "health_record",
            "resource_type": r.resource_type,
            "record_id": r.id,
            "source_name": r.source_name,
            "date": date_str,
            "label": f"{r.display_text} [{r.resource_type} — {source_label}, {date_str}]",
        })
        idx += 1

    # Active prescriptions
    prescriptions = db.query(PrescriptionDB).filter(
        PrescriptionDB.patient_id == patient_id,
    ).all()
    for p in prescriptions:
        ref = f"S{idx}"
        prescriber = p.prescribing_physician or "unknown prescriber"
        sources.append({
            "ref": ref,
            "type": "prescription",
            "prescription_id": p.id,
            "medication_name": p.medication_name,
            "prescribing_physician": p.prescribing_physician,
            "date": str(p.start_date),
            "label": f"Rx: {p.medication_name} {p.dose} {p.frequency} — prescribed by {prescriber} on {p.start_date}",
        })
        idx += 1

    # Symptom check-in logs (last 14 days)
    symptom_logs = db.query(SymptomLogDB).filter(
        SymptomLogDB.patient_id == patient_id,
        SymptomLogDB.submitted_at >= since_14d,
    ).order_by(SymptomLogDB.session_date.desc()).all()
    for log in symptom_logs:
        ref = f"S{idx}"
        sources.append({
            "ref": ref,
            "type": "symptom_log",
            "log_id": log.id,
            "date": str(log.session_date),
            "label": f"Patient symptom check-in on {log.session_date} (CrossCures app)",
        })
        idx += 1

    # Wearable data — one citation entry per metric type
    wearable_samples = db.query(WearableSampleDB).filter(
        WearableSampleDB.patient_id == patient_id,
        WearableSampleDB.start_date >= since_14d,
    ).order_by(WearableSampleDB.start_date.desc()).all()
    wearable_by_type: dict = {}
    for s in wearable_samples:
        wearable_by_type.setdefault(s.quantity_type, []).append(s)
    for qt, samples in wearable_by_type.items():
        ref = f"S{idx}"
        earliest = min(s.start_date for s in samples)
        latest = max(s.start_date for s in samples)
        device = samples[0].source_name or "wearable device"
        sources.append({
            "ref": ref,
            "type": "wearable",
            "quantity_type": qt,
            "source_name": device,
            "date_range": f"{earliest.strftime('%Y-%m-%d')} to {latest.strftime('%Y-%m-%d')}",
            "sample_count": len(samples),
            "label": (
                f"Wearable {qt} — {device}, "
                f"{earliest.strftime('%Y-%m-%d')} to {latest.strftime('%Y-%m-%d')} "
                f"({len(samples)} samples)"
            ),
        })
        idx += 1

    if not sources:
        return [], "No sources available."

    lines = ["Source Index (annotate each claim with its source ref, e.g. [S1]):"]
    for s in sources:
        lines.append(f"  [{s['ref']}] {s['label']}")

    return sources, "\n".join(lines)


def _build_patient_summary_for_physician(
    patient_id: str,
    appointment: Optional[AppointmentDB],
    symptom_logs: List[SymptomLogDB],
    db: Session,
) -> str:
    """Create a concise physician-facing summary from structured records and recent check-ins."""
    profile = db.query(UserDB).filter(UserDB.id == patient_id).first()

    prescriptions = db.query(PrescriptionDB).filter(
        PrescriptionDB.patient_id == patient_id,
    ).order_by(PrescriptionDB.created_at.desc()).limit(3).all()

    records = db.query(HealthRecordDB).filter(
        HealthRecordDB.patient_id == patient_id,
    ).order_by(HealthRecordDB.occurred_at.desc(), HealthRecordDB.created_at.desc()).limit(3).all()

    latest_symptom_items = []
    if symptom_logs:
        latest = symptom_logs[0]
        for resp in (latest.responses or []):
            value = resp.get("value")
            if value in (None, "", []):
                continue
            qid = resp.get("question_id", "symptom")
            latest_symptom_items.append(f"{qid}: {value}")
            if len(latest_symptom_items) >= 3:
                break

    age_text = "Unknown age"
    if profile and profile.date_of_birth:
        today = datetime.utcnow().date()
        age = today.year - profile.date_of_birth.year - (
            (today.month, today.day) < (profile.date_of_birth.month, profile.date_of_birth.day)
        )
        age_text = f"{age} years"

    header_name = profile.full_name if profile and profile.full_name else "Patient"
    appt_reason = appointment.reason if appointment and appointment.reason else "No reason documented"
    appt_date = appointment.appointment_date.strftime("%Y-%m-%d") if appointment else "Unknown date"

    meds_text = ", ".join([f"{p.medication_name} ({p.dose}, {p.frequency})" for p in prescriptions])
    if not meds_text:
        meds_text = "No active prescriptions on file"

    records_text = "; ".join([r.display_text for r in records if r.display_text])
    if not records_text:
        records_text = "No recent health records available"

    symptoms_text = "; ".join(latest_symptom_items) if latest_symptom_items else "No recent symptom details captured"

    return (
        f"{header_name} ({age_text}). "
        f"Upcoming visit on {appt_date} for: {appt_reason}. "
        f"Recent symptom report: {symptoms_text}. "
        f"Current medications: {meds_text}. "
        f"Recent record highlights: {records_text}."
    )
