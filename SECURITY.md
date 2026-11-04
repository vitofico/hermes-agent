# Security and privacy

During private preparation, report vulnerabilities directly to the repository owner through the existing private collaboration channel. Before public release, enable [GitHub private vulnerability reporting](https://github.com/vitofico/hermes-agent/security/advisories/new). If that channel is unavailable, open a minimal issue requesting private contact without including exploit details, credentials, or instance identifiers.

Keep model/chat tokens, webhook keys, persistent homes, conversations, operational logs, and deployment configurations outside this repository. Examples and tests use synthetic values. Use high-entropy independent incoming and outgoing router secrets and restrict access to both gateway and router at the deployment boundary. HTTP forwards inside a private network are not encrypted; use HTTPS or reviewed transport protection when required.

A signed event is untrusted input to the agent. This container does not supply an independent human approval service. Configure least-privilege tools, RBAC, and any required approval boundary in the deployment. Do not expose an agent capable of operational writes solely on the strength of its prompt.

This project starts from a fresh reviewed snapshot; legacy operational history stays in its private source repository. Before publication, inspect candidate files and commit metadata, scan the snapshot and complete fresh history, and review the new repository’s Actions artifacts and image metadata separately. Follow [release readiness](docs/release-readiness.md). Secret scanning does not establish that personal or operational identifiers are absent.
