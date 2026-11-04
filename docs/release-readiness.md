# Release readiness

The new repository and nested image packages start private while their public export is prepared. The original private source and legacy image packages remain available until their consuming cluster has switched successfully. They are not inputs to this repository’s history.

Before changing public visibility:

- Review every candidate file, examples, commit author metadata, and links. Keep instance identifiers, credentials, rendered cluster configuration, private diagnostics, and identifier inventories outside this repository.
- Run `make test shellcheck py-compile privacy`; lint both Dockerfiles. Scan a `git archive HEAD` export and complete fresh Git history with a pinned offline secret scanner. Inspect findings individually; secret scans do not establish privacy.
- Render the Compose example with synthetic credentials. Build gateway and router for `linux/amd64`. Run `tests/smoke-image.sh IMAGE` against the actual gateway image with networking disabled. Review the real Tini, explicit-empty-toolset and Anthropic compatibility checks when the upstream base changes.
- Require clean CI from the exact source revision. Inspect its logs, Docker build artifacts, SBOM, provenance, image layers and OCI labels for private identifiers and legacy source links. Retain MIT and required third-party notices.
- Record reviewed registry digests for `ghcr.io/vitofico/hermes-agent/gateway` and `ghcr.io/vitofico/hermes-agent/router`. Check each image points to this source repository and exact revision. Packages and source repository have separate visibility settings.
- Complete independent privacy and clean-setup reviews, then make only the new repository and intended nested packages public. Verify anonymous clone and anonymous pull of each exact digest; a logged-in pull does not establish public availability.
- Update the public homelab kit and private cluster consumer references to those verified digests. Repository changes do not deploy workloads. Live cluster migration has its own operational verification; keep legacy images available until that switch is confirmed.

The default automated acceptance uses synthetic credentials and no external networking. Real provider/model/chat testing is a separate opt-in operator check; process health alone does not establish successful model or chat access.
