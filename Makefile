# ==============================================================================
# UDS Bundle Development, Compliance & Interactive CLI Troubleshooting Lab
# ==============================================================================

SHELL := /bin/bash
.DEFAULT_GOAL := help

SCENARIO ?= comp-oom-killed
NO_INJECT ?= 0
REVEAL ?= 0

.PHONY: help
help: ## Display available targets for bundle engineering and CLI troubleshooting drills
	@echo "===================================================================================="
	@echo "     UDS BUNDLE ENGINEERING & INTERACTIVE CLI TROUBLESHOOTING LAB                   "
	@echo "===================================================================================="
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-24s\033[0m %s\n", $$1, $$2}'
	@echo "===================================================================================="

# ------------------------------------------------------------------------------
# Bundle Packaging, Air-Gap Verification & Compliance
# ------------------------------------------------------------------------------

.PHONY: build
build: ## Build modular Zarf packages and assemble the UDS bundle (.tar.zst)
	@./scripts/build-bundle.sh

.PHONY: deploy
deploy: ## Deploy the compiled UDS bundle to the active target cluster
	@./scripts/test-deploy.sh

.PHONY: verify-airgap
verify-airgap: ## Run strict zero-egress network isolation checks
	@./scripts/verify-airgap.sh

.PHONY: compliance
compliance: ## Validate live cluster against DoD IL5 NIST 800-53 controls with Lula
	@./scripts/test-compliance.sh

.PHONY: status
status: ## Display cluster nodes, pods, Zarf packages, and services
	@python3 -c 'import scripts.common as c; r = c.run_cmd("kubectl get nodes,pods,svc -A -o wide"); print(r.stdout or r.stderr)'

# ------------------------------------------------------------------------------
# Interactive CLI Troubleshooting Tutor & Chaos Injection Engine
# ------------------------------------------------------------------------------

.PHONY: drill-list
drill-list: ## List all 10 troubleshooting scenarios across Zarf, UDS, K8s, and Lula
	@python3 scripts/drill_manager.py --list

.PHONY: drill-cheatsheet
drill-cheatsheet: ## Display the kubectl, zarf, uds, and lula CLI diagnostic cheat sheet
	@python3 scripts/drill_manager.py --cheatsheet

.PHONY: drill-tutor
drill-tutor: ## Launch interactive 4-phase CLI tutor (Usage: make drill-tutor SCENARIO=<id>)
	@if [ "$(NO_INJECT)" = "1" ]; then \
		python3 scripts/drill_manager.py --tutor "$(SCENARIO)" --no-inject; \
	else \
		python3 scripts/drill_manager.py --tutor "$(SCENARIO)"; \
	fi

.PHONY: drill-mystery
drill-mystery: ## Inject a random blind fault for unassisted CLI diagnosis & remediation
	@python3 scripts/drill_manager.py --mystery

.PHONY: drill-check
drill-check: ## Audit cluster & Lula compliance health (pass REVEAL=1 to reveal mystery fault)
	@if [ "$(REVEAL)" = "1" ]; then \
		python3 scripts/drill_manager.py --check --reveal; \
	else \
		python3 scripts/drill_manager.py --check; \
	fi

.PHONY: drill-inject
drill-inject: ## Inject a specific failure scenario (Usage: make drill-inject SCENARIO=<id>)
	@python3 scripts/drill_manager.py --inject "$(SCENARIO)"

.PHONY: drill-verify
drill-verify: ## Observe live symptoms of a scenario (Usage: make drill-verify SCENARIO=<id>)
	@python3 scripts/drill_manager.py --verify "$(SCENARIO)"

.PHONY: drill-heal
drill-heal: ## Heal a scenario or all scenarios (Usage: make drill-heal SCENARIO=<id|all>)
	@python3 scripts/drill_manager.py --heal "$(SCENARIO)"

.PHONY: lint
lint: ## Lint shell scripts, Python modules, and Zarf/UDS/OSCAL YAML manifests
	@shellcheck scripts/*.sh
	@python3 -m py_compile scripts/*.py tests/*.py
	@python3 -c 'import pathlib, yaml; [list(yaml.safe_load_all(p.read_text())) for pat in ("bundles/*.yaml", "packages/**/*.yaml", "docs/compliance/*.yaml", ".github/workflows/*.yml") for p in sorted(pathlib.Path(".").glob(pat))]'
	@PATH="$$HOME/.local/bin:$$HOME/Projects/uds-platform-prep/payloads/bin:$$PATH"; \
	if command -v lula >/dev/null 2>&1; then \
		lula tools lint -f docs/compliance/oscal-il5.yaml,docs/compliance/assessment-results.yaml; \
	fi
	@echo "✓ All shell scripts, Python modules, and Lula OSCAL / YAML manifests passed lint checks."

.PHONY: test
test: ## Run automated unit and schema tests for the drill engine and OSCAL rules
	@python3 -m unittest discover -v -s tests
