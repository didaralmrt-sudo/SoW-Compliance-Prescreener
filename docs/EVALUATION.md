# Evaluation and reproduction

## Authoritative evidence

The final evidence was taken from `SoW_Evaluation_20261004T075925Z.zip`. Original code, prompt, inputs, labels and result files are preserved. `freeze_manifest.json` records the original frozen candidate and file hashes; `manual_decisions.json` holds final decisions. The English README summarises the final results.

Development AI outputs are in `saved_dev_ai/`. Holdout AI outputs are in `results/holdout_ai/20261004T075011236089Z/`. Baseline outputs are in `results/dev_baseline/` and `results/holdout_baseline/`. Final summaries, machine-readable metrics and case-review HTML are under `reports/dev/` and `reports/holdout/`. Do not sum costs across duplicate cache, snapshots and result folders.

## Shared criteria

Both systems receive identical inputs and use the same fixed labels and full-task rubric. Check amounts, currencies, amount basis, person/event, period, status, required calculations, issues, evidence semantics and prohibited inferences. Equivalent wording and reordered facts may be accepted. A required referral is not a full-task pass. Errors and missing outputs remain in denominators.

Action and source type are scalar matches. Issue-set matching requires all required codes and permits only allowed extras. Source-reference and numeric checks are aids, not proof of semantic support. Full-task decisions are assistant-assisted case reviews recorded by the user, not independent expert adjudication. The accompanying Chinese review notes retain detailed reasoning.

## Important implementation limitation

`required_numeric_coverage` recognises paths such as `expected.claims[0].amount`. Some holdout labels instead use aliases with `field_mapping_to_expected`; the frozen helper does not resolve these aliases. A true automatic coverage flag can therefore be uninformative. Holdout amounts and meanings were reviewed directly against fixed labels. Rebuilding the frozen evaluator reproduces this limitation; the submission does not silently fix it or assert that the helper verifies every required field.

## Case findings

- DEV06: AI omitted required ownership allocation and an associated risk code.
- HOLD02: AI missed the ownership issue and assigned an inappropriate completed status to contractual consideration.
- HOLD03: AI misclassified the wealth source and subtracted amounts in different currencies without exchange evidence. Numerical arithmetic validation did not detect the semantic problem.
- HOLD04: AI retained conflicting figures and requested review but omitted a required conflict code, despite passing mechanical validation.
- DEV07: the validator demanded a comparable paid amount, although the fixed rubric allowed omission of a separate zero-receipt fact. Overall reviewed task success can differ from mechanical status.
- DEV05: evidence elsewhere supported receipt, but its dedicated status reference was imprecise; overall task review is not a claim of perfect field-level citations.

The keyword baseline also loses negation, ownership and multi-document context. Both systems need review. See `docs/review_notes/` and the case-review HTML for preserved details.

## Reproduction in Colab

Use the submission notebook. Default cells only read the final package. Optional offline reproduction runs the fixed baseline and evaluator and writes separate `reproduction/` reports; it never calls the model or overwrites `reports/`. Baseline timing can vary. Reproduction retains existing manual decisions rather than performing a new independent review.

The optional fresh-case demo is not another holdout experiment. It calls the unchanged pipeline only after explicit opt-in and keeps outputs in `demo_results/`. Do not use its result to replace a final result or improve the submitted score. A new version tuned on holdout failures would need a fresh evaluation set.

## Cost and reproducibility boundaries

Provider-reported costs for the 15 selected AI outputs total USD 0.0060306. Development outputs are reused historical evidence; reading them incurs no new model charge. Mean recorded request times are 3.40 seconds (development) and 4.26 seconds (holdout), not end-to-end analyst time. Earlier experiments, engineering, infrastructure and analyst review are excluded. Baseline API cost is zero; CPU cost is unmeasured.

Persistent cache and attempt markers limit duplicate calls when restored. They do not survive deletion or a fresh checkout unless retained. Cached results represent earlier responses, not independent replications. No repeated-run reliability or production validation is claimed.
