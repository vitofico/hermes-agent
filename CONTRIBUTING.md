# Contributing

Run `make test` and `make lint`, then build both Docker contexts. Behavioral changes need regression tests using synthetic inputs and mocked outbound HTTP. Do not use live provider credentials, chat accounts, or operational clusters in CI.

Keep generic container/router behavior here. Keep account identities, concrete cluster policies, schedules, credentials, skills tied to one environment, and deployment records in the consuming repository. Preserve upstream attribution. Base-image upgrades require runtime smoke checks against that exact pinned image and the documented non-root configuration.
