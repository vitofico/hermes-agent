# Hermes Agent container

A small container integration for [Nous Research Hermes Agent](https://github.com/NousResearch/hermes-agent), plus a standalone Uptime Kuma alert router. This project is independently maintained; it does not contain a deployment's accounts, cluster privileges, prompts, or credentials.

## First run from source

Docker Engine with the Compose plugin and make are required for this flow. This source repository and the gateway/router image packages are public; anonymous cloning and image pulls require no GitHub or GHCR credentials. The companion `:dev` images in this flow are built locally. The gateway's pinned base and both published image builds currently target **linux/amd64**; ARM hosts need working amd64 emulation. Other router architectures have not been verified.

```sh
git clone https://github.com/vitofico/hermes-agent.git
cd hermes-agent
cp .env.example .env
chmod 600 .env
# Edit .env: supply your Anthropic key and two independent random webhook keys.
# Generate each webhook key separately with: openssl rand -hex 32
make build build-router
docker compose --env-file .env config --quiet
docker compose up -d --no-build
docker compose ps
curl --fail http://127.0.0.1:8080/health
```

This builds `:dev` images locally, so first run does not depend on an available registry release. [compose.yaml](compose.yaml) starts the gateway plus router. A new named volume is populated from the image with UID/GID `10000` ownership, and the generic configuration is mounted read-only. No host-directory chown is required for a fresh volume. The gateway is reachable only on the Compose network; the router's health/webhook port is bound to localhost. Both services use `restart: unless-stopped`; an explicit Compose stop/down remains stopped. Persistent homes contain private state. `docker compose down` stops the stack and retains its volume; preserve that volume when upgrading.

The example explicitly selects Anthropic and `claude-sonnet-4-5`. Choose a model supported by your account and review provider costs before use. Credentials remain in your ignored `.env`; Compose must receive its real values only for normal operation. Tests and isolated acceptance use synthetic values with networking disabled.

## Images and Kubernetes

| Component | Public package | Verified build platform |
|---|---|---|
| Gateway | `ghcr.io/vitofico/hermes-agent/gateway` | `linux/amd64` |
| Alert router | `ghcr.io/vitofico/hermes-agent/router` | `linux/amd64` |

CI publishes `sha-<short>` images from `main` or an explicit manual dispatch, and version tags from `v*` releases. For example, pull the reviewed source build without registry credentials:

```sh
docker pull --platform linux/amd64 ghcr.io/vitofico/hermes-agent/gateway:sha-a475ec4
docker pull --platform linux/amd64 ghcr.io/vitofico/hermes-agent/router:sha-a475ec4
# Record the immutable registry references returned for this build.
docker image inspect ghcr.io/vitofico/hermes-agent/gateway:sha-a475ec4 \
  --format '{{index .RepoDigests 0}}'
docker image inspect ghcr.io/vitofico/hermes-agent/router:sha-a475ec4 \
  --format '{{index .RepoDigests 0}}'
```

Use the resulting `ghcr.io/…@sha256:…` references in deployments; registry digests are immutable while tags can be moved. The Compose quickstart above deliberately builds local `:dev` images. To run published images through Compose, supply a local override selecting the two digest references and use `docker compose -f compose.yaml -f local/published.compose.yaml up -d --no-build`. Configure credentials and persistent storage exactly as for the source build.

The gateway uses the pinned Hermes v0.21.5 base in `Dockerfile`. Its source-guarded Anthropic authentication and empty-webhook-toolset compatibility patches, plus the independently pinned real Tini, are documented in [design.md](docs/design.md).

For Kubernetes, use [Kubernetes Homelab Kit](https://github.com/vitofico/kubernetes-homelab-kit) and its optional Hermes modules. Image release/digest selection is explicit; verify the kit revision you use supports the selected companion image contract. Deployment-specific skills, RBAC, networking, model selection, and repair authority belong to the consuming repository. Archived operational source and older flat image packages remain private rollback assets. Public installation uses the nested packages above; new builds publish only those packages.

## Gateway configuration

Tini supervises the gateway and reaps orphan processes. The shell entrypoint starts `hermes gateway run` directly with `exec`: the gateway receives container signals and its exit status becomes the container exit status. It does not write credentials to disk or remove another gateway's PID file. Use a single gateway process per persistent home and a supervisor restart policy appropriate to your deployment. The pinned upstream handles ordinary container `SIGTERM` with graceful teardown and deliberately exits **1** to request supervisor restart; this differs from its marked CLI planned-stop path. An exit status alone is not proof of a crash or of graceful cleanup.

| Input | Default / contract |
|---|---|
| `HOME` | `/opt/data`; writable by UID/GID `10000` |
| `HERMES_HOME` | `$HOME/.hermes`; config, skills, and persistent state |
| `HERMES_WRITE_SAFE_ROOT` | `$HOME` |
| `TELEGRAM_BOT_TOKEN` | Optional; enables the configured Telegram adapter |
| `TELEGRAM_ALLOWED_USERS` | Required with a Telegram token; comma-separated numeric user IDs |
| `TELEGRAM_USER_ID` | Legacy single-user alias when `TELEGRAM_ALLOWED_USERS` is absent |
| `WEBHOOK_ENABLED` | Set `true` to enable the webhook platform |
| `WEBHOOK_SECRET` | Required with enabled webhooks; `HERMES_WEBHOOK_SECRET` is an alias |
| `WEBHOOK_PORT` | Upstream webhook port; use `8644` for the example |
| Provider credentials | Supply the variables required by your selected Hermes model/provider |

Mount your reviewed `config.yaml` at `$HERMES_HOME/config.yaml` and skills below `$HERMES_HOME/skills`. [examples/config.yaml](examples/config.yaml) is an alert-only starting point. Credentials go in an ignored env file, secret manager, or Kubernetes Secret. Never publish the persistent home: it can contain private prompts and conversations.

`GET /health` is served by the upstream webhook platform on port 8644. Process health does not establish model access or successful chat delivery.

### Optional Telegram

The default example enables only webhooks. To add interactive chat:

1. Create the ignored configuration copy: `mkdir -p local && cp examples/config.yaml local/config.yaml`.
2. Under its existing `platforms` map, add `telegram: {enabled: true}` while retaining the webhook section.
3. Set `HERMES_CONFIG=./local/config.yaml`, your `TELEGRAM_BOT_TOKEN`, and comma-separated numeric `TELEGRAM_ALLOWED_USERS` in `.env`.
4. Recreate the gateway with `docker compose up -d --no-build --force-recreate gateway`. Verify an unlisted account is rejected before relying on chat access.

The webhook route has an explicit empty tool list. Enabling Telegram does not grant cluster privileges: any interactive tools, skills, credentials, and approval boundary require deployment-specific review. No real chat traffic is sent by default tests.

## Alert router

The router authenticates `POST /webhooks/uptime-kuma` using `X-Webhook-Secret`. It forwards first DOWN and corresponding UP events with Hermes V2 HMAC signatures and distinct delivery IDs. Duplicate DOWN, unsolicited UP, PENDING, and MAINTENANCE events are suppressed. Failed deliveries remain retryable when the sender retries; the router does not schedule retries itself. Signing timestamps are refreshed while the incident's delivery identity remains stable.

| Variable | Default / contract |
|---|---|
| `WEBHOOK_SHARED_SECRET` | Required; Uptime Kuma's incoming header value |
| `HERMES_WEBHOOK_SECRET` | Required; must match the destination route's secret |
| `HERMES_URL` | Required HTTP(S) destination, e.g. `http://gateway:8644/webhooks/uptime-kuma` |
| `LISTEN_HOST`, `LISTEN_PORT` | `0.0.0.0`, `8080` |
| `HERMES_TIMEOUT` | `15` seconds, maximum `60` |
| `INCIDENT_TTL` | `7200` seconds |
| `MAX_INCIDENTS` | `10000`; capacity exhaustion returns retryable HTTP 503 |
| `LOG_LEVEL` | `INFO` |

The router runs as UID/GID `65532`, requires no writable persistent volume, and exposes `GET /health`. Request bodies are limited to 1 MB and read timeouts to 20 seconds, with at most 64 concurrent request handlers. Redirects and ambient HTTP proxies are disabled for forwards. Use one replica: state is in memory, is not shared, and resets on restart. Incidents expire after the TTL, so a long-running outage can produce a fresh notification. Concurrent deliveries for one monitor receive HTTP 503 and require sender retry. Secrets and raw monitor payloads are excluded from normal logs.

### Connect Uptime Kuma

For a sender on the same Compose network, use `http://router:8080/webhooks/uptime-kuma`; a sender on the Docker host can use `http://127.0.0.1:8080/webhooks/uptime-kuma`. Configure JSON payloads and the custom header `X-Webhook-Secret` with the same value as `WEBHOOK_SHARED_SECRET`. The router signs its outgoing request with the distinct gateway key. A container on another network cannot use the host's localhost address; configure a reviewed private connection instead of exposing an unrestricted public port.

Health checks do not invoke the model:

```sh
curl --fail http://127.0.0.1:8080/health
docker compose exec -T gateway /opt/hermes/.venv/bin/python -c \
  'import urllib.request; print(urllib.request.urlopen("http://127.0.0.1:8644/health", timeout=2).read().decode())'
```

A real authenticated DOWN/UP webhook can invoke the configured model and incur provider costs. Perform that integration test deliberately with synthetic monitor data after health and access checks. Avoid posting tokens or raw monitor payloads in public reports.

## Develop and release

```sh
make test
make lint  # shellcheck, hadolint, Python compilation
make privacy
make build build-router
# Gateway acceptance: uses the actual example config with networking disabled.
tests/smoke-image.sh ghcr.io/vitofico/hermes-agent/gateway:dev
```

Tests use fake credentials and mocked HTTP. CI runs isolated image acceptance with the actual entrypoint, example config, non-root home, zero tool schemas, forced-stop/restart recovery, and bounded SIGTERM shutdown. Real model/chat access and consuming Kubernetes behavior require separate operator acceptance.

See [release readiness](docs/release-readiness.md), [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
