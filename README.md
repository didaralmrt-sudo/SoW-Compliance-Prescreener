# Source-of-Wealth Compliance Prescreener

PE6201 end-of-course project — Didaer Ailimulati, 4 October 2026.

An analyst-support prototype that compares a synthetic wealth declaration with supporting documents and returns structured claims, document facts, evidence references, issues and a review action. It uses GPT-4o-mini through OpenRouter, deterministic evidence binding and mechanical validation. A non-AI keyword and money-extraction baseline is evaluated on the same cases.

Start here: the submitted experiments are already saved. No API key or model call is needed to inspect the results. This is a coursework prototype, not a compliance approval system.
Final results

| Metric | Development baseline | Development AI | Holdout baseline | Holdout AI |
|---|---:|---:|---:|---:|
| Cases | 10 | 10 | 5 | 5 |
| Review-action matches | 8/10 | 9/10 | 3/5 | 5/5 |
| Source-type matches | 8/10 | 9/10 | 4/5 | 4/5 |
| Issue-set matches | 6/10 | 9/10 | 1/5 | 2/5 |
| Full-task passes | 1/10 | 6/10 | 1/5 | 2/5 |

Full-task results use fixed-rubric, assistant-assisted case reviews recorded in `manual_decisions.json`; they are not independent expert judgments. Correct referral alone is not full-task success. The original 85% target was not achieved. See [evaluation protocol and limitations](docs/EVALUATION.md).

The 15 selected AI responses cost **USD 0.0060306** in total (development: 0.0037278; holdout: 0.0023028), averaging USD 0.00040204 per case. Mean recorded request latency was 3.40 seconds for development and 4.26 seconds for holdout. These are historical response costs, excluding earlier debugging, engineering, infrastructure and analyst time. Baseline API cost was zero; CPU cost was not estimated.

 Use in Google Colab — no local Python installation

1. Download this repository as a ZIP from GitHub (Code → Download ZIP), or use the supplied `SoW_GitHub_Submission.zip`.
2. Download `notebooks/SoW_Submission_Colab.ipynb` from this repository and upload it using Colab → File → Upload notebook.
3. Run notebook steps 1–3. Upload the repository ZIP when prompted. These steps unpack the project, verify frozen-file hashes and display the saved reports and one example. They do not call an API.
4. Optional step 4 rebuilds baseline outputs and evaluation reports from saved AI responses into a **separate** `reproduction/` folder. It makes no model calls. Leave its checkbox off for inspection only.
5. Optional step 5 demonstrates one fresh synthetic case. It is off by default and requires an explicit checkbox and a privately entered OpenRouter API key. It may cost money. It does not change the submitted results.

The notebook is a new submission wrapper around the frozen files, not the notebook that originally generated the experiments. It uses readable code cells and no embedded encoded project payload. Core project modules use Python's standard library; Colab supplies the notebook display/upload utilities. During packaging, only static syntax, JSON, path and hash checks were performed; this wrapper has not been executed end to end in Colab.

 Repository map

```text
.
├── README.md                         # English entry point
├── sow.py                            # Frozen v4.1 AI pipeline and validation
├── baseline.py                       # Frozen non-AI keyword/money rules
├── evaluate.py                       # Shared evaluator and report generation
├── checks.py                         # Existing network-blocked evaluation checks
├── prompts/system.txt                # Actual frozen inference prompt
├── data/                             # Inputs only: 10 dev + 5 holdout cases
├── labels/                           # Fixed answers; never sent to the model
├── saved_dev_ai/                      # Original development AI responses
├── results/                          # Baselines and original holdout AI responses
├── reports/                          # Final metrics and case-review HTML
├── manual_decisions.json             # Final recorded PASS/FAIL decisions
├── freeze_manifest.json              # Original frozen-file SHA-256 hashes
├── expected_manifest.json            # Original expected artifact hashes
├── request_cache/                    # Preserved historical response ledger
├── holdout_run_state.json            # Original holdout run marker
├── notebooks/SoW_Submission_Colab.ipynb
└── docs/                             # Product, data, evaluation and report
```

Keep the source modules, `prompts/`, `data/` and `labels/` in these locations: moving them would break relative-path assumptions and frozen-manifest verification. Historical files such as `manual_decisions.previous.json` and `docs/archive/README_before_submission.md` are retained for provenance; the current README and final decisions take precedence for submission status.

 How the system works

```text
One declaration + supporting text, with document/line IDs
        ↓
GPT-4o-mini → structured claims, facts, references, issues, action
        ↓
Original source text attached by Python → mechanical checks
        ↓
Saved raw/validated output + errors + usage + latency
        ↓
Analyst review; separate fixed-label evaluation
```

Each short case fits directly in the prompt. There is no vector store, fine-tuning, autonomous agent or separate web front end. Evidence quotes attached by code must not be reported as independently generated citation accuracy. Unknown information is retained as unresolved; validation failures trigger review, but semantic errors can still pass mechanical checks.

 Documentation

- [Product: persona, input/output, architecture and boundaries](docs/PRODUCT.md)
- [Data: provenance, splits and missing generation records](docs/DATA.md)
- [Evaluation: rubric, failures, costs and reproduction](docs/EVALUATION.md)
- [English final report](docs/FINAL_REPORT.md)
- [Editable Word report](docs/PE6201_Final_Report_Didaer_Ailimulati.docx)
- [Vendor sources and build-versus-buy notes](docs/Comparator_sources_and_build_buy.md)
- [Packaging verification](docs/PACKAGING_CHECKS.json)

 Reproducibility and limitations

The frozen candidate was evaluated on a small synthetic holdout; it is not a blind third-party benchmark. The dataset had been inspected during preparation. No inference changes were made in this submission package. Fresh model responses can vary and must not replace the historical final evidence.

Known failures include ownership allocation, financial amount basis, cross-currency subtraction, incomplete issue codes and over-strict validation. The holdout numeric-coverage helper does not recognise some label aliases; its flags are not proof of required numeric coverage. Direct case review is necessary. See the evaluation document before interpreting scores.

Keep API keys out of source files, notebook outputs and Git commits. The optional demo prompts privately for the key. Preserve the cache and run markers when resuming an experiment: a clean runtime does not remember earlier calls. No license grant or production-use claim is supplied with this coursework submission.
