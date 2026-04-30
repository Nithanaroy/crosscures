# History-Taking Eval: Tech Design

## Data layer

Existing medalign DuckDB (`data/medalign/medalign.duckdb`) has all OMOP tables loaded: `person` (275 patients), `note` (46K notes with full text), `condition_occurrence`, `drug_exposure`, `measurement`, `procedure_occurrence`, `visit_occurrence`.

Add 3 tables from Kapil's Excel (`data/Data sheet Xcures.xlsx`):

```sql
eval_cases (
  case_id           TEXT PRIMARY KEY,   -- e.g. "124938510_C01"
  patient_id        BIGINT,             -- FK to person.person_id
  cutoff_date       DATE,
  case_domain       TEXT,               -- e.g. "gynecology", "cardiology"
  case_name         TEXT,
  note_ids_included BIGINT[],           -- array of note_id FKs
  input_summary     TEXT                -- human-readable, for debugging only
)

history_targets (
  target_id         TEXT PRIMARY KEY,   -- generated: case_id + row index
  case_id           TEXT,               -- FK to eval_cases
  patient_id        BIGINT,
  case_domain       TEXT,
  concept           TEXT,               -- e.g. "iud", "knee_pain"
  target_slot       TEXT,               -- e.g. "bleeding", "redness_warmth"
  patient_answerable TEXT,
  severity          TEXT,               -- low / medium / high
  weight            INTEGER,            -- 1 / 2 / 3
  source_note_ids   BIGINT[],
  rationale         TEXT
)

linked_outcomes (
  outcome_id        TEXT PRIMARY KEY,   -- generated: case_id + row index
  case_id           TEXT,
  patient_id        BIGINT,
  case_domain       TEXT,
  concept           TEXT,
  event_type        TEXT,               -- diagnosis / referral / follow_up / etc.
  severity          TEXT,
  source_note_ids   BIGINT[],
  outcome_detail    TEXT
)
```

No junction tables. Use `unnest(note_ids_included)` to join to `note` when needed.

## Eval pipeline

### Step 1: Assemble model input

For each row in `eval_cases`:

```sql
SELECT note_text
FROM note
WHERE note_id IN (SELECT unnest(note_ids_included) FROM eval_cases WHERE case_id = ?)
ORDER BY note_DATETIME ASC
```

Concatenate notes in chronological order. This is the model's sole input.

### Step 2: Generate questions

Prompt the model:

```
System: You are a physician reviewing a patient chart. Based only on the
clinical notes below, generate follow-up history questions you would ask
this patient at their next visit. Output each question on its own line.
Ask only questions a patient can answer from their own experience.

User: [concatenated notes]
```

Capture raw output as a list of free-text questions.

### Step 3: Normalize questions

For each generated question, use a second LLM call (or batch) to map it to the eval schema:

```
Given this question: "{raw_question}"
And these valid domains/concepts from the case: {list from history_targets}

Output JSON:
{"domain": "...", "concept": "...", "target_slot": "...", "grounded": true/false}
```

`grounded` = whether the question is supported by information in the input notes (not a lucky guess).

The normalized triple `(domain, concept, target_slot)` is the unit of comparison.

### Step 4: Match against gold targets

A generated question matches a `history_target` if:
- `normalized_domain == target.case_domain`
- `normalized_concept == target.concept`
- `normalized_target_slot == target.target_slot`

Matching is set-based: each target can be matched at most once.

### Step 5: Compute scores

Four metrics per case, then averaged across all 12 cases:

```
coverage            = |matched targets| / |all targets|
weighted_coverage   = sum(weight of matched) / sum(weight of all)       <-- primary metric
grounded_precision  = |grounded AND matched| / |total generated|
top_k_coverage      = coverage using only the first K generated questions
```

## Run configuration

| Parameter            | Default             |
|----------------------|---------------------|
| Model                | claude-sonnet-4-6  |
| Prompt mode          | raw_notes           |
| Max output tokens    | 2048                |
| Top-K values         | 5, 10               |
| Normalization model  | claude-haiku-4-5   |

## Output format

Per-case results stored as JSON:

```json
{
  "case_id": "124938510_C01",
  "model": "claude-sonnet-4-6",
  "generated_questions": [
    {"rank": 1, "raw": "Have you had any bleeding?", "domain": "gynecology",
     "concept": "iud", "slot": "bleeding", "grounded": true, "matched_target": "..."}
  ],
  "scores": {
    "coverage": 0.75,
    "weighted_coverage": 0.82,
    "grounded_precision": 0.90,
    "top_5_coverage": 0.625,
    "top_10_coverage": 0.75
  }
}
```

Aggregate summary: table of all 12 cases with per-case and mean scores.

## Implementation order

1. Load Excel into 3 DuckDB tables (Python script, ~50 lines)
2. Input assembler: query notes, concatenate, return text (function)
3. Question generator: prompt model, parse output (function)
4. Normalizer: map raw questions to triples (function)
5. Scorer: match + compute metrics (function)
6. Runner: loop over cases, call 2-5, write results (script)
