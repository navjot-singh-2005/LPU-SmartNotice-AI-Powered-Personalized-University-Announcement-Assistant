# Setup & Troubleshooting Guide — LPU SmartNotice

## 1. Prerequisites
- **Operating System:** Windows 10/11
- **Python:** Python 3.10+ installed and added to PATH.
- **Terminal:** PowerShell or Command Prompt.

## 2. Windows Environment Setup

```powershell
# Navigate to project directory
cd path\to\LPU-SmartNotice

# Create virtual environment
python -m venv .venv

# Activate virtual environment
.venv\Scripts\Activate.ps1

# Install requirements
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

## 3. Common Issues & Solutions

### Issue 1: `GEMINI_API_KEY is missing from .env`
**Solution:** Ensure `.env` file exists in root directory and contains a valid key:
```env
GEMINI_API_KEY=your_key_here
```

### Issue 2: `Embedding dimension mismatch`
**Cause:** ChromaDB index was created with a different embedding model or dimension setting.
**Solution:** Run index script with `--force-reindex` to rebuild:
```powershell
python -m app.scripts.build_index --limit 25 --force-reindex
```

### Issue 3: `ModuleNotFoundError: No module named 'app'`
**Solution:** Run python scripts using module syntax (`python -m app.scripts....`) from root directory.

---
*Return to [Root README](../README.md)*
