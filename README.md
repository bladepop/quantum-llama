# Quantum Llama

LLM operations assistant for automated code analysis, planning, and execution.

## Project Overview

Quantum Llama is a comprehensive LLM-based system designed to automate code operations. It discovers repositories, analyzes code, generates execution plans, patches code, and verifies changes through a streamlined pipeline.

## Architecture

The project follows a layered architecture:

- **crawler** - Repository discovery, cloning, and AST snapshots
- **planner** - LLM analysis and PlanItem generation
- **engine** - Code patching, git & PR automation
- **verification** - CI result parsing and policy enforcement
- **api** - FastAPI service exposing REST/GraphQL interfaces
- **web** - Next.js 14 dashboard (TypeScript + Tailwind)
- **security** - Secret scanning, redaction, and token rotation
- **cli** - Click CLI entry-points (`ql plan`, `ql exec`)
- **docs** - ADRs, runbooks, and incident playbooks
- **tests** - Unit, integration, and golden-set tests

## Development

### Requirements

- Python 3.11+
- Node.js (for web dashboard)
- pnpm (for web dependencies)

### Setup

```bash
# Clone the repository
git clone https://github.com/bladepop/quantum-llama.git
cd quantum-llama

# Set up Python environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -e ".[dev]"

# Set up web dependencies
cd web
pnpm install
```

### Configuration

The project uses 12-factor app configuration with `.env` files and Pydantic Settings.

## Standards

- Python code: Black (line-length = 88) + Ruff (select = ALL)
- TypeScript/React: Next.js 14, app-router, shadcn/ui, TailwindCSS
- Commits: Conventional Commits format
- Testing: pytest + pytest-cov with ≥ 90% package coverage

## License

[License information] 