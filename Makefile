.PHONY: help install install-dev test test-verbose test-coverage test-parallel clean lint format type-check quality pre-commit all coverage-html coverage-report watch-tests

# Default target
.DEFAULT_GOAL := help

# Colors for output
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

# ============================================================================
# Help
# ============================================================================
help: ## Show this help message
	@echo '$(BLUE)Anova Oven SDK - Makefile Commands$(NC)'
	@echo ''
	@echo 'Usage:'
	@echo '  $(GREEN)make$(NC) $(YELLOW)<target>$(NC)'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# ============================================================================
# Installation
# ============================================================================
install: ## Install package dependencies
	@echo "$(BLUE)Installing package dependencies...$(NC)"
	pip install -e .
	@echo "$(GREEN)✓ Package installed$(NC)"

install-dev: ## Install package + development dependencies
	@echo "$(BLUE)Installing development dependencies...$(NC)"
	pip install -e ".[dev]"
	@echo "$(GREEN)✓ Development environment ready$(NC)"

# ============================================================================
# Testing
# ============================================================================
test: ## Run all tests
	@echo "$(BLUE)Running tests...$(NC)"
	pytest tests/
	@echo "$(GREEN)✓ All tests passed$(NC)"

test-verbose: ## Run tests with verbose output
	@echo "$(BLUE)Running tests (verbose)...$(NC)"
	pytest tests/ -vv

test-coverage: ## Run tests with coverage report
	@echo "$(BLUE)Running tests with coverage...$(NC)"
	pytest tests/ --cov=anova_oven_sdk --cov-report=term-missing --cov-report=html --cov-report=xml
	@echo "$(GREEN)✓ Coverage report generated$(NC)"
	@echo "$(YELLOW)View HTML report: htmlcov/index.html$(NC)"

test-parallel: ## Run tests in parallel (faster)
	@echo "$(BLUE)Running tests in parallel...$(NC)"
	pytest tests/ -n auto
	@echo "$(GREEN)✓ Tests completed$(NC)"

test-fast: ## Run tests with minimal output (fast feedback)
	@echo "$(BLUE)Running fast tests...$(NC)"
	pytest tests/ -q --tb=line
	@echo "$(GREEN)✓ Quick test completed$(NC)"

test-failed: ## Re-run only failed tests
	@echo "$(BLUE)Re-running failed tests...$(NC)"
	pytest tests/ --lf

test-watch: ## Watch for changes and re-run tests
	@echo "$(BLUE)Watching for changes...$(NC)"
	@echo "$(YELLOW)Press Ctrl+C to stop$(NC)"
	pytest-watch tests/

# ============================================================================
# Testing - Specific Modules
# ============================================================================
test-models: ## Run tests for models module
	pytest tests/test_models.py -v

test-client: ## Run tests for client module
	pytest tests/test_client.py -v

test-commands: ## Run tests for commands module
	pytest tests/test_commands.py -v

test-oven: ## Run tests for oven module
	pytest tests/test_oven_part1.py tests/test_oven_part2.py -v

test-presets: ## Run tests for presets module
	pytest tests/test_presets.py -v

test-utils: ## Run tests for utils module
	pytest tests/test_utils.py -v

# ============================================================================
# Coverage
# ============================================================================
coverage: test-coverage ## Alias for test-coverage

coverage-html: test-coverage ## Generate and open HTML coverage report
	@echo "$(BLUE)Opening coverage report...$(NC)"
	python -m http.server 8000 --directory htmlcov

coverage-report: ## Show coverage summary
	@echo "$(BLUE)Coverage Summary:$(NC)"
	coverage report

coverage-100: ## Verify 100% coverage (fails if not 100%)
	@echo "$(BLUE)Verifying 100% coverage...$(NC)"
	pytest tests/ --cov=anova_oven_sdk --cov-report=term --cov-fail-under=100
	@echo "$(GREEN)✓ 100% coverage achieved!$(NC)"

# ============================================================================
# Code Quality
# ============================================================================
lint: ## Run linter (ruff)
	@echo "$(BLUE)Running linter...$(NC)"
	ruff check anova_oven_sdk tests
	@echo "$(GREEN)✓ Linting passed$(NC)"

lint-fix: ## Run linter and auto-fix issues
	@echo "$(BLUE)Running linter with auto-fix...$(NC)"
	ruff check --fix anova_oven_sdk tests
	@echo "$(GREEN)✓ Linting issues fixed$(NC)"

