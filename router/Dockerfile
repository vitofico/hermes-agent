# Hermes alert router image.
#
# Small stdlib-only Python service that authenticates and dedups Uptime Kuma
# webhooks before forwarding them to the hermes-agent route. No dependencies,
# so a plain python:3-alpine base is enough.
FROM python:3.12-alpine@sha256:d09d15e60962ca365d1cd544a48773bac9d33f2fb1b00f2aa0deec78ade7dc31

WORKDIR /app

COPY --chmod=0755 router.py /app/router.py
COPY LICENSE /usr/share/licenses/hermes-agent-router/LICENSE

# Read-only root filesystem friendly: router.py is static; state is in-memory.
ENV PYTHONDONTWRITEBYTECODE=1
USER 65532:65532
EXPOSE 8080

ENTRYPOINT ["python3", "/app/router.py"]
