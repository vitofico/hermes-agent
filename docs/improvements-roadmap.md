# Maintenance priorities

- Revalidate the pinned upstream release and Anthropic credential backport before upgrading.
- Preserve compatibility with native Hermes home, adapter, and webhook configuration.
- Keep delivery behavior covered with synthetic regression tests.
- Evaluate durable/shared incident storage only if a deployment requires multiple router replicas; current state is intentionally process-local.

Instance-specific operational records and deployment decisions belong in the consuming deployment repository.
