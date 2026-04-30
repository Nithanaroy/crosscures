# Offline Evaluation Pipeline

Evaluates LLM-generated follow-up history questions against gold-standard clinical targets. The pipeline generates questions from patient notes, normalizes them to structured triples, and scores them against expert-curated targets.

## Prerequisites

- Python 3.12+ (see `.python-version` at repo root)
- [uv](https://docs.astral.sh/uv/) -- the project uses uv workspaces for dependency management
- A running LLM service: [Ollama](https://ollama.com/) locally, or an OpenAI API key

### Install dependencies

From the repository root:

```bash
uv sync
```

This installs all workspace dependencies including the ones needed by the eval pipeline (`duckdb`, `openpyxl`, `openai` -- declared in `crosscures_v2/offline_eval/pyproject.toml`). All commands below should be run with `uv run` to use the managed environment.

## Data Ingestion

Two data sources must be in place before running evaluations.

### Step 1: Create the MedAlign DuckDB database

The eval pipeline reads clinical notes from a DuckDB database at `data/medalign/medalign.duckdb`. See the [`medalign/README.md`](../../medalign/README.md) for setup instructions on ingesting the raw MedAlign dataset into DuckDB.

### Step 2: Load evaluation test data into DuckDB

The gold-standard evaluation cases are maintained in an Excel file at `data/Data sheet Xcures.xlsx` (curated by Kapil). This file contains three sheets with test case definitions, target questions, and expected outcomes. Ask the team for the latest copy if you don't have it.

Load it into DuckDB (one-time, re-run if the Excel changes):

```bash
cd crosscures_v2
uv run python -m offline_eval.load_eval_data
```

This reads the three sheets and creates the following tables in `medalign.duckdb`:

| Table              | Source Sheet         | Purpose                                        |
| ------------------ | -------------------- | ---------------------------------------------- |
| `eval_cases`       | "input reference"    | Test case definitions (patient, domain, notes)  |
| `history_targets`  | "question list"      | Gold-standard questions to evaluate against     |
| `linked_outcomes`  | "outcomes references"| Downstream clinician outcomes (reference only)  |

On success, the script prints a summary of loaded row counts and cases by domain.

## Running the Pipeline

### With Ollama (default)

Start Ollama, then run:

```bash
uv run python -m offline_eval.runner --provider ollama --model llama3
```

### With OpenAI

```bash
export OPENAI_API_KEY="sk-..."
uv run python -m offline_eval.runner --provider openai --model gpt-4o
```

### Using a separate normalizer model

The generation and normalization steps can use different models/providers:

```bash
uv run python -m offline_eval.runner \
  --provider ollama --model gemma4:e4b \
  --normalizer-provider openai --normalizer-model gpt-4o
```

### Other options

| Flag                     | Default                          | Description                          |
| ------------------------ | -------------------------------- | ------------------------------------ |
| `--provider`             | `ollama`                         | `openai` or `ollama`                 |
| `--model`                | `llama3`                         | Model name for question generation   |
| `--base-url`             | `http://localhost:11434/v1`      | API base URL for generator           |
| `--api-key`              | env `OPENAI_API_KEY`             | API key (OpenAI provider)            |
| `--normalizer-provider`  | same as `--provider`             | Provider for normalization step      |
| `--normalizer-model`     | same as `--model`                | Model for normalization step         |
| `--normalizer-base-url`  | inferred from provider           | API base URL for normalizer          |
| `--normalizer-api-key`   | inferred from provider           | API key for normalizer               |
| `--cases`                | all                              | Space-separated case IDs to run      |
| `--temperature`          | `0.3`                            | LLM temperature                      |
| `--dry-run`              | off                              | Assemble inputs only, skip LLM calls |

## Pipeline Steps

For each case, the runner executes:

1. **Assemble** (`assembler.py`) -- Fetches clinical notes from DuckDB by case ID and concatenates them chronologically.
2. **Generate** (`generator.py`) -- Sends the notes to the LLM with a physician prompt; receives 10-15 ranked follow-up questions.
3. **Normalize** (`normalizer.py`) -- Maps each raw question to a structured `(domain, concept, target_slot)` triple using the normalizer LLM. Also flags whether the question is grounded in the input notes.
4. **Score** (`scorer.py`) -- Matches normalized triples against gold targets. Each target can match at most once (first match by rank wins).

## Output

Results are saved to `offline_eval/results/` as JSON:

```
results/eval_{provider}_{model}_{timestamp}.json
```

Each result file contains:

- **config** -- Provider, model, temperature used
- **aggregate_scores** -- Averages across all cases:
  - `coverage` -- fraction of gold targets matched
  - `weighted_coverage` -- primary metric (targets weighted 1-3 by severity)
  - `grounded_precision` -- fraction of generated questions that are both grounded and matched
  - `top_5_coverage` / `top_10_coverage` -- coverage using only top-N ranked questions
- **case_results** -- Per-case breakdown with generated questions, target match details, and unmatched questions

## Project Structure

```
offline_eval/
  runner.py          -- CLI entry point, orchestrates the pipeline
  assembler.py       -- Retrieves and concatenates clinical notes
  generator.py       -- LLM question generation
  normalizer.py      -- LLM-based question normalization
  scorer.py          -- Triple matching and metric computation
  load_eval_data.py  -- One-time data ingestion from Excel to DuckDB
  config.py          -- Paths, LLMConfig dataclass, defaults
  models.py          -- Pydantic models for pipeline data
  requirements.txt   -- Python dependencies
  results/           -- Output JSON files
```
