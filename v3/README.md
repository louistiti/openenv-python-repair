# Python Repair Lab v3

Status: implemented, locally verified and probed with real quantized Qwen. The owner approved proceeding to public image/source publication without further tuning; CI verifies the Linux container and anonymous pull before any submission. NOT full-precision calibrated or submitted to Arena. Invalid replies and budget limits still confound the difficulty probe. An official-template raw adapter resolved local tool-parser errors. No score improvement is claimed. The published v2 baseline is preserved at https://github.com/louistiti/openenv-python-repair .

## What changed

24 declared task IDs: eight algorithmic families, three defect counts (one, two or three). Each reset creates five Python modules, seeded constants and examples, and a seeded subset of defects in separate modules. This is eight repair families, not 1,200 unrelated algorithms. The 1,200 replays below are verification episodes, not model rollouts or a training dataset row-count claim.

Families: FIFO multi-account accounting; half-open weighted capacity scheduling; dependency-graph timing and invalidity; deduplicated incident correlation; calibrated sensor aggregation; exact quoted-CSV reconciliation; min-cost capacitated allocation with reassignment; rational expression parsing with unary signs and right-associative powers.

Actions: read, write, test, submit. Initial observation contains the workspace, specification and three public examples. Write replaces one observed module after validation; settings.py is read-only. Test shows only public-example feedback. Submit uses hidden edge/random checks and ends; the 30-action budget also forces terminal grading. Invalid/fenced/non-JSON model replies are handled by the rollout harness by submitting current source, as in the Arena finish-action mechanism.

Terminal reward is the mean of per-behavior-group pass rates, not the pass rate dominated by numerous random cases. Intermediate reward is zero. Exact type-aware recursive comparisons reject bool/int confusion, extra keys, nonfinite values and input mutation. Parent-side verifiers alone own expected outputs and reward. Candidate execution receives input arguments and source, not references, expected answers, verifier groups or rewards.

## Local verification

Pinned OpenEnv SDK: 86a180ede21e044f7929b9a7783ad83aa67d83a3.

- 100 tests passed (environment, WebSocket/HTTP sessions, attack/resource checks, calibration-harness unit tests, and deterministic witnesses for every designed defect).
- 1,200 fresh episodes: 50 reset seeds (1000 through 1049) for every one of the 24 IDs. Every reference scored 1; every starter scored below 1.
- 2,400 single-defect ablations: every remaining defect was detected by hidden checks.
- Real network WebSocket replay of all 24 IDs at seed 1234 passed for reference and starter outcomes.
- Official live OpenEnv runtime validation: 6/6 checks passed. This is contract validation, not Arena admission or model evaluation.
- Real local Qwen probes: 12 completed primary episodes, plus 25 completed episodes out of a requested 32 across all eight families. One extra diagnostic episode was completed separately. A further official-template raw sweep completed 32/32 episodes with zero inference errors, 15 full rewards and seven mixed groups. Nine earlier inference-aborted attempts across runs were not scored as zero. See CALIBRATION.md for limits and replacement accounting. Mock transport tests do not count as model results.

Evidence: replay-results.json, live-replay-results.json, validation-runtime.json and test-results.txt. The raw replay progress is in replay-progress.jsonl.

## Reproduce

From this directory, use the virtual environment one level above. For a fresh checkout or extracted draft, create it first (Python 3.11+ and Git required):

    python3 -m venv ../.venv
    ../.venv/bin/python -m pip install -r requirements-calibration.txt pytest

Then run:

    ../.venv/bin/python -m pytest -q test_environment.py test_calibrate.py test_targeted.py test_calibrate_raw.py
    ../.venv/bin/python replay.py --seeds 50 --start 1000
    ../.venv/bin/uvicorn server:app --host 127.0.0.1 --port 8766
    ../.venv/bin/openenv validate --url http://127.0.0.1:8766 --level runtime --json

Public Linux image: ghcr.io/louistiti/openenv-python-repair:v3. See https://github.com/louistiti/openenv-python-repair/releases/tag/v3 for container validation and anonymous pull reports once CI completes. The workflow tests all 24 IDs over a real WebSocket and checks the exact SDK schema. The proposed submission is submission-v3.json; its image tag is replaced by the verified immutable digest before owner review. Separate explicit owner approval is required before submission.

## Qwen calibration gate

The owner updated Ollama to 0.40.2; qwen3.8:27b was successfully downloaded and tested using its nvfp4/MLX runner. No paid GPU/inference service was used or authorized. The chat API produced mixed rewards but also HTTP 500 EOF/XML tool-parser errors. The official-template raw adapter removed those errors: 32/32 episodes completed; seven groups were mixed. After excluding invalid endings, only workflow, incident, allocation and expression still showed reward variation, with some budget confounding. Frequent invalid JSON/prose still prevents a clean overall task-difficulty claim. See CALIBRATION.md. With Ollama listening locally, reproduce a probe using:

    ollama pull qwen3.8:27b
    ../.venv/bin/python calibrate_raw.py --tasks allocation-3 expression-3 incident-3 workflow-3 --seed 5001 --repeats 4

The harness uses untrained local Qwen, thinking off, one exact JSON action per response, no JSON-constrained decoding and four stochastic rollouts per task/reset group. Inspect full and partial reward spread, invalid-action rate, truncations and elapsed time. If every group is uniformly perfect or uniformly unsuccessful, change difficulty and rerun. Mixed rewards are a candidate GRPO signal, NOT evidence of an optimizer gradient or learning gain.

Local Ollama uses quantized weights, unlike Arena's full-precision model. Runtime/template details are recorded; completion budget counts generated model tokens plus an explicitly approximate observation-token estimate. Context uses Ollama's prompt counter. The per-reply generation cap is 1,600 tokens, with a 4,096-token approximate completion budget and 8,192-token context. Temperature is a configurable local choice, not asserted to match Arena. Inference errors are recorded as ungraded attempts, not reward zero; reports distinguish requested and completed episode counts. Results are a proxy, never an Arena score prediction. For strong evidence, follow this with an authorized full-precision Qwen3.8-27B preflight. Never spend the daily submission slot as a substitute for calibration.

## Limits and originality

This is restricted Python, not a general Python sandbox. Only local modules and tightly exposed csv, io.StringIO and fractions.Fraction imports are available. No dynamic introspection, private attributes, filesystem, network or processes. A fresh isolated interpreter has CPU/wall/file/descriptor caps; Linux adds a 256 MiB address-space cap. Mac address-space limits are not applied. The container is the outer security boundary; more adversarial audit is needed before treating this as a secure arbitrary-code runner.

Templates still exist, and an effective learner could master all eight solution programs. Seeded data and interacting defects reduce simple single-line repetition but do not by themselves prove useful transfer to Arena's eight evaluation domains. Correctness testing and learning testing are separate gates. All code, tasks and oracles are original synthetic work; no personal data, credentials or private evaluation tasks are included. MIT license inherited from repository root.
