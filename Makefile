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
# ycashd 6.20.0 line: both references are commit-pinned (branch heads, no tags); ycash6/librustzcash6 are their forks.
YCASH6_PIN    := $(shell $(REPOS) get ref/ycash6 commit)
LRZ6_PIN      := $(shell $(REPOS) get ref/librustzcash6 commit)
YCASH6_BRANCH := $(shell $(REPOS) get ycash6 branch)
YCASH6_BASE   := $(shell $(REPOS) get ycash6 base)
LRZ6_BRANCH   := $(shell $(REPOS) get librustzcash6 branch)
LRZ6_BASE     := $(shell $(REPOS) get librustzcash6 base)
DD_BRANCH     := $(shell $(REPOS) get ycash-dd branch)
DD_BASE       := $(shell $(REPOS) get ycash-dd base)
WALLET_BASE   := $(shell $(REPOS) get yecwallet-dd base)
LWD_BASE      := $(shell $(REPOS) get lightwalletd-dd base)
# yew is an app repo (role `app`): its own repository on `main`, no baseline, so diff/log skip it.
YEW_BRANCH    := $(shell $(REPOS) get yew branch)
# yolo: ref/yolo is a commit-pinned reference (Perl, yecdev); yolo/ is an app repo (the Rust rewrite).
YOLO_PIN      := $(shell $(REPOS) get ref/yolo commit)
YOLO_BRANCH   := $(shell $(REPOS) get yolo branch)
# chain-viz: an app repo (the real-time chain/mempool/Yellowback visualizer); no reference, no baseline.
CHAINVIZ_BRANCH := $(shell $(REPOS) get chain-viz branch)
# x402-ycash: an app repo (x402 agent payments in YEC and YED); no reference, no baseline.
X402_BRANCH   := $(shell $(REPOS) get x402-ycash branch)
# yb-calibration: an app repo (calibrates the constants baked into Yellowback releases); no reference, no baseline.
YBCAL_BRANCH  := $(shell $(REPOS) get yb-calibration branch)
WORKSPACE     := $(notdir $(CURDIR))

export DIGIBYTE_PIN YCASH_PIN YECWALLET_PIN LWD_PIN YCASH6_PIN LRZ6_PIN YCASH6_BRANCH YCASH6_BASE LRZ6_BRANCH LRZ6_BASE DD_BRANCH DD_BASE WALLET_BASE LWD_BASE YEW_BRANCH YOLO_PIN YOLO_BRANCH CHAINVIZ_BRANCH X402_BRANCH YBCAL_BRANCH

.DEFAULT_GOAL := help
.PHONY: help bootstrap pull status status-short pins diff log spec spec-check

help: ## Show this help
	@printf '\033[1m$(WORKSPACE)\033[0m\n\n'
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) \
		| sort \
		| awk -F':.*?## ' '{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'
	@printf '\n  \033[2mpins: digibyte=%s  ycash=%s  yecwallet=%s  lightwalletd=%s  forks: %s off %s / %s / %s  app: yew on %s  yolo: ref %s, app on %s  chain-viz: app on %s  x402-ycash: app on %s  yb-calibration: app on %s\033[0m\n' \
		'$(DIGIBYTE_PIN)' '$(YCASH_PIN)' '$(YECWALLET_PIN)' '$(LWD_PIN)' '$(DD_BRANCH)' '$(DD_BASE)' '$(WALLET_BASE)' '$(LWD_BASE)' '$(YEW_BRANCH)' '$(YOLO_PIN)' '$(YOLO_BRANCH)' '$(CHAINVIZ_BRANCH)' '$(X402_BRANCH)' '$(YBCAL_BRANCH)'
	@printf '  \033[2mv6.20.0 line: ycash6=%s  librustzcash6=%s  forks: %s off %s / %s\033[0m\n' \
		'$(YCASH6_PIN)' '$(LRZ6_PIN)' '$(YCASH6_BRANCH)' '$(YCASH6_BASE)' '$(LRZ6_BASE)'

bootstrap: ## Clone every repo in repos.yaml at its pin and create .venv (SSH=1 for pushable fork clones)
	@scripts/bootstrap.sh $(if $(SSH),--ssh) $(if $(NOVENV),--no-venv) $(if $(DRY),--dry-run)

pull: ## Fast-forward every repo from its remote (never merges, rebases or discards; NOREF=1 skips ref/)
	@scripts/pull.sh $(if $(DRY),--dry-run) $(if $(NOREF),--no-ref) $(if $(SHORT),--short)

