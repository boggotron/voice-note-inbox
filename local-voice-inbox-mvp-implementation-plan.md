# Public, Local Voice Inbox MVP

## Status

**PLAN stage, awaiting human approval.** This document and the linked GitHub
Issues are the durable design/plan record required by the Agentic Engineering
methodology before any ISOLATE/IMPLEMENT work begins. Tracking: [Epic #11](https://github.com/boggotron/voice-note-inbox/issues/11).
Repository: `boggotron/voice-note-inbox` (already public; this repo is the
target — the "voice-inbox" name used below refers to this project, not a
separate repository).

## Summary

Build a public GitHub repository containing only sanitized infrastructure, workflow definitions, tests, and documentation. The deployed system remains local to the Mac: Superwhisper recordings are mounted read-only into n8n, enriched with OpenAI, and saved to a durable local inbox. No task/calendar/message automation is permitted, except a terminal-failure Gmail alert explicitly approved for this MVP.

Raw transcripts may be sent to the OpenAI API. OpenAI states API data is not used to train models unless opted in; default abuse-monitoring logs may retain content for up to 30 days, with legal and safety exceptions. Use foreground requests with server-side storage disabled where supported, and record this policy in the privacy documentation. [Official OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data)

## Model configuration decision

The enrichment model is **`gpt-5.6-luna`** at the **low** intelligence/reasoning
tier, called through the OpenAI Responses API as a single configurable value
(model name + tier together, per the plan's original "single configuration
value" decision). Design constraints for this call, to be finalized during
implementation of [#5](https://github.com/boggotron/voice-note-inbox/issues/5)
against the current [Responses API reference](https://developers.openai.com/api/reference/resources/responses/methods/create):

- `store: false` — disable server-side response storage where the API
  supports it for this model/tier; if unsupported, document the fallback and
  update the privacy documentation ([#10](https://github.com/boggotron/voice-note-inbox/issues/10)).
- Structured output via a `text.format` JSON Schema bound to the model-output
  contract defined in [#2](https://github.com/boggotron/voice-note-inbox/issues/2).
- Transcript and first-pass note passed as **untrusted input data only** — no
  tool use, no external actions reachable from the model response.
- The `low` intelligence tier is a starting point, not a fixed constraint: the
  evaluation gate in [#7](https://github.com/boggotron/voice-note-inbox/issues/7)
  is the mechanism for deciding whether to raise it.

## Design record (Agentic Engineering DESIGN stage)

- **Goal:** ship a working, safe, evidence-verified MVP as scoped in Summary.
- **Status and ownership:** see epic [#11](https://github.com/boggotron/voice-note-inbox/issues/11).
- **Scope / Non-goals:** see epic [#11](https://github.com/boggotron/voice-note-inbox/issues/11).
- **Architecture impact:** greenfield; establishes the deployment boundary
  (local-only n8n, read-only source mount), the data contracts (schemas in
  [#2](https://github.com/boggotron/voice-note-inbox/issues/2)), and the CI/CD
  gates (PR-time in [#4](https://github.com/boggotron/voice-note-inbox/issues/4),
  release-time in [#9](https://github.com/boggotron/voice-note-inbox/issues/9)).
- **Dependencies:** none external; internal task dependency graph is in the
  Task Breakdown section below.
- **Risks:** see epic [#11](https://github.com/boggotron/voice-note-inbox/issues/11)
  and each sub-issue's Risks section.
- **Security implications:** this is a public repository automating a local,
  privileged capability (reading personal voice recordings and calling an
  external API). The controls are: zero live data/credentials tracked in Git
  (enforced by [#1](https://github.com/boggotron/voice-note-inbox/issues/1) and
  scanned in [#4](https://github.com/boggotron/voice-note-inbox/issues/4)),
  localhost-only/read-only-mount deployment ([#3](https://github.com/boggotron/voice-note-inbox/issues/3)),
  untrusted-data-only model calls with no tool use ([#5](https://github.com/boggotron/voice-note-inbox/issues/5)),
  and a single, narrowly-scoped external side effect ([#6](https://github.com/boggotron/voice-note-inbox/issues/6)).
- **Data implications:** enriched records and diagnostic records are retained
  indefinitely (per Assumptions below); the data model and its versioning are
  defined in [#2](https://github.com/boggotron/voice-note-inbox/issues/2).
- **Migration implications:** N/A — greenfield. [#9](https://github.com/boggotron/voice-note-inbox/issues/9)
  and [#10](https://github.com/boggotron/voice-note-inbox/issues/10) establish
  the rollback anchor and procedure for all future changes.

## Implementation Changes

- Create a public `voice-inbox` repository with:
  - Pinned Docker/n8n image version or digest; no `latest` tag.
  - Sanitized Compose configuration, `.env.example`, workflow JSON export, schemas, synthetic fixtures, test harness, operations runbook, and threat model.
  - A strict `.gitignore` for `.env*` except `.env.example`, `recordings/`, `output/`, `logs/`, `dead-letter/`, n8n database/volume exports, backups, test artefacts, and credential exports. Keep live recordings outside the repository; add CI checks that reject symlinks or copied recording/output data.
- Add repository hygiene:
  - GitHub secret scanning, push protection, Dependabot alerts/security updates, branch protection, required pull requests, and required CI checks.
  - Pre-commit and CI secret scanning, tracked-file data scan, dependency scan, and configuration validation. CI uses no production secrets, OpenAI key, Gmail credential, or real transcript.
  - Pin GitHub Actions by commit SHA; grant each workflow minimum permissions; use separate read-only pull-request and write-capable release permissions.

- Deploy local n8n:
  - Bind-mount Superwhisper recordings read-only and the inbox/output root read-write; bind localhost only.
  - Store n8n state in a named volume, credentials in n8n's encrypted credential store, and its encryption key only in the local restricted `.env`.
  - Enable only required nodes; keep Execute Command disabled. Disable successful-execution payload persistence and prune native failure history after a short diagnostic window.

- Implement the versioned n8n intake workflow:
  - Poll recursively for completed `meta.json` records; require the exact `Idea Inbox` mode and non-empty transcript/first-pass note.
  - Stabilize incomplete writes before processing, validate metadata against a local schema, and use a source ID/path hash as an idempotency key.
  - Serialize processing with persisted states: `pending`, `processing`, `succeeded`, `retry_pending`, and `quarantined`.
  - Call the configured model (see Model configuration decision above) through a strict structured-output schema. Include transcript and first-pass note as untrusted data; prohibit tool use and all external actions.
  - Persist a single JSON record with capture metadata, source reference, transcript, first-pass note, model result, workflow/prompt/schema versions, and `approval_state: not_requested`.

- Add layered error handling:
  - Classify failures as transient (timeouts, network failures, 429, 5xx), model-output repairable, or terminal (invalid source, auth/configuration failure, schema failure after repair).
  - Retry transient items locally up to four total attempts using persisted exponential backoff—2, 10, then 60 minutes—with a request timeout and a stale-processing-lock recovery path.
  - Move exhausted or terminal items to a local dead-letter area and write append-only, structured, transcript-free diagnostic records containing source ID, timestamps, error class/message, request ID, attempt history, and remediation hint.
  - Send one Gmail alert only after terminal failure. It must contain no transcript, prompt, credential, or sensitive metadata; include the event ID and local diagnostic location. The Gmail OAuth credential is created only in n8n and excluded from exports.
  - Define the machine-readable issue-log format so a future AI reviewer can periodically inspect and summarize it without changing any source record.

- Establish model quality control:
  - Start with the configured model behind a single configuration value.
  - Create a versioned, redacted golden evaluation set with expected title, summary, actions, project, unknowns, urgency, confidence, and approval behavior.
  - Iterate prompt, schema, and model configuration before considering fine-tuning. Promotion requires 100% valid-schema/safety behavior and at least 90% agreement with human labels.
  - Treat formal model fine-tuning as a later gated project requiring separately approved training-data, retention, cost, and rollback decisions.

## Key Technical Decisions

| Decision | Selected approach | Main advantage | Trade-off |
|---|---|---|---|
| Workflow source | Sanitized n8n JSON in Git | Reviewable diffs, rollback, reproducible recovery | Requires import/export discipline |
| Failure recovery | Persisted queue + exponential retry + dead letter | Survives restarts and distinguishes transient from terminal failures | More workflow state to test |
| Alerting | Gmail only after exhaustion | Visible failure notification without operational actions | Adds OAuth setup and an external message |
| CI | Static validation plus Docker smoke test with mocked model output | Catches configuration/startup regressions without data or API spend | Does not validate production OpenAI behavior |
| Model improvement | Evaluation and prompt iteration first | Evidence-based, low-risk quality improvement | Does not immediately customize model weights |

## CI/CD and GitHub Plan

- On every pull request: validate JSON/YAML and schemas; lint scripts; scan secrets, tracked files, dependencies, and container configuration; run the Docker smoke test using synthetic recordings and a mocked structured model response. Implemented in [#4](https://github.com/boggotron/voice-note-inbox/issues/4).
- On protected-branch merge: build and verify the pinned local deployment artefacts, publish only source/release metadata if desired, and create a signed/tagged release. Do not deploy to the Mac automatically. Implemented in [#9](https://github.com/boggotron/voice-note-inbox/issues/9).
- Require a manual local deployment step: review release notes, back up the local n8n volume and `.env`, import the reviewed workflow, run the preflight mount test, then execute the acceptance suite. Documented in [#10](https://github.com/boggotron/voice-note-inbox/issues/10).
- Maintain rollback instructions for workflow JSON, Compose image digest, prompt/schema version, and n8n state backup. Documented in [#10](https://github.com/boggotron/voice-note-inbox/issues/10).
- Branch protection on `main` requires the `validate`, `scan`, and `smoke-test` checks from [#4](https://github.com/boggotron/voice-note-inbox/issues/4) to pass, requires PR review, and blocks direct pushes and force-pushes. Configured in [#1](https://github.com/boggotron/voice-note-inbox/issues/1).
- Every workflow file is pinned to third-party actions by commit SHA and declares an explicit minimal `permissions:` block; PR-time workflows are read-only, only the release workflow ([#9](https://github.com/boggotron/voice-note-inbox/issues/9)) has write-capable (`contents: write`, tag-only) permissions.

## Test Plan

- Verify read-only source mount and local-only n8n access.
- Process a valid synthetic recording exactly once; repeat its event and confirm idempotency.
- Test incomplete metadata, wrong mode, malformed JSON, duplicate event, restart during processing, stale lock, timeout, 429, 5xx, invalid model JSON, authentication failure, and disk-write failure.
- Confirm retry schedule, dead-letter creation, sanitized diagnostic detail, and exactly one Gmail alert after retry exhaustion.
- Confirm no calendar/task/message creation beyond the approved terminal-failure Gmail alert.
- Confirm public-repository scans find no credentials, recordings, transcripts, output records, logs, n8n state, or personal paths.

The full, itemized version of this Test Plan is the acceptance criteria of
[#8](https://github.com/boggotron/voice-note-inbox/issues/8); the CI-time
subset (startup + one synthetic happy-path event) is
[#4](https://github.com/boggotron/voice-note-inbox/issues/4)'s `smoke-test` job.

## Task breakdown & dependency graph

Tracked as GitHub Issues under [Epic #11](https://github.com/boggotron/voice-note-inbox/issues/11).
Each issue carries the full plan contract (goal, scope, non-goals, architecture
impact, dependencies, risks, security/data/migration implications, acceptance
criteria). Per the Agentic Engineering methodology, each issue proceeds through
its own DESIGN → PLAN → ISOLATE → IMPLEMENT → REVIEW → VERIFY → CI/PR →
READY FOR HUMAN → HUMAN APPROVAL → MERGE lifecycle independently; this plan
document only fixes the cross-issue scope and ordering.

| Round | Issue | Title | Depends on | Notes |
|---|---|---|---|---|
| 1 | [#1](https://github.com/boggotron/voice-note-inbox/issues/1) | Repo & GitHub hygiene | — | Foundational; gates branch protection for everything else |
| 1 | [#2](https://github.com/boggotron/voice-note-inbox/issues/2) | Schemas, contracts & fixtures | — | Foundational; independent write set from #1 |
| 1 | [#3](https://github.com/boggotron/voice-note-inbox/issues/3) | Local n8n deployment (Compose) | #1 | Independent write set from #2; can start once #1 lands |
| 2 | [#4](https://github.com/boggotron/voice-note-inbox/issues/4) | CI: PR validation & smoke test | #1, #2 | Independent write set from #5 |
| 2 | [#5](https://github.com/boggotron/voice-note-inbox/issues/5) | n8n intake workflow core | #2, #3 | Independent write set from #4 |
| 3 | [#6](https://github.com/boggotron/voice-note-inbox/issues/6) | Error handling, dead-letter, alert | #5 | Edits the same workflow file as #5; must be serialized after it |
| 3 | [#7](https://github.com/boggotron/voice-note-inbox/issues/7) | Model eval harness & promotion gate | #2, #5 | Can run parallel to #6 if it avoids the same workflow file sections |
| 4 | [#8](https://github.com/boggotron/voice-note-inbox/issues/8) | End-to-end acceptance suite | #5, #6 | |
| 4 | [#9](https://github.com/boggotron/voice-note-inbox/issues/9) | CI: release workflow | #4, #3 | Highest-privilege workflow in the repo; review accordingly |
| 5 | [#10](https://github.com/boggotron/voice-note-inbox/issues/10) | Docs: privacy, threat model, runbook, rollback | #1, #3, #5, #6, #9 | Can start drafting earlier; finalize last |

Parallelism follows the methodology's safe-parallelism rule: independent,
non-conflicting write sets (different files/directories) may run concurrently;
overlapping write-heavy work (e.g. #5 and #6 both editing the intake workflow
definition) is serialized by dependency order instead.

## Skills for Claude Sonnet 5

- **agentic-engineering** (`engineering-workflow`, `designing-changes`,
  `planning-implementation`, `executing-tasks`, `testing-changes`,
  `reviewing-changes`, `verifying-completion`, `finishing-work`,
  `debugging-systematically`): the controlling methodology for every sub-issue
  from here through merge. This plan and its issues were produced under this
  skill set.
- **security-review**: run before merging [#1](https://github.com/boggotron/voice-note-inbox/issues/1),
  [#3](https://github.com/boggotron/voice-note-inbox/issues/3), and any change
  touching credentials, the model call, or the Gmail alert.
- **code-review**: required before merging any workflow, Compose, or CI change.
- **superpowers** (`test-driven-development`, `systematic-debugging`,
  `subagent-driven-development`, `using-git-worktrees`): used within each
  sub-issue's IMPLEMENT/REVIEW/VERIFY stages as the concrete Claude Code
  mechanics behind the portable Agentic Engineering lifecycle.
- **playwright** / **chrome-devtools-mcp**: optional, for documenting or
  regression-testing the local n8n UI; never used to expose the local editor
  externally.
- **plugin-dev**: not needed for the MVP unless the future AI issue-reviewer
  mentioned in [#6](https://github.com/boggotron/voice-note-inbox/issues/6)
  becomes a custom Claude/Codex integration.

## Assumptions

- The repository is public; all live data remains outside it and is excluded by both ignore rules and CI gates.
- Enriched records and local diagnostic records are retained indefinitely.
- Gmail is available for the approved terminal-failure alert.
- No automatic external actions are added beyond that alert.
