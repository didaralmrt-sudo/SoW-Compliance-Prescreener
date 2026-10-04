# Source of Wealth Prescreening with AI

Didaer Ailimulati  |  G2609876A  |  PE6201 Section A

4 October 2026

## Problem and scope

This project evaluates an AI-assisted Source-of-Wealth prescreener for private banking. The prototype produces traceable structured outputs and identifies more required review actions than a keyword baseline, but its incomplete financial reasoning prevents reliable autonomous use. The appropriate outcome is an analyst-support prototype, not a production compliance decision engine.

The intended user is a compliance analyst comparing a client’s wealth declaration with supporting records. Similar numbers can describe different concepts: company valuation, personal proceeds, contractual entitlement, received cash, principal or investment gain. The task is to preserve these distinctions and identify evidence gaps. Final compliance approval, account opening, document authentication and external wealth investigations remain outside scope. No bank deployment or analyst productivity improvement was demonstrated.

The unit of analysis is one declared wealth event with associated evidence. It does not reconstruct a client’s lifetime wealth history, corroborate records with external registries, or infer legitimacy from an internally consistent transaction.

## Design and build versus buy

The final v4.1 pipeline runs in Google Colab and sends each case’s complete declaration and supporting text to GPT-4o-mini through OpenRouter. It requests structured JSON containing claims, document facts, issue codes and a review action. The model selects document and line identifiers; Python attaches the original text, constructs citation paths, checks provenance and numbers, and executes proposed arithmetic. Raw responses, validation errors, usage and latency remain available for inspection.

I retained full-context prompting instead of the proposed vector-store architecture: these short cases fit directly in the prompt, so retrieval would introduce indexing and retrieval failures without a demonstrated benefit. No fine-tuning or autonomous agent was needed. The application owns evidence binding, validation, evaluation and audit records while renting model inference. Contrary to the initial proposal, abstention is triggered by rules and unresolved checks, not a calibrated confidence threshold. Grounding constrains outputs but cannot guarantee correct interpretation.

Unique AI’s KYC–SoW Agent is the closest comparator identified. Its official product page describes narrative generation, source traceability, information-gap handling and human oversight [1]. Its demonstration describes uploading questionnaires and client documents, resolving inconsistencies, and reviewing a drafted wealth narrative [2]. These are vendor descriptions, not independently verified performance results or features tested against my dataset.

The build-versus-buy decision should be made by layer. Renting inference avoids model-training costs. Building the narrow comparison and evaluation layer exposes task-specific failures and keeps assessment criteria inspectable. For production, buying or integrating an established document and case-management platform merits consideration; authentication, retention, access controls and operational support should not be improvised in a notebook. The reviewed vendor pages provide no quoted price, so this study cannot establish that building is cheaper. Vendor procurement would require a separate pilot, security review and total-cost assessment.

## Evaluation and results

The final evaluation used ten synthetic development cases and five synthetic holdout cases. Labels were fixed before these final runs and excluded from model inputs. Both systems received identical inputs and the same scoring requirements. The baseline used keywords, currency/amount extraction and simple matching rules, without model calls. Its performance was measured rather than assuming the proposal’s 30% figure. Development outputs were reused; the frozen candidate then processed the holdout once, with no subsequent inference tuning.

Full-task assessment required correct amounts, currencies, financial meanings, statuses, mandatory calculations, issue codes and supporting evidence. Equivalent wording and fact order were accepted. Assistant-assisted case reviews were recorded in the manual decision file; they were not independent expert adjudication. The holdout numeric-coverage helper did not recognise its label aliases, so its automatic coverage flags were not relied upon: amounts and meanings were checked directly against the fixed labels. Failures were retained in every denominator.

|Metric|Dev baseline|Dev AI|Holdout baseline|Holdout AI|
|---|---|---|---|---|
|Action matches|8/10|9/10|3/5|5/5|
|Issue sets match|6/10|9/10|1/5|2/5|
|Full tasks pass|1/10|6/10|1/5|2/5|

AI routed all five development cases requiring human review correctly, versus four for the baseline; both referred one of five normal cases unnecessarily. On holdout, AI referred all three review-required cases and cleared the sole normal case; both systems handled the empty case correctly. Consequently, 5/5 holdout action matches did not mean 100% full-task accuracy. The recorded full-task results did not meet the original 85% target.

## Costs and business value

Provider-reported costs for the fifteen selected outputs totalled USD 0.0060306: USD 0.0037278 for development and USD 0.0023028 for holdout, averaging USD 0.00040204 per case. Mean recorded request latency was 3.40 and 4.26 seconds respectively. These figures exclude earlier debugging, engineering, hosting and analyst review, and do not measure end-to-end turnaround. Baseline API cost was zero; CPU cost was not estimated. Caching prevented identical saved requests from being charged again while the cache remained available.

A business case remains hypothetical. Assuming 200 monthly cases and a reduction from 20 to 15 analyst minutes per case would yield approximately 16.7 hours of gross monthly time savings. Neither workload nor time reduction was measured. Verification, correcting errors and reviewing unnecessary referrals could eliminate that benefit. A future pilot should measure total analyst time and escaped errors against the existing workflow, rather than infer savings from fast, inexpensive model responses.

## Failure analysis and next steps

The most important failures concerned meaning. DEV06 detected a monetary discrepancy but omitted the required ownership-allocation calculation and risk code. HOLD02 omitted the ownership issue and incorrectly marked contractual consideration completed. HOLD03 classified property proceeds as equity proceeds and subtracted SGD from USD without exchange evidence. Python verified the subtraction numerically but did not establish currency comparability. HOLD04 preserved two conflicting settlement amounts and requested review, yet omitted the mandatory conflicting-documents code despite passing mechanical checks.

The baseline frequently lost context: negated references to other income types affected classification, and matching a declaration to one document could conceal disagreement with another. These weaknesses explain the value of semantic interpretation, without establishing that every AI-generated interpretation is dependable.

Validation also sometimes overstated failure. DEV07 correctly distinguished claimed receipt from pending payment; the fixed rubric permitted omitting a separate zero-receipt fact, although the validator demanded a comparable paid amount. DEV05’s overall evidence supported receipt, but its dedicated status citation was imprecise. These cases require separate measures for routing, task completeness and citation quality; neither a green validation status nor a referral proves correctness.

The dataset is small, synthetic and partly shaped through development, with no real operational validation or repeated-run stability study. Rule-based injection detection covers only listed patterns. Real client deployment would require approved processing arrangements, access controls, retention policies and human sign-off. Future development should validate currency and ownership relationships, improve evaluation-field mapping, and use fresh test cases after any changes. The present results justify further supervised experimentation, not a claim of production readiness.

## References

[1] Unique AI. KYC SoW Agent. Product page. Accessed 4 October 2026. [Official source](https://www.unique.ai/ai-factory/kyc-sow)

[2] Ritter, D. (16 March 2026). Source of Wealth Agent Demo: Reimagining KYC for Wealth Management. Unique AI. Accessed 4 October 2026. [Official source](https://www.unique.ai/en/blog/source-of-wealth-agent-demo-reimagining-kyc-for-wealth-management)

[3] Project evidence. SoW_Evaluation_20261004T075925Z.zip, 4 October 2026. reports/dev and reports/holdout; manual_decisions.json; frozen labels, source code and saved model outputs.
