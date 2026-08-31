# Public, Local Voice Inbox MVP

## Summary

Build a public GitHub repository containing only sanitized infrastructure, workflow definitions, tests, and documentation. The deployed system remains local to the Mac: Superwhisper recordings are mounted read-only into n8n, enriched with OpenAI, and saved to a durable local inbox. No task/calendar/message automation is permitted, except a terminal-failure Gmail alert explicitly approved for this MVP.

Raw transcripts may be sent to the OpenAI API. OpenAI states API data is not used to train models unless opted in; default abuse-monitoring logs may retain content for up to 30 days, with legal and safety exceptions. Use foreground requests with server-side storage disabled where supported, and record this policy in the privacy documentation. [Official OpenAI data controls](https://developers.openai.com/api/docs/guides/your-data)

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
  - Store n8n state in a named volume, credentials in n8n’s encrypted credential store, and its encryption key only in the local restricted `.env`.
  - Enable only required nodes; keep Execute Command disabled. Disable successful-execution payload persistence and prune native failure history after a short diagnostic window.

- Implement the versioned n8n intake workflow:
  - Poll recursively for completed `meta.json` records; require the exact `Idea Inbox` mode and non-empty transcript/first-pass note.
  - Stabilize incomplete writes before processing, validate metadata against a local schema, and use a source ID/path hash as an idempotency key.
  - Serialize processing with persisted states: `pending`, `processing`, `succeeded`, `retry_pending`, and `quarantined`.
  - Call the configured Luna model through a strict structured-output schema. Include transcript and first-pass note as untrusted data; prohibit tool use and all external actions.
  - Persist a single JSON record with capture metadata, source reference, transcript, first-pass note, model result, workflow/prompt/schema versions, and `approval_state: not_requested`.

- Add layered error handling:
  - Classify failures as transient (timeouts, network failures, 429, 5xx), model-output repairable, or terminal (invalid source, auth/configuration failure, schema failure after repair).
  - Retry transient items locally up to four total attempts using persisted exponential backoff—2, 10, then 60 minutes—with a request timeout and a stale-processing-lock recovery path.
  - Move exhausted or terminal items to a local dead-letter area and write append-only, structured, transcript-free diagnostic records containing source ID, timestamps, error class/message, request ID, attempt history, and remediation hint.
  - Send one Gmail alert only after terminal failure. It must contain no transcript, prompt, credential, or sensitive metadata; include the event ID and local diagnostic location. The Gmail OAuth credential is created only in n8n and excluded from exports.
  - Define the machine-readable issue-log format so a future AI reviewer can periodically inspect and summarize it without changing any source record.

- Establish model quality control:
  - Start with Luna behind a single configuration value.
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

- On every pull request: validate JSON/YAML and schemas; lint scripts; scan secrets, tracked files, dependencies, and container configuration; run the Docker smoke test using synthetic recordings and a mocked structured model response.
- On protected-branch merge: build and verify the pinned local deployment artefacts, publish only source/release metadata if desired, and create a signed/tagged release. Do not deploy to the Mac automatically.
- Require a manual local deployment step: review release notes, back up the local n8n volume and `.env`, import the reviewed workflow, run the preflight mount test, then execute the acceptance suite.
- Maintain rollback instructions for workflow JSON, Compose image digest, prompt/schema version, and n8n state backup.

## Test Plan

- Verify read-only source mount and local-only n8n access.
- Process a valid synthetic recording exactly once; repeat its event and confirm idempotency.
- Test incomplete metadata, wrong mode, malformed JSON, duplicate event, restart during processing, stale lock, timeout, 429, 5xx, invalid model JSON, authentication failure, and disk-write failure.
- Confirm retry schedule, dead-letter creation, sanitized diagnostic detail, and exactly one Gmail alert after retry exhaustion.
- Confirm no calendar/task/message creation beyond the approved terminal-failure Gmail alert.
- Confirm public-repository scans find no credentials, recordings, transcripts, output records, logs, n8n state, or personal paths.

## Skills for Claude Sonnet 5

Install or enable these if available:

- **superpowers / CI-CD skill set**: use for project decomposition, GitHub Actions design, release/rollback checklists, and disciplined incremental delivery. It is not installed in this Codex environment, so verify its exact commands in Claude before relying on them.
- **security-guidance**: required for threat modelling, public-repository hygiene, credential boundaries, and log redaction.
- **feature-dev**: implement the repository, workflow assets, fixtures, and acceptance harness in small reviewable increments.
- **code-review**: required before merging workflow, Compose, and CI changes.
- **code-simplifier**: apply after tests pass to keep the retry/error design maintainable.
- **playwright** and **chrome-devtools-mcp**: optional for documenting and regression-testing the local n8n UI setup; do not use them to expose the local editor.
- **plugin-dev**: not needed for the MVP unless the future AI issue-reviewer becomes a custom Claude/Codex integration.

## Assumptions

- The repository is public; all live data remains outside it and is excluded by both ignore rules and CI gates.
- Enriched records and local diagnostic records are retained indefinitely.
- Gmail is available for the approved terminal-failure alert.
- No automatic external actions are added beyond that alert.
