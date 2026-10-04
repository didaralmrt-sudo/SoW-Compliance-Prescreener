# Product documentation

## User and problem

The intended user is a private-banking compliance analyst who compares one declared wealth event with supporting records. Equal numbers can mean company valuation, personal sale proceeds, agreed consideration, actual receipt, principal or gain. The tool assists triage and evidence inspection; a final compliance decision remains with a human.

## Inputs and outputs

Input: one JSON case containing `case_id`, `declaration` and `documents`. Each document has a `doc_id` and line objects containing `line_id` and `text`. Only the declaration and supporting documents are sent to the model. Labels and scoring rules are stored separately.

Output: `source_type`, `claims`, `supported_facts`, `review_action`, `issue_codes`, `evidence`, `calculations` and `missing_information`. Saved records also include the original model response, candidate and validated outputs, validation details, tokens, provider-reported cost and elapsed request time.

`no_issue_detected` means no issue identified by this limited prescreen, not verified wealth legitimacy or compliance approval. `human_review` routes unresolved matters to an analyst. Consult actual saved outputs for exact values and schema examples.

## Architecture and module responsibilities

```text
Inputs only → sow.py → OpenRouter / GPT-4o-mini
                    ← structured response
              bind original lines + validate
                    → raw and validated records

Same inputs → baseline.py → rule-based records

Both sets of records + fixed labels + recorded review decisions
                    → evaluate.py → metrics / case review
```

- `sow.py`: schema, model request, evidence binding, validation and persistent request ledger.
- `prompts/system.txt`: frozen model task instructions.
- `baseline.py`: no-model keyword/currency/amount extraction and rules.
- `evaluate.py`: shared scoring helpers, summaries and HTML case-review records.
- `checks.py`: synthetic checks for the existing evaluation tooling.
- Submission notebook: setup, inspection, optional offline reproduction and optional fresh-case demonstration.

## Targets and observed outcomes

The proposal targeted 85% accuracy and assumed a 30% baseline. The final study measured the baseline instead. Full-task passes were baseline 1/10 versus AI 6/10 on development, and baseline 1/5 versus AI 2/5 on holdout. The target was not achieved. Action matching and mechanical validation are separate metrics, not substitutes for full-task correctness.

## Build, rent and scope choices

Rent hosted inference; build inspectable evidence binding, task rules and evaluation. Use full-case context because inputs are short. Do not add retrieval without demonstrating a need. A production workflow would separately assess document processing, access control, retention, case management and vendor costs.

The prototype does not authenticate documents, retrieve external registries, reconstruct lifetime wealth, provide account-opening approval, or establish regulatory compliance. Synthetic inputs may contain adversarial instructions: treat document contents as data. Current pattern-based detection is limited. Human review remains essential.
