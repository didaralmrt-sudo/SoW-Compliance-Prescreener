# SoW baseline + fixed evaluation

## How to run
Upload SoW_Baseline_Evaluation.ipynb to Colab. It embeds this project; no Python installation or separate upload is needed. Run the free setup/check/development sections first. The 10 v4.1 development outputs are preserved exactly and reused without API calls. Only the explicit holdout switch can call the model, at most five new requests in the initial run.

## Frozen candidate
AI code and prompt are byte-for-byte from the uploaded v4.1 development run. No inference fixes, case-specific answer overrides or best-of-many selection are applied. The baseline is a fixed, generic keyword/currency regex implementation. It uses the same input JSON as AI, never reads labels, and does not call an API. Its actual score is unknown until execution; no 30% baseline is assumed.

Baseline source classification uses text keywords; declaration amount selection keeps the last currency amount per category/currency. Supporting amounts are regex-extracted, exact duplicates removed, and coarse keyword bases compared. Explicit nonpayment/missing evidence/instruction patterns trigger review. It cannot reliably resolve entities, periods, negation, personal-vs-aggregate ownership, or multiple independent sources of the same type. It produces no ownership arithmetic. These limitations are declared, not hidden by excluding difficult cases.

## Same scoring criteria for both systems
Development and holdout use their existing frozen label files. Scalar source type/action and required/allowed issue sets are automatically compared. Quote/source references receive the same audit. Required amount/currency coverage and calculation-result presence are necessary checks, not proof of semantic alignment. Candidate array order and label wording are not used for numeric matching.

Full task assessment must also check amount basis, person/transaction, time period, status, arithmetic relationship, evidence semantics, missing information, acceptable variations, and must_not rules. All are shown in manual_review.html with input and candidate output. Record PASS/FAIL plus reason in manual_decisions.json for every case and both systems. A failed/error/missing result remains in the denominator. Full-task accuracy is withheld until every human decision in that split/system is complete. A manual PASS conflicting with an automatic necessary check is rejected for inspection, not silently accepted. Correct routing to human review is never treated as full task success.

Human ground-truth verification in the original files remains pending. Review the labels before accepting final scores; correct only documented label mistakes, never change a label to fit a model output. If a frozen label must change, version it and rescore both systems; preserve original results and explain why.

## Holdout protocol
Manifest records SHA-256 of inference, prompt, baseline, evaluator, inputs, labels and model configuration before any holdout request. Use the holdout once after accepting the frozen candidate. No tuning on its results, no automatic repairs or alternative models. Reports remain separate (10 development / 5 holdout); optionally provide pooled counts but never replace the split results with a pooled headline. The holdout is synthetic, small, and not an unbiased estimate of production accuracy.

This test set was previously inspected/corrected during dataset preparation. Call it a held-out synthetic evaluation set not used for inference tuning; do not claim a third-party blind benchmark. Actual generator identity and prompts must be documented from user records, not guessed.

## Cost and reproducibility
Baseline API cost/tokens are zero (CPU cost not estimated). AI costs/latency come from saved provider responses. Development figures are historical costs, not new spending in this notebook. Deduplicate responses/cached trials; do not add overlapping directory totals. Missing cost is unavailable, not zero. All failures are retained. Preserve report, data, source, prompt, manifest and raw results in the downloadable ZIP. Cache and started-run markers are lost if the Colab runtime is reset; restore the whole project before attempting to continue.

## Delivery status
Only static syntax/package checks were performed while authoring. Neither baseline, evaluation tests nor model inference was executed on the user's behalf. Colab contains nine network-blocked checks before any paid step. No API credentials are embedded. Interface references are unchanged from v4.1.
