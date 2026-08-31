# Security Policy

## Scope

This repository publishes sanitized infrastructure, workflow definitions,
tests, and documentation for a local, single-user voice-note automation
pipeline. The running system stays on the operator's own Mac: it reads
voice recordings from a read-only local mount, enriches them via the
OpenAI API, and writes results to a local inbox. No task, calendar, or
messaging automation is performed, other than a single narrowly-scoped
terminal-failure email alert.

Nothing in this repository handles live user data, credentials, or secrets.
Real recordings, transcripts, model output, logs, and n8n runtime state are
excluded from version control (see `.gitignore`) and must never be
committed. If you find any of that content — or any other credential or
secret — tracked in this repository, please report it as described below.

## Reporting a Vulnerability

Please report security issues privately rather than opening a public GitHub
issue. Use one of the following, in order of preference:

1. **GitHub Private Vulnerability Reporting**: open a report via the
   repository's [Security tab](https://github.com/boggotron/voice-note-inbox/security/advisories/new).
2. **Email**: [abogdan.inbox@gmail.com](mailto:abogdan.inbox@gmail.com).

Please include:

- A description of the issue and its potential impact.
- Steps to reproduce, or a proof of concept if available.
- Any affected file(s), workflow(s), or commit(s).

You should expect an initial response within a few days. This is a
single-maintainer personal project without a formal SLA, but credential
leaks and secret-scanning bypasses will be treated as highest priority.

Please do not publicly disclose a vulnerability (e.g. in a GitHub issue,
pull request, or discussion) until it has been reviewed and, if applicable,
fixed.

## Repository Controls

This repository is public and relies on the following controls to keep
credentials and personal data out of the tracked history:

- GitHub secret scanning and push protection are enabled.
- Dependabot alerts and automated security updates are enabled.
- `main` is protected: changes require a pull request with at least one
  approving review, up-to-date required status checks (`validate`, `scan`,
  `smoke-test`), and direct or force pushes are blocked.
- A repository-level `.gitignore` gate list excludes `.env*` (other than
  the tracked `.env.example`), `recordings/`, `output/`, `logs/`,
  `dead-letter/`, n8n runtime/volume/database exports, backups, and test
  artefacts, so none of that content can be tracked in the first place.
- GitHub Actions workflows in this repository (added in later issues) are
  expected to: pin third-party actions to a commit SHA rather than a
  mutable tag, declare an explicit minimal `permissions:` block per
  workflow, keep pull-request-time workflows read-only, and grant
  write-capable permissions (e.g. `contents: write`) only to the tag-only
  release workflow.

## Data Handling Note (OpenAI API)

Transcripts and first-pass notes are sent to the OpenAI API for
enrichment. Per OpenAI's published data controls, API data is not used to
train models unless the account has explicitly opted in; default
abuse-monitoring logs may retain content for up to 30 days, subject to
legal and safety exceptions. Where the configured model/endpoint supports
it, requests are made with server-side response storage disabled
(`store: false`) and as foreground (non-batch) requests. See
[OpenAI's API data controls](https://developers.openai.com/api/docs/guides/your-data)
for the current policy. No transcript, prompt, or model output is ever
included in the terminal-failure alert email or in any file tracked in
this repository.
