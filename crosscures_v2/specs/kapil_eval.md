Core idea

For each case, we define a timepoint in the longitudinal chart and restrict the model to seeing only the notes available up to that cutoff. The model then generates follow-up questions it would ask the patient. We compare those generated questions against a gold-standard set of history targets that represent things a patient could realistically answer.

Those history targets are linked to later downstream clinician-level outcomes, which tell us why those questions mattered.

So the evaluation question is:

Given only the early chart, did the model ask grounded, patient-answerable questions that cover the clinically important information later shown to be relevant?

Dataset structure

The dataset has three main tables.

1. input_cases

This defines what the model is allowed to see.

Each row is one evaluation case.

Fields:

case_id
patient_id
cutoff_date
note_ids_included
case_domain
case_name
input_summary_for_humans

Important:

input_summary_for_humans is only for reviewers and debugging.
It is not the literal model input unless we explicitly choose to test a summary-based setup.
The actual model input should be the raw note text from note_ids_included, concatenated in chronological order.
2. history_targets

This is the gold-standard label set for the history-taking agent.

Each row is one patient-answerable target that the model ideally should cover.

Fields:

case_id
patient_id
case_domain
concept
target_slot
patient_answerable
severity
weight
source_note_ids
rationale

Examples:

gynecology / iud / bleeding
musculoskeletal / knee_pain / redness_warmth
cardiology / coronary_artery_disease_risk / chest_pain
psychiatry / depression / suicidality

The important design choice is that a target is expressed as:
domain + concept + target_slot

That avoids ambiguous flat tags like just “pain” or “bleeding.”

3. linked_outcomes

These are downstream clinician-level anchors.

They are not the primary scoring target for the history-taking agent, but they justify why the history targets matter and help determine severity/weight.

Fields:

case_id
patient_id
case_domain
concept
event_type
severity
source_note_ids
outcome_detail

Examples:

cellulitis
prepatellar_bursitis
bupropion_therapy
coronary_calcification
macular_telangiectasia
Why we split history targets from linked outcomes

A patient can answer:

“Have you had any bleeding?”
“Can you feel the IUD strings?”
“Does the knee feel warm or red?”
“Do you get chest pain when walking uphill?”
“Have you ever fainted or almost fainted?”
“Is the vision blurry in one eye or both?”

A patient cannot answer:

“Do you have prepatellar bursitis?”
“Do you have wall motion abnormalities?”
“Do you have macular telangiectasia?”
“Do you have a coronary calcium score over 1000?”

So if we score a history-taking agent directly on clinician diagnoses, the evaluation is conceptually wrong. The model should instead be scored on whether it asks the right history questions, and those history questions are linked to later diagnoses or workup results.

Expected model workflow

For each case_id:

Retrieve the raw notes listed in note_ids_included
Concatenate them in chronological order
Prompt the model with something like:
“Based only on the notes below, what follow-up history questions would you ask the patient?”
Capture the generated questions
Normalize each generated question into:
case_domain
concept
target_slot

Example:

“Any warmth or redness of the knee?”
becomes musculoskeletal / knee_pain / redness_warmth
“Can you still feel the IUD strings?”
becomes gynecology / iud / strings_palpable
“Any trouble breathing with exertion?”
becomes cardiology / coronary_artery_disease_risk / exertional_dyspnea

This normalization step is essential. We are not comparing free-text wording directly.

How scoring should work

Primary scoring should be against history_targets, not linked_outcomes.

1. Coverage

Did the generated questions cover the gold history targets?

Formula:
coverage = matched_history_targets / total_history_targets

2. Weighted coverage

Each history target has a severity/weight, so not all targets count equally.

Formula:
weighted_coverage = sum(weights of matched history targets) / sum(weights of all history targets)

This should probably be the main metric.

3. Grounded precision

A question should only get credit if it is actually supported by the chart available at the cutoff.

Formula:
grounded_precision = grounded_and_matched_questions / total_generated_questions

This penalizes lucky but unsupported questioning.

4. Top-K coverage

Since real agents cannot ask infinite questions, evaluate performance on the top 5 or top 10 generated questions.

That gives a more realistic view of usefulness.

What counts as a match

We do not require exact wording.

A generated question is counted as covering a gold target if it maps to the same concept + target_slot.

For example, all of these may hit the same target:

“Any redness over the knee?”
“Has the knee felt warm?”
“Any redness or warmth around the kneecap?”

All could map to:
musculoskeletal / knee_pain / redness_warmth

That is the correct LLM evaluation paradigm here: semantic target coverage, not exact sentence matching.