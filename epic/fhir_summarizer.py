#!/usr/bin/env python3
"""
FHIR Data Summarizer
====================
Transforms raw FHIR resources into a human-readable longitudinal EHR summary.

This module takes FHIR R4 resources (from Epic or other sources) and creates
structured summaries suitable for:
- Clinical review
- Patient portals
- LLM processing
- Research analytics
"""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional, Dict, Any, List
from enum import Enum
import json


class SummaryFormat(Enum):
    """Output format for the summary."""
    TEXT = "text"
    JSON = "json"
    MARKDOWN = "markdown"


@dataclass
class PatientSummary:
    """Container for a complete patient EHR summary."""
    patient_id: str
    demographics: Dict[str, Any]
    active_conditions: List[Dict[str, Any]]
    resolved_conditions: List[Dict[str, Any]]
    current_medications: List[Dict[str, Any]]
    allergies: List[Dict[str, Any]]
    recent_encounters: List[Dict[str, Any]]
    recent_labs: List[Dict[str, Any]]
    recent_vitals: List[Dict[str, Any]]
    procedures: List[Dict[str, Any]]
    immunizations: List[Dict[str, Any]]
    timeline: List[Dict[str, Any]] = field(default_factory=list)
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())


class FHIRSummarizer:
    """
    Transforms FHIR resources into structured summaries.
    
    Usage:
        summarizer = FHIRSummarizer()
        raw_data = epic_client.get_all_patient_data()
        summary = summarizer.summarize(raw_data)
        print(summary.to_markdown())
    """
    
    def __init__(self, include_timeline: bool = True):
        """
        Initialize the summarizer.
        
        Args:
            include_timeline: Whether to build a chronological timeline
        """
        self.include_timeline = include_timeline
    
    def summarize(self, fhir_data: Dict[str, Any]) -> PatientSummary:
        """
        Create a comprehensive summary from FHIR data.
        
        Args:
            fhir_data: Dictionary with FHIR resources organized by type
                       (output from EpicFHIRClient.get_all_patient_data())
        
        Returns:
            PatientSummary object
        """
        patient = fhir_data.get("patient", {})
        
        # Parse demographics
        demographics = self._parse_demographics(patient)
        
        # Parse conditions
        conditions = fhir_data.get("conditions", [])
        active_conditions = self._parse_conditions(conditions, clinical_status="active")
        resolved_conditions = self._parse_conditions(conditions, clinical_status="resolved")
        
        # Parse medications
        medications = fhir_data.get("medications", [])
        current_medications = self._parse_medications(medications)
        
        # Parse allergies
        allergies = self._parse_allergies(fhir_data.get("allergies", []))
        
        # Parse encounters
        encounters = fhir_data.get("encounters", [])
        recent_encounters = self._parse_encounters(encounters)
        
        # Parse observations (labs and vitals)
        observations = fhir_data.get("observations", [])
        recent_labs = self._parse_observations(observations, category="laboratory")
        recent_vitals = self._parse_observations(observations, category="vital-signs")
        
        # Parse procedures
        procedures = self._parse_procedures(fhir_data.get("procedures", []))
        
        # Parse immunizations
        immunizations = self._parse_immunizations(fhir_data.get("immunizations", []))
        
        summary = PatientSummary(
            patient_id=patient.get("id", "unknown"),
            demographics=demographics,
            active_conditions=active_conditions,
            resolved_conditions=resolved_conditions,
            current_medications=current_medications,
            allergies=allergies,
            recent_encounters=recent_encounters,
            recent_labs=recent_labs,
            recent_vitals=recent_vitals,
            procedures=procedures,
            immunizations=immunizations,
        )
        
        # Build timeline if requested
        if self.include_timeline:
            summary.timeline = self._build_timeline(fhir_data)
        
        return summary
    
    # =========================================================================
    # Parsing Methods
    # =========================================================================
    
    def _parse_demographics(self, patient: Dict[str, Any]) -> Dict[str, Any]:
        """Extract demographic information from Patient resource."""
        if not patient:
            return {}
        
        # Parse name
        names = patient.get("name", [])
        name = "Unknown"
        if names:
            name_obj = names[0]
            given = " ".join(name_obj.get("given", []))
            family = name_obj.get("family", "")
            name = f"{given} {family}".strip()
        
        # Parse birth date and calculate age
        birth_date = patient.get("birthDate")
        age = None
        if birth_date:
            try:
                bd = datetime.strptime(birth_date, "%Y-%m-%d").date()
                today = date.today()
                age = today.year - bd.year - ((today.month, today.day) < (bd.month, bd.day))
            except ValueError:
                pass
        
        # Parse address
        addresses = patient.get("address", [])
        address = None
        if addresses:
            addr = addresses[0]
            parts = addr.get("line", []) + [
                addr.get("city", ""),
                addr.get("state", ""),
                addr.get("postalCode", "")
            ]
            address = ", ".join(p for p in parts if p)
        
        # Parse contact info
        telecoms = patient.get("telecom", [])
        phone = None
        email = None
        for t in telecoms:
            if t.get("system") == "phone" and not phone:
                phone = t.get("value")
            elif t.get("system") == "email" and not email:
                email = t.get("value")
        
        return {
            "name": name,
            "birth_date": birth_date,
            "age": age,
            "gender": patient.get("gender", "unknown"),
            "address": address,
            "phone": phone,
            "email": email,
            "mrn": self._get_identifier(patient, "MR"),
            "language": self._get_language(patient),
        }
    
    def _get_identifier(self, patient: Dict, type_code: str) -> Optional[str]:
        """Get a specific identifier type from patient."""
        for identifier in patient.get("identifier", []):
            id_type = identifier.get("type", {})
            codings = id_type.get("coding", [])
            for coding in codings:
                if coding.get("code") == type_code:
                    return identifier.get("value")
        return None
    
    def _get_language(self, patient: Dict) -> Optional[str]:
        """Get patient's preferred language."""
        communications = patient.get("communication", [])
        for comm in communications:
            if comm.get("preferred"):
                lang = comm.get("language", {})
                return lang.get("text") or self._get_coding_display(lang)
        return None
    
    def _get_coding_display(self, codeable_concept: Dict) -> Optional[str]:
        """Extract display text from a CodeableConcept."""
        if not codeable_concept:
            return None
        
        # Try text first
        if codeable_concept.get("text"):
            return codeable_concept["text"]
        
        # Try codings
        codings = codeable_concept.get("coding", [])
        for coding in codings:
            if coding.get("display"):
                return coding["display"]
        
        return None
    
    def _parse_conditions(
        self, 
        conditions: List[Dict], 
        clinical_status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Parse Condition resources."""
        parsed = []
        
        for condition in conditions:
            status = self._get_coding_display(condition.get("clinicalStatus", {}))
            
            # Filter by status if specified
            if clinical_status and status and status.lower() != clinical_status.lower():
                continue
            
            parsed.append({
                "id": condition.get("id"),
                "name": self._get_coding_display(condition.get("code", {})),
                "clinical_status": status,
                "verification_status": self._get_coding_display(
                    condition.get("verificationStatus", {})
                ),
                "onset_date": self._extract_date(condition, "onset"),
                "recorded_date": condition.get("recordedDate"),
                "category": self._get_coding_display(
                    (condition.get("category", []) or [{}])[0]
                ),
                "severity": self._get_coding_display(condition.get("severity", {})),
                "code": self._get_code(condition.get("code", {})),
            })
        
        # Sort by onset date (most recent first)
        parsed.sort(key=lambda x: x.get("onset_date") or "", reverse=True)
        return parsed
    
    def _parse_medications(self, medications: List[Dict]) -> List[Dict[str, Any]]:
        """Parse MedicationRequest resources."""
        parsed = []
        
        for med in medications:
            status = med.get("status", "")
            
            # Get medication name
            med_codeable = med.get("medicationCodeableConcept", {})
            med_name = self._get_coding_display(med_codeable)
            
            # Parse dosage
            dosage_instructions = []
            for dosage in med.get("dosageInstruction", []):
                dose_text = dosage.get("text", "")
                if dose_text:
                    dosage_instructions.append(dose_text)
                else:
                    # Try to construct from structured data
                    dose_qty = dosage.get("doseAndRate", [{}])[0].get("doseQuantity", {})
                    if dose_qty:
                        dosage_instructions.append(
                            f"{dose_qty.get('value', '')} {dose_qty.get('unit', '')}"
                        )
            
            parsed.append({
                "id": med.get("id"),
                "name": med_name,
                "status": status,
                "authored_on": med.get("authoredOn"),
                "dosage": "; ".join(dosage_instructions) if dosage_instructions else None,
                "requester": self._get_reference_display(med.get("requester", {})),
                "code": self._get_code(med_codeable),
            })
        
        # Filter to active medications and sort
        active = [m for m in parsed if m["status"] in ("active", "completed")]
        active.sort(key=lambda x: x.get("authored_on") or "", reverse=True)
        return active
    
    def _parse_allergies(self, allergies: List[Dict]) -> List[Dict[str, Any]]:
        """Parse AllergyIntolerance resources."""
        parsed = []
        
        for allergy in allergies:
            # Get reactions
            reactions = []
            for reaction in allergy.get("reaction", []):
                manifestations = reaction.get("manifestation", [])
                for m in manifestations:
                    reactions.append(self._get_coding_display(m))
            
            parsed.append({
                "id": allergy.get("id"),
                "substance": self._get_coding_display(allergy.get("code", {})),
                "clinical_status": self._get_coding_display(
                    allergy.get("clinicalStatus", {})
                ),
                "verification_status": self._get_coding_display(
                    allergy.get("verificationStatus", {})
                ),
                "type": allergy.get("type"),
                "category": allergy.get("category", []),
                "criticality": allergy.get("criticality"),
                "reactions": [r for r in reactions if r],
                "onset_date": allergy.get("onsetDateTime"),
                "recorded_date": allergy.get("recordedDate"),
            })
        
        return parsed
    
    def _parse_encounters(self, encounters: List[Dict]) -> List[Dict[str, Any]]:
        """Parse Encounter resources."""
        parsed = []
        
        for enc in encounters:
            # Get period
            period = enc.get("period", {})
            
            # Get reason
            reasons = []
            for reason in enc.get("reasonCode", []):
                reasons.append(self._get_coding_display(reason))
            
            parsed.append({
                "id": enc.get("id"),
                "status": enc.get("status"),
                "class": self._get_coding_display(enc.get("class", {})),
                "type": self._get_coding_display((enc.get("type", []) or [{}])[0]),
                "start_date": period.get("start"),
                "end_date": period.get("end"),
                "reason": "; ".join(r for r in reasons if r),
                "location": self._get_location(enc),
            })
        
        # Sort by start date (most recent first)
        parsed.sort(key=lambda x: x.get("start_date") or "", reverse=True)
        return parsed[:20]  # Return last 20 encounters
    
    def _parse_observations(
        self, 
        observations: List[Dict],
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Parse Observation resources (labs, vitals)."""
        parsed = []
        
        for obs in observations:
            # Check category
            obs_categories = obs.get("category", [])
            cat_codes = []
            for cat in obs_categories:
                for coding in cat.get("coding", []):
                    cat_codes.append(coding.get("code"))
            
            if category and category not in cat_codes:
                continue
            
            # Get value
            value = self._extract_observation_value(obs)
            
            parsed.append({
                "id": obs.get("id"),
                "name": self._get_coding_display(obs.get("code", {})),
                "value": value,
                "unit": self._get_observation_unit(obs),
                "reference_range": self._get_reference_range(obs),
                "status": obs.get("status"),
                "effective_date": obs.get("effectiveDateTime"),
                "category": category,
                "code": self._get_code(obs.get("code", {})),
                "interpretation": self._get_interpretation(obs),
            })
        
        # Sort by date (most recent first)
        parsed.sort(key=lambda x: x.get("effective_date") or "", reverse=True)
        return parsed[:50]  # Return last 50 observations
    
    def _extract_observation_value(self, obs: Dict) -> Any:
        """Extract the value from an Observation."""
        if "valueQuantity" in obs:
            qty = obs["valueQuantity"]
            return qty.get("value")
        elif "valueString" in obs:
            return obs["valueString"]
        elif "valueCodeableConcept" in obs:
            return self._get_coding_display(obs["valueCodeableConcept"])
        elif "valueBoolean" in obs:
            return obs["valueBoolean"]
        elif "valueInteger" in obs:
            return obs["valueInteger"]
        return None
    
    def _get_observation_unit(self, obs: Dict) -> Optional[str]:
        """Get unit from observation value."""
        if "valueQuantity" in obs:
            return obs["valueQuantity"].get("unit")
        return None
    
    def _get_reference_range(self, obs: Dict) -> Optional[str]:
        """Get reference range from observation."""
        ranges = obs.get("referenceRange", [])
        if ranges:
            r = ranges[0]
            low = r.get("low", {}).get("value")
            high = r.get("high", {}).get("value")
            if low is not None and high is not None:
                return f"{low}-{high}"
            elif low is not None:
                return f">= {low}"
            elif high is not None:
                return f"<= {high}"
        return None
    
    def _get_interpretation(self, obs: Dict) -> Optional[str]:
        """Get interpretation of observation (high, low, normal, etc.)."""
        interps = obs.get("interpretation", [])
        if interps:
            return self._get_coding_display(interps[0])
        return None
    
    def _parse_procedures(self, procedures: List[Dict]) -> List[Dict[str, Any]]:
        """Parse Procedure resources."""
        parsed = []
        
        for proc in procedures:
            parsed.append({
                "id": proc.get("id"),
                "name": self._get_coding_display(proc.get("code", {})),
                "status": proc.get("status"),
                "performed_date": self._extract_date(proc, "performed"),
                "category": self._get_coding_display(proc.get("category", {})),
                "code": self._get_code(proc.get("code", {})),
            })
        
        parsed.sort(key=lambda x: x.get("performed_date") or "", reverse=True)
        return parsed
    
    def _parse_immunizations(self, immunizations: List[Dict]) -> List[Dict[str, Any]]:
        """Parse Immunization resources."""
        parsed = []
        
        for imm in immunizations:
            parsed.append({
                "id": imm.get("id"),
                "vaccine": self._get_coding_display(imm.get("vaccineCode", {})),
                "status": imm.get("status"),
                "occurrence_date": imm.get("occurrenceDateTime"),
                "lot_number": imm.get("lotNumber"),
                "site": self._get_coding_display(imm.get("site", {})),
            })
        
        parsed.sort(key=lambda x: x.get("occurrence_date") or "", reverse=True)
        return parsed
    
    def _extract_date(self, resource: Dict, prefix: str) -> Optional[str]:
        """Extract date from various FHIR date fields."""
        # Try DateTime first
        if f"{prefix}DateTime" in resource:
            return resource[f"{prefix}DateTime"]
        # Try Period
        if f"{prefix}Period" in resource:
            return resource[f"{prefix}Period"].get("start")
        # Try Age (convert to approximate date)
        if f"{prefix}Age" in resource:
            return None  # Would need patient birth date to calculate
        return None
    
    def _get_code(self, codeable_concept: Dict) -> Optional[str]:
        """Get the primary code from a CodeableConcept."""
        codings = codeable_concept.get("coding", [])
        if codings:
            coding = codings[0]
            system = coding.get("system", "")
            code = coding.get("code", "")
            # Simplify common systems
            if "snomed" in system.lower():
                return f"SNOMED:{code}"
            elif "loinc" in system.lower():
                return f"LOINC:{code}"
            elif "rxnorm" in system.lower():
                return f"RxNorm:{code}"
            elif "icd" in system.lower():
                return f"ICD:{code}"
            return code
        return None
    
    def _get_reference_display(self, reference: Dict) -> Optional[str]:
        """Get display text from a Reference."""
        return reference.get("display")
    
    def _get_location(self, encounter: Dict) -> Optional[str]:
        """Get location from encounter."""
        locations = encounter.get("location", [])
        if locations:
            loc = locations[0].get("location", {})
            return loc.get("display")
        return None
    
    # =========================================================================
    # Timeline Building
    # =========================================================================
    
    def _build_timeline(self, fhir_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build a chronological timeline of all events."""
        events = []
        
        # Add encounters
        for enc in fhir_data.get("encounters", []):
            period = enc.get("period", {})
            events.append({
                "date": period.get("start"),
                "type": "encounter",
                "description": self._get_coding_display((enc.get("type", []) or [{}])[0]),
                "details": enc.get("status"),
            })
        
        # Add conditions
        for condition in fhir_data.get("conditions", []):
            events.append({
                "date": condition.get("recordedDate") or self._extract_date(condition, "onset"),
                "type": "condition",
                "description": self._get_coding_display(condition.get("code", {})),
                "details": self._get_coding_display(condition.get("clinicalStatus", {})),
            })
        
        # Add medications
        for med in fhir_data.get("medications", []):
            events.append({
                "date": med.get("authoredOn"),
                "type": "medication",
                "description": self._get_coding_display(med.get("medicationCodeableConcept", {})),
                "details": med.get("status"),
            })
        
        # Add procedures
        for proc in fhir_data.get("procedures", []):
            events.append({
                "date": self._extract_date(proc, "performed"),
                "type": "procedure",
                "description": self._get_coding_display(proc.get("code", {})),
                "details": proc.get("status"),
            })
        
        # Add key observations (labs/vitals)
        for obs in fhir_data.get("observations", []):
            events.append({
                "date": obs.get("effectiveDateTime"),
                "type": "observation",
                "description": self._get_coding_display(obs.get("code", {})),
                "details": f"{self._extract_observation_value(obs)} {self._get_observation_unit(obs) or ''}".strip(),
            })
        
        # Sort by date
        events = [e for e in events if e.get("date")]
        events.sort(key=lambda x: x["date"], reverse=True)
        
        return events[:100]  # Return last 100 events
    
    # =========================================================================
    # Output Formatting
    # =========================================================================
    
    def to_text(self, summary: PatientSummary) -> str:
        """Convert summary to plain text format."""
        lines = []
        demo = summary.demographics
        
        lines.append("=" * 60)
        lines.append("PATIENT EHR SUMMARY")
        lines.append("=" * 60)
        lines.append("")
        
        # Demographics
        lines.append("DEMOGRAPHICS")
        lines.append("-" * 40)
        lines.append(f"Name: {demo.get('name', 'Unknown')}")
        lines.append(f"Age: {demo.get('age', 'Unknown')} ({demo.get('gender', 'Unknown')})")
        lines.append(f"DOB: {demo.get('birth_date', 'Unknown')}")
        lines.append(f"MRN: {demo.get('mrn', 'N/A')}")
        lines.append("")
        
        # Allergies
        lines.append("ALLERGIES")
        lines.append("-" * 40)
        if summary.allergies:
            for a in summary.allergies:
                reactions = ", ".join(a.get("reactions", [])) or "No reactions recorded"
                lines.append(f"• {a.get('substance', 'Unknown')} - {reactions}")
        else:
            lines.append("No known allergies")
        lines.append("")
        
        # Active Conditions
        lines.append("ACTIVE CONDITIONS")
        lines.append("-" * 40)
        if summary.active_conditions:
            for c in summary.active_conditions:
                lines.append(f"• {c.get('name', 'Unknown')} (since {c.get('onset_date', 'unknown')})")
        else:
            lines.append("No active conditions")
        lines.append("")
        
        # Current Medications
        lines.append("CURRENT MEDICATIONS")
        lines.append("-" * 40)
        if summary.current_medications:
            for m in summary.current_medications:
                dosage = f" - {m['dosage']}" if m.get('dosage') else ""
                lines.append(f"• {m.get('name', 'Unknown')}{dosage}")
        else:
            lines.append("No current medications")
        lines.append("")
        
        # Recent Labs
        lines.append("RECENT LABS")
        lines.append("-" * 40)
        if summary.recent_labs:
            for lab in summary.recent_labs[:10]:
                value = lab.get('value', 'N/A')
                unit = lab.get('unit', '')
                ref = f" (ref: {lab['reference_range']})" if lab.get('reference_range') else ""
                lines.append(f"• {lab.get('name', 'Unknown')}: {value} {unit}{ref}")
        else:
            lines.append("No recent labs")
        lines.append("")
        
        # Recent Vitals
        lines.append("RECENT VITALS")
        lines.append("-" * 40)
        if summary.recent_vitals:
            for v in summary.recent_vitals[:5]:
                lines.append(f"• {v.get('name', 'Unknown')}: {v.get('value', 'N/A')} {v.get('unit', '')}")
        else:
            lines.append("No recent vitals")
        lines.append("")
        
        lines.append("=" * 60)
        lines.append(f"Generated: {summary.generated_at}")
        
        return "\n".join(lines)
    
    def to_markdown(self, summary: PatientSummary) -> str:
        """Convert summary to Markdown format."""
        lines = []
        demo = summary.demographics
        
        lines.append("# Patient EHR Summary")
        lines.append("")
        
        # Demographics
        lines.append("## Demographics")
        lines.append(f"- **Name:** {demo.get('name', 'Unknown')}")
        lines.append(f"- **Age:** {demo.get('age', 'Unknown')} ({demo.get('gender', 'Unknown')})")
        lines.append(f"- **DOB:** {demo.get('birth_date', 'Unknown')}")
        lines.append(f"- **MRN:** {demo.get('mrn', 'N/A')}")
        lines.append("")
        
        # Allergies
        lines.append("## Allergies")
        if summary.allergies:
            for a in summary.allergies:
                reactions = ", ".join(a.get("reactions", [])) or "No reactions recorded"
                crit = f" ⚠️ **{a['criticality']}**" if a.get('criticality') == 'high' else ""
                lines.append(f"- **{a.get('substance', 'Unknown')}** - {reactions}{crit}")
        else:
            lines.append("*No known allergies*")
        lines.append("")
        
        # Active Conditions
        lines.append("## Active Conditions")
        if summary.active_conditions:
            lines.append("| Condition | Onset | Code |")
            lines.append("|-----------|-------|------|")
            for c in summary.active_conditions:
                lines.append(f"| {c.get('name', 'Unknown')} | {c.get('onset_date', '-')} | {c.get('code', '-')} |")
        else:
            lines.append("*No active conditions*")
        lines.append("")
        
        # Current Medications
        lines.append("## Current Medications")
        if summary.current_medications:
            lines.append("| Medication | Dosage | Prescribed |")
            lines.append("|------------|--------|------------|")
            for m in summary.current_medications:
                lines.append(f"| {m.get('name', 'Unknown')} | {m.get('dosage', '-')} | {m.get('authored_on', '-')[:10] if m.get('authored_on') else '-'} |")
        else:
            lines.append("*No current medications*")
        lines.append("")
        
        # Recent Labs
        lines.append("## Recent Labs")
        if summary.recent_labs:
            lines.append("| Test | Value | Reference | Date |")
            lines.append("|------|-------|-----------|------|")
            for lab in summary.recent_labs[:15]:
                value = f"{lab.get('value', 'N/A')} {lab.get('unit', '')}".strip()
                ref = lab.get('reference_range', '-')
                date = lab.get('effective_date', '-')[:10] if lab.get('effective_date') else '-'
                lines.append(f"| {lab.get('name', 'Unknown')} | {value} | {ref} | {date} |")
        else:
            lines.append("*No recent labs*")
        lines.append("")
        
        # Recent Vitals
        lines.append("## Recent Vitals")
        if summary.recent_vitals:
            for v in summary.recent_vitals[:5]:
                lines.append(f"- **{v.get('name', 'Unknown')}:** {v.get('value', 'N/A')} {v.get('unit', '')}")
        else:
            lines.append("*No recent vitals*")
        lines.append("")
        
        # Recent Encounters
        lines.append("## Recent Encounters")
        if summary.recent_encounters:
            for enc in summary.recent_encounters[:5]:
                date = enc.get('start_date', 'Unknown')[:10] if enc.get('start_date') else 'Unknown'
                lines.append(f"- **{date}** - {enc.get('type', 'Unknown')} ({enc.get('class', '')})")
                if enc.get('reason'):
                    lines.append(f"  - Reason: {enc['reason']}")
        else:
            lines.append("*No recent encounters*")
        lines.append("")
        
        lines.append("---")
        lines.append(f"*Generated: {summary.generated_at}*")
        
        return "\n".join(lines)
    
    def to_json(self, summary: PatientSummary) -> str:
        """Convert summary to JSON format."""
        return json.dumps({
            "patient_id": summary.patient_id,
            "demographics": summary.demographics,
            "active_conditions": summary.active_conditions,
            "resolved_conditions": summary.resolved_conditions,
            "current_medications": summary.current_medications,
            "allergies": summary.allergies,
            "recent_encounters": summary.recent_encounters,
            "recent_labs": summary.recent_labs,
            "recent_vitals": summary.recent_vitals,
            "procedures": summary.procedures,
            "immunizations": summary.immunizations,
            "timeline": summary.timeline,
            "generated_at": summary.generated_at,
        }, indent=2)


# =============================================================================
# Convenience Functions
# =============================================================================

def summarize_patient_data(fhir_data: Dict[str, Any], format: str = "markdown") -> str:
    """
    One-liner to summarize patient FHIR data.
    
    Args:
        fhir_data: Dictionary with FHIR resources
        format: Output format ("text", "markdown", or "json")
        
    Returns:
        Formatted summary string
    """
    summarizer = FHIRSummarizer()
    summary = summarizer.summarize(fhir_data)
    
    if format == "json":
        return summarizer.to_json(summary)
    elif format == "text":
        return summarizer.to_text(summary)
    else:
        return summarizer.to_markdown(summary)


if __name__ == "__main__":
    # Demo with sample FHIR data
    sample_data = {
        "patient": {
            "id": "example-patient",
            "name": [{"given": ["John"], "family": "Doe"}],
            "birthDate": "1980-05-15",
            "gender": "male",
        },
        "conditions": [
            {
                "id": "cond-1",
                "code": {"coding": [{"display": "Type 2 Diabetes Mellitus"}]},
                "clinicalStatus": {"coding": [{"code": "active", "display": "Active"}]},
                "onsetDateTime": "2015-03-20",
            }
        ],
        "medications": [
            {
                "id": "med-1",
                "medicationCodeableConcept": {"coding": [{"display": "Metformin 500mg"}]},
                "status": "active",
                "dosageInstruction": [{"text": "Take 1 tablet twice daily"}],
                "authoredOn": "2023-01-15",
            }
        ],
        "allergies": [
            {
                "id": "allergy-1",
                "code": {"coding": [{"display": "Penicillin"}]},
                "reaction": [{"manifestation": [{"coding": [{"display": "Rash"}]}]}],
                "criticality": "high",
            }
        ],
        "observations": [],
        "encounters": [],
        "procedures": [],
        "immunizations": [],
    }
    
    print(summarize_patient_data(sample_data, format="markdown"))
