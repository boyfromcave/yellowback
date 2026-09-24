# Workspace Makefile.
#
# Repositories, URLs and pins live in repos.yaml (read through scripts/repos.sh) and are
# mirrored in AGENTS.md and docs/mapping.md. `make status` fails if a ref/ repo drifts off
# its pin; `make bootstrap` recreates the whole workspace on a fresh machine.

REPOS         := scripts/repos.sh
DIGIBYTE_PIN  := $(shell $(REPOS) get ref/digibyte tag)
YCASH_PIN     := $(shell $(REPOS) get ref/ycash tag)
YECWALLET_PIN := $(shell $(REPOS) get ref/yecwallet tag)
# lightwalletd upstream publishes no tags, so its reference is pinned by commit, not tag.
LWD_PIN       := $(shell $(REPOS) get ref/lightwalletd commit)
DD_BRANCH     := $(shell $(REPOS) get ycash-dd branch)
DD_BASE       := $(shell $(REPOS) get ycash-dd base)
WALLET_BASE   := $(shell $(REPOS) get yecwallet-dd base)
LWD_BASE      := $(shell $(REPOS) get lightwalletd-dd base)
WORKSPACE     := $(notdir $(CURDIR))

export DIGIBYTE_PIN YCASH_PIN YECWALLET_PIN LWD_PIN DD_BRANCH DD_BASE WALLET_BASE LWD_BASE

.DEFAULT_GOAL := help
.PHONY: help bootstrap pull status status-short pins diff log spec spec-check

help: ## Show this help
	@printf '\033[1m$(WORKSPACE)\033[0m\n\n'
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) \
		| sort \
		| awk -F':.*?## ' '{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'
	@printf '\n  \033[2mpins: digibyte=%s  ycash=%s  yecwallet=%s  lightwalletd=%s  forks: %s off %s / %s / %s\033[0m\n' \
		'$(DIGIBYTE_PIN)' '$(YCASH_PIN)' '$(YECWALLET_PIN)' '$(LWD_PIN)' '$(DD_BRANCH)' '$(DD_BASE)' '$(WALLET_BASE)' '$(LWD_BASE)'

bootstrap: ## Clone every repo in repos.yaml at its pin and create .venv (SSH=1 for pushable fork clones)
	@scripts/bootstrap.sh $(if $(SSH),--ssh) $(if $(NOVENV),--no-venv) $(if $(DRY),--dry-run)

pull: ## Fast-forward every repo from its remote (never merges, rebases or discards; NOREF=1 skips ref/)
	@scripts/pull.sh $(if $(DRY),--dry-run) $(if $(NOREF),--no-ref) $(if $(SHORT),--short)

status: ## git status across all eight repos, with pin verification and the generated-spec check
	@scripts/repo-status.sh && scripts/extract-spec.sh --check

status-short: ## Same as status, without the per-file listing
	@scripts/repo-status.sh --short && scripts/extract-spec.sh --check

spec: ## Regenerate docs/spec/yellowback-spec.md, the fork copy and both rpc-contract copies from the plan
	@scripts/extract-spec.sh

spec-check: ## Fail if any generated spec/contract copy is stale vs the plan (run by `make status`)
	@scripts/extract-spec.sh --check

pins: ## Print just the current HEAD of each repo (machine-readable)
	@printf '%-14s %-20s %s\n' repo ref commit
	@printf '%-14s %-20s %s\n' workspace \
		"$$(git rev-parse --abbrev-ref HEAD)" "$$(git rev-parse --short HEAD)"
	@printf '%-14s %-20s %s\n' ref/digibyte \
		"$$(git -C ref/digibyte describe --tags 2>/dev/null)" \
		"$$(git -C ref/digibyte rev-parse --short HEAD)"
	@printf '%-14s %-20s %s\n' ref/ycash \
		"$$(git -C ref/ycash describe --tags 2>/dev/null)" \
		"$$(git -C ref/ycash rev-parse --short HEAD)"
	@printf '%-14s %-20s %s\n' ref/yecwallet \
		"$$(git -C ref/yecwallet describe --tags 2>/dev/null)" \
		"$$(git -C ref/yecwallet rev-parse --short HEAD)"
	@printf '%-16s %-20s %s\n' ref/lightwalletd \
		"$$(git -C ref/lightwalletd describe --tags 2>/dev/null || echo 'commit (no tags)')" \
		"$$(git -C ref/lightwalletd rev-parse --short HEAD)"
	@printf '%-14s %-20s %s\n' ycash-dd \
		"$$(git -C ycash-dd rev-parse --abbrev-ref HEAD)" \
		"$$(git -C ycash-dd rev-parse --short HEAD)"
	@printf '%-14s %-20s %s\n' yecwallet-dd \
		"$$(git -C yecwallet-dd rev-parse --abbrev-ref HEAD)" \
		"$$(git -C yecwallet-dd rev-parse --short HEAD)"
	@printf '%-16s %-20s %s\n' lightwalletd-dd \
		"$$(git -C lightwalletd-dd rev-parse --abbrev-ref HEAD)" \
		"$$(git -C lightwalletd-dd rev-parse --short HEAD)"

diff: ## Fork deltas: ycash-dd, yecwallet-dd and lightwalletd-dd vs their -legacy baselines
	@for r in "ycash-dd $(DD_BASE)" "yecwallet-dd $(WALLET_BASE)" "lightwalletd-dd $(LWD_BASE)"; do set -- $$r; \
	printf '\033[1m%s\033[0m\n' "$$1"; \
	out="$$(git -C $$1 diff --stat "$$2...$(DD_BRANCH)")"; \
	if [ -n "$$out" ]; then printf '%s\n' "$$out"; \
	else printf '  \033[2mno changes vs %s\033[0m\n' "$$2"; fi; done

log: ## Commits on each fork branch not in its baseline
	@for r in "ycash-dd $(DD_BASE)" "yecwallet-dd $(WALLET_BASE)" "lightwalletd-dd $(LWD_BASE)"; do set -- $$r; \
	printf '\033[1m%s\033[0m\n' "$$1"; \
	out="$$(git -C $$1 log --oneline --no-merges "$$2..$(DD_BRANCH)")"; \
	if [ -n "$$out" ]; then printf '%s\n' "$$out"; \
	else printf '  \033[2mno commits on %s beyond %s\033[0m\n' '$(DD_BRANCH)' "$$2"; fi; done
