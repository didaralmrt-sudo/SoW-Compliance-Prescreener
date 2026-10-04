# Data and provenance

The final inputs are synthetic Chinese-language wealth declarations and supporting documents: 10 development cases (`DEV01`–`DEV10`) and 5 held-out cases (`HOLD01`–`HOLD05`). No real client data is intended in the dataset.

| File | Role |
|---|---|
| `data/dev_inputs.json` | Development declarations and documents only |
| `data/holdout_inputs.json` | Held-out declarations and documents only |
| `labels/dev_ground_truth.json` | Development expected outputs and fixed scoring rules |
| `labels/holdout_ground_truth.json` | Holdout expected outputs and fixed scoring rules |
| `docs/data_history/` | Original/corrected generation artifacts and preparation change notes |

## Provenance and preparation

Development cases came from the user's separate SoW generation conversation. The user confirmed that the five holdout cases were generated with DeepSeek. The specific DeepSeek model/version, exact development generator model and original generation prompts have not been verified in the available package. Do not infer them from the names of applications or recreate prompts and call them historical originals. The operational inference prompt is preserved in `prompts/system.txt`; it is not a dataset-generation prompt.

Dataset preparation included assistant-assisted structural, evidence and arithmetic review and documented corrections before the final inference runs. The final files are identified by the original freeze manifest. The synthetic holdout was inspected during preparation; it is not an independent blind third-party benchmark. Original metadata may still say human verification is pending. Recorded output review decisions do not establish independent expert ground-truth validation.

Use inputs-only files for model calls. Do not upload corrected combined data or ground-truth labels as model input. The model receives a single case's declaration and documents. Development data supported iteration; after candidate freezing, the five held-out cases were evaluated without subsequent inference tuning.

## Coverage and limitations

Cases cover different wealth categories, payment status, missing evidence, conflicting records, ownership/currency distinctions and an empty input. Some development inputs contain adversarial instructions. The holdout has three review-required cases, one normal case and one empty case; it does not cover prompt injection. Some source documents provide arithmetic results explicitly. This small synthetic set cannot establish operational accuracy, complete security coverage or independent complex financial reasoning.

Generation provenance remains a submission documentation gap: add actual generator names, dates and verbatim generation prompts if the original records can be recovered. Preserve missing values honestly. Do not alter final labels to improve model scores.