format: ## Format code with black
	@echo "$(BLUE)Formatting code...$(NC)"
	black anova_oven_sdk tests
	@echo "$(GREEN)✓ Code formatted$(NC)"

format-check: ## Check if code is formatted
	@echo "$(BLUE)Checking code formatting...$(NC)"
	black --check anova_oven_sdk tests

type-check: ## Run type checker (mypy)
	@echo "$(BLUE)Running type checker...$(NC)"
	mypy anova_oven_sdk
	@echo "$(GREEN)✓ Type checking passed$(NC)"

quality: lint format type-check ## Run all quality checks
	@echo "$(GREEN)✓ All quality checks passed$(NC)"

# ============================================================================
# Pre-commit / CI
# ============================================================================
pre-commit: quality test-coverage ## Run all checks before committing
	@echo "$(GREEN)✓ Pre-commit checks passed$(NC)"
	@echo "$(YELLOW)Ready to commit!$(NC)"

ci: quality coverage-100 ## Run CI pipeline checks
	@echo "$(GREEN)✓ CI checks passed$(NC)"

# ============================================================================
# Cleanup
# ============================================================================
clean: ## Clean build artifacts and cache
	@echo "$(BLUE)Cleaning build artifacts...$(NC)"
	rm -rf build/
	rm -rf dist/
	rm -rf *.egg-info
	rm -rf htmlcov/
	rm -rf .coverage
	rm -rf coverage.xml
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	rm -rf .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type f -name "*.pyd" -delete
	@echo "$(GREEN)✓ Cleaned$(NC)"

clean-all: clean ## Deep clean (including venv)
	@echo "$(BLUE)Deep cleaning...$(NC)"
	rm -rf venv/
	rm -rf .venv/
	@echo "$(GREEN)✓ Deep cleaned$(NC)"

# ============================================================================
# Development
# ============================================================================
dev: install-dev ## Setup development environment
	@echo "$(GREEN)✓ Development environment ready$(NC)"
	@echo "$(YELLOW)Run 'make test' to verify setup$(NC)"

check: quality test-fast ## Quick check before committing
	@echo "$(GREEN)✓ Quick checks passed$(NC)"

all: clean install-dev quality test-coverage ## Full build and test
	@echo "$(GREEN)✓ All tasks completed$(NC)"

verify: coverage-100 ## Verify 100% test coverage
	@echo "$(GREEN)✓ 100% coverage verified$(NC)"

# ============================================================================
# Documentation
# ============================================================================
docs: ## Generate documentation (placeholder)
	@echo "$(BLUE)Documentation generation...$(NC)"
	@echo "$(YELLOW)Not implemented yet$(NC)"

# ============================================================================
# Build
# ============================================================================
build: clean ## Build package
	@echo "$(BLUE)Building package...$(NC)"
	pip install build
	python -m build
	@echo "$(GREEN)✓ Package built in dist/$(NC)"

# ============================================================================
# Info
# ============================================================================
info: ## Show project information
	@echo "$(BLUE)Anova Oven SDK$(NC)"
	@echo "Version: 2025.10.0"
	@echo ""
	@echo "$(YELLOW)Statistics:$(NC)"
	@echo "  Source files: $$(find anova_oven_sdk -name '*.py' | wc -l)"
	@echo "  Test files: $$(find tests -name 'test_*.py' | wc -l)"
	@echo "  Lines of code: $$(find anova_oven_sdk -name '*.py' -exec wc -l {} + | tail -1 | awk '{print $$1}')"
	@echo "  Lines of tests: $$(find tests -name 'test_*.py' -exec wc -l {} + | tail -1 | awk '{print $$1}')"
	@echo ""
	@echo "$(YELLOW)Dependencies:$(NC)"
	@pip list | grep -E "(pytest|pydantic|dynaconf|websockets)" || echo "  Run 'make install-dev' first"

# ============================================================================
# Watch / Development Loop
# ============================================================================
watch: ## Watch for changes and run tests
	@echo "$(BLUE)Watching for changes...$(NC)"
	@echo "$(YELLOW)Press Ctrl+C to stop$(NC)"
	while true; do \
		inotifywait -r -e modify anova_oven_sdk/ tests/ 2>/dev/null || sleep 2; \
		clear; \
		make test-fast; \
	done