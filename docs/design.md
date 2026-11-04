# Container integration design

The gateway image extends the pinned Nous Research Hermes Agent v0.21.5 container. The original integration consists of an entrypoint that honors the native home/configuration contract and starts the gateway with `exec`. Kubernetes deployments supply their own secrets, model configuration, skills, storage, and permissions.

The Dockerfile retains a targeted compatibility backport of upstream commit `33287432`: Anthropic Console `sk-ant-usr` keys are treated as API keys rather than subscription OAuth credentials. The build verifies the replacement is present. On an upstream base upgrade, verify the new credential classifier and remove this patch when it is included upstream. Retain the upstream license and notices when distributing modified code.

The pinned upstream webhook adapter and turn resolver both treat an empty per-route tool list as absent by default. The image applies a source-guarded compatibility patch so `toolsets: []` resolves to zero tools, including bypassing default MCP toolsets. The Docker build exercises the actual patched methods through `tests/check_upstream.py`; base upgrades must revalidate this boundary and remove the patch when upstream fixes it. Routes that omit a tool list retain upstream defaults.

The image downloads an independently checksum-pinned real Tini v0.19.0 executable at `/usr/local/bin/tini`. The base image’s `/usr/bin/tini` is an s6 compatibility shell wrapper and cannot be used for this non-root entrypoint. Real Tini acts as PID 1, forwards process-group signals, and reaps orphan processes.

The separate alert router has no external Python dependencies. Its incoming shared secret and outgoing HMAC key are distinct credentials. It signs the exact serialized JSON bytes with a fresh timestamp using Hermes's generic V2 signature. Recovery events have their own delivery identity. Forward failures preserve the incident identity for sender-driven retries. A per-monitor in-flight guard prevents concurrent transitions from corrupting incident state. Expiration and a capacity limit bound the incident map.

HTTP health only establishes process availability. It does not prove provider access, authorized chat delivery, model correctness, or workload recovery. Authentication establishes an event source; payload text remains untrusted. Agent tools and operational privileges must be explicitly configured and verified in the deployment.

Acceptance for a consuming deployment includes UID/GID and writable-home checks, configuration and skill loading, unauthorized-chat rejection, gateway shutdown/crash handling, webhook signing compatibility, and observed outcomes for any enabled operational action. Test real provider/chat traffic only with explicit operator authorization.

Pinned shutdown contract: `gateway/run_shutdown.py::_resolve_gateway_exit_verdict` returns false after an unplanned SIGTERM, so the CLI exits 1 after teardown. The signal handler records this separately from marked CLI planned stops. Build checks execute the actual verdict function; runtime acceptance requires health before and after an ungraceful restart, then a bounded exit1 on SIGTERM and its native signal log. A forced exit137 fails acceptance.