status: ## git status across all eighteen repos: fetches origin, reports ahead/behind, verifies pins and the generated spec (NOFETCH=1 to skip the fetch)
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
	@printf '%-16s %-20s %s\n' ref/ycash6 \
		"$$(git -C ref/ycash6 describe --tags 2>/dev/null || echo 'commit (no tags)')" \
		"$$(git -C ref/ycash6 rev-parse --short HEAD)"
	@printf '%-16s %-20s %s\n' ref/librustzcash6 \
		"$$(git -C ref/librustzcash6 describe --tags 2>/dev/null || echo 'commit (no tags)')" \
		"$$(git -C ref/librustzcash6 rev-parse --short HEAD)"
	@printf '%-14s %-20s %s\n' ycash-dd \
		"$$(git -C ycash-dd rev-parse --abbrev-ref HEAD)" \
		"$$(git -C ycash-dd rev-parse --short HEAD)"
	@printf '%-14s %-20s %s\n' yecwallet-dd \
		"$$(git -C yecwallet-dd rev-parse --abbrev-ref HEAD)" \
		"$$(git -C yecwallet-dd rev-parse --short HEAD)"
	@printf '%-16s %-20s %s\n' lightwalletd-dd \
		"$$(git -C lightwalletd-dd rev-parse --abbrev-ref HEAD)" \
		"$$(git -C lightwalletd-dd rev-parse --short HEAD)"
	@printf '%-16s %-20s %s\n' ycash6 \
		"$$(git -C ycash6 rev-parse --abbrev-ref HEAD)" \
		"$$(git -C ycash6 rev-parse --short HEAD)"
	@printf '%-16s %-20s %s\n' librustzcash6 \
		"$$(git -C librustzcash6 rev-parse --abbrev-ref HEAD)" \
		"$$(git -C librustzcash6 rev-parse --short HEAD)"
	@printf '%-14s %-20s %s\n' yew \
		"$$(git -C yew rev-parse --abbrev-ref HEAD)" \
		"$$(git -C yew rev-parse --short HEAD)"
	@printf '%-14s %-20s %s\n' ref/yolo \
		"$$(git -C ref/yolo describe --tags 2>/dev/null || echo 'commit (no tags)')" \
		"$$(git -C ref/yolo rev-parse --short HEAD)"
	@printf '%-14s %-20s %s\n' yolo \
		"$$(git -C yolo rev-parse --abbrev-ref HEAD)" \
		"$$(git -C yolo rev-parse --short HEAD)"
	@printf '%-14s %-20s %s\n' chain-viz \
		"$$(git -C chain-viz rev-parse --abbrev-ref HEAD)" \
		"$$(git -C chain-viz rev-parse --short HEAD)"
	@printf '%-14s %-20s %s\n' x402-ycash \
		"$$(git -C x402-ycash rev-parse --abbrev-ref HEAD)" \
		"$$(git -C x402-ycash rev-parse --short HEAD)"
	@printf '%-14s %-20s %s\n' yb-calibration \
		"$$(git -C yb-calibration rev-parse --abbrev-ref HEAD)" \
		"$$(git -C yb-calibration rev-parse --short HEAD)"

# Every fork (role `fork` in repos.yaml), each with its own branch and baseline: the v4.5.0 forks are on
# feature/yellowback-price-attest, the v6.20.0 forks (ycash6, librustzcash6) on feature/yellowback.
FORKS := $(shell for r in $$($(REPOS) list); do [ "$$($(REPOS) get $$r role)" = fork ] && printf '%s ' "$$r"; done)

diff: ## Fork deltas: every fork vs its -legacy baseline (the app repos have none)
	@for f in $(FORKS); do b="$$($(REPOS) get $$f base)"; br="$$($(REPOS) get $$f branch)"; \
	printf '\033[1m%s\033[0m\n' "$$f"; \
	out="$$(git -C $$f diff --stat "$$b...$$br")"; \
	if [ -n "$$out" ]; then printf '%s\n' "$$out"; \
	else printf '  \033[2mno changes vs %s\033[0m\n' "$$b"; fi; done

log: ## Commits on each fork branch not in its baseline (the app repos have none)
	@for f in $(FORKS); do b="$$($(REPOS) get $$f base)"; br="$$($(REPOS) get $$f branch)"; \
	printf '\033[1m%s\033[0m\n' "$$f"; \
	out="$$(git -C $$f log --oneline --no-merges "$$b..$$br")"; \
	if [ -n "$$out" ]; then printf '%s\n' "$$out"; \
	else printf '  \033[2mno commits on %s beyond %s\033[0m\n' "$$br" "$$b"; fi; done
