# ==============================================================================
# MAKRAY — Makefile
# ==============================================================================
# One-line commands for developers. Works on macOS, Linux, and Windows
# (Windows requires WSL, Git Bash, or `make` via Chocolatey/Scoop).
#
# All real work lives in npm scripts (package.json) so Windows-native users
# who don't have `make` can still run `npm run <script>` directly.
# ==============================================================================

# Use bash consistently on all platforms
SHELL := /bin/bash

# Detect OS for any platform-specific behavior
UNAME_S := $(shell uname -s 2>/dev/null || echo Windows)

# ------------------------------------------------------------------------------
# Default target: show help
# ------------------------------------------------------------------------------
.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help message
	@echo ""
	@echo "MAKRAY — available commands"
	@echo "============================"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
	@echo ""
	@echo "Platform detected: $(UNAME_S)"
	@echo ""

# ==============================================================================
# Setup
# ==============================================================================

.PHONY: install
install: ## Install all dependencies
	npm install

.PHONY: setup
setup: install env ## First-time project setup (install + create .env)
	@echo ""
	@echo "✓ Setup complete. Next steps:"
	@echo "    1. Edit .env with your keys"
	@echo "    2. Run: make dev"
	@echo ""

.PHONY: env
env: ## Create .env from .env.example if it doesn't exist
	@if [ ! -f .env ]; then \
		cp .env.example .env && \
		echo "✓ Created .env from template. Edit it with real values."; \
	else \
		echo "✓ .env already exists."; \
	fi

# ==============================================================================
# Development
# ==============================================================================

.PHONY: dev
dev: ## Start development server (Phase 3+)
	npm run dev

.PHONY: build
build: ## Compile TypeScript
	npm run build

.PHONY: typecheck
typecheck: ## Type-check without emitting output
	npx tsc -p tsconfig.json --noEmit

.PHONY: lint
lint: ## Run linter
	npm run lint

.PHONY: format
format: ## Auto-format code with Prettier
	npm run format

.PHONY: clean
clean: ## Remove build artifacts and caches
	rm -rf dist build .next .turbo coverage node_modules/.cache
	@echo "✓ Cleaned build artifacts."

.PHONY: clean-all
clean-all: clean ## Remove everything including node_modules
	rm -rf node_modules
	@echo "✓ Cleaned everything. Run 'make install' to reinstall."

# ==============================================================================
# Testing
# ==============================================================================

.PHONY: test
test: ## Run full test suite
	npm test -- --runInBand

.PHONY: test-watch
test-watch: ## Run tests in watch mode
	npm test -- --watch

.PHONY: test-coverage
test-coverage: ## Run tests with coverage report
	npm test -- --coverage --runInBand

.PHONY: test-integration
test-integration: ## Run only integration tests
	npm test -- --runInBand --testPathPattern='tests/integration'

# ==============================================================================
# Database (Phase 1+)
# ==============================================================================

.PHONY: db-migrate
db-migrate: ## Run pending database migrations
	npm run db:migrate

.PHONY: db-reset
db-reset: ## Reset database (drop + migrate + seed). Destructive.
	npm run db:reset

.PHONY: db-seed
db-seed: ## Seed development data
	npm run db:seed

# ==============================================================================
# Deployment
# ==============================================================================

.PHONY: deploy-staging
deploy-staging: test typecheck ## Deploy to staging (runs tests + typecheck first)
	npm run deploy:staging

.PHONY: deploy-prod
deploy-prod: test typecheck ## Deploy to production
	@echo "Deploying to production..."
	@read -p "Are you sure? [y/N] " confirm && [ "$$confirm" = "y" ] || exit 1
	npm run deploy:prod

# ==============================================================================
# Meta
# ==============================================================================

.PHONY: check
check: typecheck lint test ## Run all checks (typecheck + lint + test)
	@echo ""
	@echo "✓ All checks passed."
	@echo ""

.PHONY: doctor
doctor: ## Diagnose environment
	@echo "MAKRAY environment diagnostic"
	@echo "=============================="
	@echo "Platform:   $(UNAME_S)"
	@echo -n "Node:       "; node --version 2>/dev/null || echo "NOT INSTALLED"
	@echo -n "npm:        "; npm --version 2>/dev/null || echo "NOT INSTALLED"
	@echo -n "Git:        "; git --version 2>/dev/null || echo "NOT INSTALLED"
	@echo -n "TypeScript: "; npx tsc --version 2>/dev/null || echo "NOT INSTALLED"
	@echo ""
	@echo -n ".env:       "; [ -f .env ] && echo "present" || echo "MISSING (run 'make env')"
	@echo -n "node_modules: "; [ -d node_modules ] && echo "present" || echo "MISSING (run 'make install')"
	@echo ""

.PHONY: version
version: ## Print package version
	@node -p "require('./package.json').version"
