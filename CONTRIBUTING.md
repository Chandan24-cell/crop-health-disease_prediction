# Contributing to Fieldnote

Thank you for your interest in contributing to the Fieldnote Crop Health platform! We welcome contributions from developers, agronomists, and data scientists worldwide.

---

## Code of Conduct
We are committed to providing a welcoming, inclusive, and harassment-free experience for everyone. Please be respectful and constructive in all interactions.

---

## Development Setup

### 1. Prerequisites
- Python 3.11+
- Node.js 20+ and npm
- Docker and Docker Compose (optional for containerized setup)

### 2. Backend Setup
```bash
# Clone the repository
git clone https://github.com/fieldnote/crop-health-app.git
cd crop-health-app

# Create and activate virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\Activate.ps1
# On Linux/macOS:
source venv/bin/activate

# Install dependencies in editable mode
pip install -e .
pip install pytest pytest-asyncio pytest-cov httpx ruff black mypy
```

### 3. Frontend Setup
```bash
cd frontend
npm install
cd ..
```

### 4. Running the Dev Server
```bash
# Start backend API (with auto-reload)
uvicorn backend.app.main:app --reload --port 8000
```
Open `http://localhost:8000` in your web browser.

---

## Code Quality & Standards

Before opening a pull request, verify that all checks pass:

### 1. Python Linting & Formatting
```bash
ruff check backend scripts
black --check backend scripts
mypy backend
```

### 2. Frontend Linting & Formatting
```bash
cd frontend
npm run lint
npm run format:check
cd ..
```

### 3. Running Backend Tests & Coverage
```bash
pytest --cov=backend --cov-report=term-missing --cov-fail-under=80 backend/tests
```

### 4. Model Regression Gate
```bash
pytest backend/tests/test_model_regression.py -v
```
*Note: Any pull request that drops unweighted macro-F1 on the field evaluation split by more than 1.0 point will fail the CI gate.*

### 5. Playwright E2E Tests
```bash
cd frontend
npx playwright test
cd ..
```

---

## Git Workflow & Pull Requests
1. Create a feature branch: `git checkout -b feat/my-new-feature`
2. Follow Conventional Commits format (`feat:`, `fix:`, `docs:`, `test:`, `perf:`).
3. Ensure all tests pass.
4. Submit a Pull Request targeting `main`.
