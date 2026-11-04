# Pinned to nousresearch/hermes-agent v2026.9.24 (Hermes v0.21.5). Pin by
# digest so the base image cannot drift under a moving tag. Bump deliberately
# and re-verify config compatibility.
FROM nousresearch/hermes-agent@sha256:fca358f12efd65bfaaca05884166f15c0e2788375ca30d77061ac1ebc96452b7
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# The base image replaces /usr/bin/tini with an s6 wrapper requiring root.
# Use an independently checksum-pinned real init; this pinned base is amd64.
RUN curl -fsSL https://github.com/krallin/tini/releases/download/v0.19.0/tini-amd64 -o /usr/local/bin/tini \
    && echo "93dcc18adc78c65a028a84799ecf8ad40c936fdfc5f2a57b1acda5a8117fa82c  /usr/local/bin/tini" | sha256sum -c - \
    && chmod 0755 /usr/local/bin/tini \
    && /usr/local/bin/tini --version

# The native webhook platform (hermes gateway run) and Telegram gateway are part
# of the base image; this layer only adds the entrypoint that starts them.
COPY --chmod=0755 entrypoint.sh /opt/entrypoint.sh
COPY LICENSE THIRD_PARTY_NOTICES.md tini-LICENSE /usr/share/licenses/hermes-agent-container/

# Backport of upstream 33287432 (Hermes v0.22.x): treat sk-ant-usr* Console
# API keys as x-api-key. v0.21.5 reads them as Claude subscription OAuth
# tokens and sends the Claude Code identity, so Anthropic bills them against a
# subscription and answers "credit balance is too low". Drop on the next bump.
RUN f=/opt/hermes/agent/anthropic_credentials.py \
    && sed -i 's/key.startswith("sk-ant-api")/key.startswith(("sk-ant-api", "sk-ant-usr"))/' "$f" \
    && grep -q '"sk-ant-usr"' "$f"

COPY patches/empty_webhook_tools.py /tmp/empty_webhook_tools.py
COPY tests/check_upstream.py /tmp/check_upstream.py
RUN /opt/hermes/.venv/bin/python /tmp/empty_webhook_tools.py \
    && /opt/hermes/.venv/bin/python /tmp/check_upstream.py \
    && rm /tmp/empty_webhook_tools.py /tmp/check_upstream.py

# Native webhook platform (Uptime Kuma alerts) + its /health endpoint.
ENV HOME=/opt/data HERMES_HOME=/opt/data/.hermes HERMES_WRITE_SAFE_ROOT=/opt/data
RUN mkdir -p /opt/data/.hermes && chown -R 10000:10000 /opt/data
USER 10000:10000
EXPOSE 8644

ENTRYPOINT ["/usr/local/bin/tini", "-g", "--", "/opt/entrypoint.sh"]
