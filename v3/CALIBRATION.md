# Real-Qwen local calibration, 2026-10-09

## Decision

Calibration-only recommendation was to keep v3 as a local draft. On 2026-10-09 the owner approved stopping further tuning and proceeding to essential validation/publication; this does not waive separate submission approval. Reward variation is more promising than v2's nearly uniform perfect training groups, but these probes do not establish an optimizer gradient, learning improvement or an Arena score. The raw-template recovery removed local inference-parser failures, but frequent action-format failures and budget cuts still confound task difficulty. At calibration time no new image or dataset was published and no second submission was made. Publication subsequently proceeds through Linux CI; no second submission is authorized yet.

## Runtime and protocol

- Ollama 0.40.2, qwen3.8:27b, model digest 47951e4a666180bc2aedfc93c169472f2de783696fe196efbf063f5730ecf163.
- Download: 18,174,721,847 bytes. Reported weights: nvfp4, MLX runner, 27.8B. This is not Arena's full-precision inference runtime.
- Untrained model; temperature 1.0; thinking false; no JSON-constrained decoding. Exact JSON action or literal finish true only; invalid replies cause grading of current source.
- Four attempts requested per task/reset group. Completion budget 4,096 includes model tokens and post-reset observations estimated as UTF-8 bytes/3. Context 8,192, per-reply token cap 1,600. These choices and token estimates are a local proxy, not verified equivalence with Arena. No call-rate pacing emulation.
- Hidden checks and reference solutions are never supplied to the model. Rewards are calculated by the same parent-side environment verifier used in correctness testing.
- Inference HTTP errors are ungraded attempts, not failed-repair rewards. The updated harness records their status/body and continues the sweep.

## Initial primary probe, reset seed 5000

Completed rewards, four per group:

| Task | Rewards |
| --- | --- |
| allocation-3 | 0.166667, 0.178161, 0.166667, 1 |
| expression-3 | 0.166667, 1, 1, 0.821839 |
| incident-3 | 0.5, 1, 0.333333, 0.333333 |

All three groups are mixed. Four of 12 episodes earned full reward; eight terminated with invalid actions. Full reward can still occur after an invalid reply when previously written code passes hidden checks. Mean terminal reward 0.555556 is an environment reward, not an Arena score.

Provenance: qwen-calibration.json contains the first four allocation episodes; qwen-calibration-followup.json contains four expression and three incident episodes. The original run aborted on an expression inference HTTP 500 after the allocation group; the follow-up aborted on incident repeat 3. qwen-incident-replacement.json is an explicit replacement for that ungraded incident episode, with initial sampling seed 9080 rather than the normal initial seed 9000. This replacement and inference attrition limit the strength of any group-variance inference.

One separate expression diagnostic episode (qwen-expression-diagnostic.json and full response log) earned 0.655172 and terminated on a truncated invalid reply. It is not included in the primary 12 or the broad sweep.

## Broad sweep, reset seed 5001

qwen-eight-family-calibration.json: 32 requested attempts, 25 graded, seven HTTP 500 inference errors. 13 graded episodes earned full reward; 13 ended on invalid actions, with overlap. Mean reward among graded episodes: 0.745517. Every family showed mixed rewards among its available completed outputs, but six groups have fewer than four rewards and do not constitute complete four-candidate training groups.

| Task | Graded | Full reward | Reward range |
| --- | ---: | ---: | --- |
| ledger-3 | 4 | 2 | 0.333333 to 1 |
| capacity-3 | 2 | 1 | 0.339080 to 1 |
| workflow-3 | 3 | 2 | 0.362069 to 1 |
| incident-3 | 3 | 2 | 0.672414 to 1 |
| sensor-3 | 3 | 1 | 0.333333 to 1 |
| reconcile-3 | 4 | 3 | 0 to 1 |
| allocation-3 | 3 | 2 | 0.655172 to 1 |
| expression-3 | 3 | 0 | 0.609195 to 0.833333 |

Six errors returned EOF; one returned an XML function-closing-tag syntax error. They are observed local API/parser failures, not evidence that an Arena rollout would fail in the same way. Invalid actions included prose instead of JSON, empty content, unknown fields, and length-truncated writes. Do not attribute all reward variance to repair reasoning.

## Raw official-template recovery, reset seed 5001

The documented /api/generate endpoint with raw=true avoids the chat API's tool-output parser. calibrate_raw.py renders the official Qwen tokenizer chat template using enable_thinking=false, no native tools, and the same system/action schema. It preserves the entire generated string, including XML/prose; no JSON grammar, stripping or action extraction is used. Template pinned to official revision 1d4bf0f2ff6012fd82039f2fa52739d0dd7c60c0, SHA256 c3cf9e34abf4f9e36c2d72165aa9c132d3e2a725b6c2586aaa3a8af9d7a81041.

qwen-raw-eight-family-calibration.json: all 32 attempts completed, zero inference errors; 15 full rewards, 12 invalid-action endings and three approximate-budget endings. Mean environment reward 0.706897. Seven of eight four-candidate groups showed mixed rewards; reconciliation was uniformly perfect.

| Task | Four rewards |
| --- | --- |
| ledger-3 | 1, 1, 0.333333, 0.333333 |
| capacity-3 | 1, 0.339080, 1, 1 |
| workflow-3 | 0.362069, 0.643678, 0.362069, 0.885057 |
| incident-3 | 0.672414, 0.672414, 0.333333, 1 |
| sensor-3 | 1, 1, 0.333333, 0.333333 |
| reconcile-3 | 1, 1, 1, 1 |
| allocation-3 | 0, 1, 0.166667, 1 |
| expression-3 | 1, 0.816092, 0.201149, 0.833333 |

Excluding invalid-action terminations leaves 20 episodes and only four families with mixed rewards: workflow, incident, allocation and expression. This exclusion is a diagnostic, not an unbiased replacement scoring rule. Workflow/incident/allocation variation still includes budget-ended episodes. Expression has three normally terminal, valid-format episodes with distinct rewards (1, 0.816092, 0.833333), providing the clearest reasoning-difficulty witness in this one-seed sample. Other families' variation is largely format-driven; reconciliation is probably too easy at this seed. Prioritize these four harder candidates rather than assuming all 24 IDs are useful training tasks.

Raw reproduction (public template fetch, no Hugging Face credential used):

    ../.venv/bin/python -m pip install -r requirements-calibration.txt
    ../.venv/bin/python calibrate_raw.py --tasks ledger-3 capacity-3 workflow-3 incident-3 sensor-3 reconcile-3 allocation-3 expression-3 --seed 5001 --repeats 4 --output qwen-raw-eight-family-calibration.json

Across episode probes: 69 primary/broad/raw graded episodes plus one separate diagnostic; nine runtime-aborted attempts. A separate one-reply raw JSON smoke test is not an environment episode. No attempts were silently scored as zero or silently omitted from the narrative.

## Verification and next gate

100 unit/integration/security/harness tests pass. Environment core source was not changed by this calibration. Previous 1,200 correctness episodes, 2,400 single-defect ablations, 24 live-network IDs and six official SDK contract checks remain applicable. Container build/admission and anonymous public image pull have not been performed for v3.

For stronger learning evidence beyond the owner's authorized publication scope, improve action-format reliability and verify it with the actual full-precision model/template and accurate token accounting if an authorized runtime is available. The local raw adapter has already removed tool-parser interference; it does not remove quantization or sampling differences. Recheck repeated groups at multiple seeds and levels with complete candidate counts. Any paid inference requires owner authorization. Any second Arena submission requires showing its request and obtaining fresh approval. Do not use the daily submission slot merely to discover whether a local transport worked.
