IMAGE ?= ghcr.io/vitofico/hermes-agent/gateway
ROUTER_IMAGE ?= ghcr.io/vitofico/hermes-agent/router
TAG   ?= dev
PLATFORM ?= linux/amd64

.PHONY: build build-router lint shellcheck hadolint py-compile test privacy

build:
	docker build --platform $(PLATFORM) -t $(IMAGE):$(TAG) .

build-router:
	docker build --platform $(PLATFORM) -t $(ROUTER_IMAGE):$(TAG) router

lint: shellcheck hadolint py-compile

shellcheck:
	shellcheck entrypoint.sh tests/smoke-image.sh

hadolint:
	hadolint Dockerfile router/Dockerfile

py-compile:
	python3 -m py_compile router/router.py

test:
	python3 -m unittest discover -s tests -v

privacy:
	python3 tools/audit-publication.py
