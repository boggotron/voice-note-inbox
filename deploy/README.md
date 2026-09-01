# Local n8n deployment (issue #3)

Sanitized, reproducible local n8n instance definition. See the parent
issue (#3) and `local-voice-inbox-mvp-implementation-plan.md` at the
repo root for full context. This directory defines the deployment
boundary only — it does not include the intake workflow itself (#5)
or CI validation of this config (#4).

## Usage

```
cp deploy/.env.example deploy/.env
# edit deploy/.env — set N8N_ENCRYPTION_KEY and, if needed, the host data paths
docker compose -f deploy/docker-compose.yml --env-file deploy/.env up -d
```

Once a container is running, `deploy/preflight.sh` checks the
read-only recordings mount, the read-write output mount, the
localhost-only port binding, and the Execute Command node exclusion.

## Image digest provenance

`deploy/docker-compose.yml` pins the n8n image by content digest
rather than a mutable tag:

```
n8nio/n8n@sha256:cfe2704ff858395503d42548206c2c99ea351a205e941063a9d9b77b0f404478
```

This was resolved on **2026-08-31** directly against Docker Hub's
registry API (no local Docker daemon required):

1. Requested an anonymous pull token:
   `https://auth.docker.io/token?service=registry.docker.io&scope=repository:n8nio/n8n:pull`
2. Fetched the manifest index for the `n8nio/n8n:stable` tag (n8n's
   explicitly-stable channel, preferred over the more ambiguous
   `latest`) from
   `https://registry-1.docker.io/v2/n8nio/n8n/manifests/stable`,
   requesting `application/vnd.oci.image.index.v1+json`.
3. The registry returned `docker-content-digest:
   sha256:cfe2704ff858395503d42548206c2c99ea351a205e941063a9d9b77b0f404478`
   (HTTP 200). This is a multi-arch OCI image index (linux/amd64 and
   linux/arm64 manifests, each with a build-provenance attestation
   manifest) — Docker automatically selects the right platform
   manifest at pull time.
4. Cross-checked: the `latest` tag resolved to the same digest at the
   time of lookup, confirming `stable` and `latest` currently point
   at the same build.

**Known gap:** no bare semver tag (e.g. `2.37.5`) on Docker Hub
matched this digest at lookup time. n8n's release automation had only
published per-architecture semver tags (`2.37.5-amd64`,
`2.37.5-arm64`, etc. — no combined multi-arch `2.37.5` index yet)
alongside the floating `latest`/`stable` tags. The prior full
multi-arch tag, `2.37.4`, was checked and does **not** match this
digest, so the pinned build is newer than 2.37.4 but its exact semver
isn't independently documented here.

### Re-resolving or confirming the version later

Once a Docker daemon is available:

```
docker run --rm n8nio/n8n@sha256:cfe2704ff858395503d42548206c2c99ea351a205e941063a9d9b77b0f404478 n8n --version
```

To bump the pin in the future, repeat the registry API lookup above
against the tag of your choice (or `docker manifest inspect
n8nio/n8n:<tag>` if you have Docker available), replace the digest in
`deploy/docker-compose.yml`, and update this file's digest value and
date.
