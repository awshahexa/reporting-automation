# Moving the Project to Another Laptop

## What to Transfer

Zip the entire `Sacofa` folder (not just Reporting-Automation):

```powershell
Compress-Archive -Path "C:\Users\Apex-Guest\Documents\Nizam\Sacofa" `
                 -DestinationPath "D:\Sacofa-Full-Project.zip"
```

This preserves cross-references between:
- `Reporting-Automation\` — main project (dashboard, pipeline, verification)
- `NoteTaker\` — meeting recorder app + compiled .exe
- `TSSR-Extractor\` — older standalone TSSR tool
- `TSSR\` — raw TSSR PDFs
- `Test Doc\` — test documents
- `Timeline\` — delivery schedule
- `Presentation Deck\` — PowerPoint files

## On the New Laptop

### 1. Extract and open

```powershell
# Extract to the same path so file references stay valid
Expand-Archive -Path "D:\Sacofa-Full-Project.zip" `
              -DestinationPath "C:\Users\Apex-Guest\Documents\Nizam\"
```

Then in opencode, open the project:
```
code C:\Users\Apex-Guest\Documents\Nizam\Sacofa\Reporting-Automation
```
Or just start opencode and point it at that directory.

### 2. Install Python dependencies

```powershell
python -m pip install --upgrade pip
python -m pip install PyMuPDF openpyxl python-pptx watchdog opencv-python numpy pytesseract Pillow
```

> The bundled `requirements.txt` only lists 4 packages — install all 8 listed above.

### 3. Install Tesseract OCR (for scanned document support)

Download from: https://github.com/UB-Mannheim/tesseract/wiki
- Get the 64-bit installer (e.g. `tesseract-ocr-w64-setup-5.x.x.exe`)
- Install to default path `C:\Program Files\Tesseract-OCR\`
- Add to PATH or pytesseract will auto-detect it

Verify:
```powershell
python -c "import pytesseract; print(pytesseract.get_tesseract_version())"
```

### 4. Start the dashboard

```powershell
cd C:\Users\Apex-Guest\Documents\Nizam\Sacofa\Reporting-Automation
python run.py dashboard
```

Open http://localhost:8080 in a browser.

### 5. Other commands

```powershell
# Submit pipeline status
python run.py sp-submit-status

# Process hot folder
python run.py sp-submit-process

# Watch hot folder continuously
python run.py sp-submit-watch

# Verify a document
python run.py sp-submit-verify

# Verification module
python run.py verify
python run.py verify-status
```

### 6. Resuming with me

Share AGENTS.md (the first message when resuming):

> "Read AGENTS.md and continue. The project is at C:\Users\Apex-Guest\Documents\Nizam\Sacofa\Reporting-Automation"

All context — progress, decisions, file locations, pending items — will restore automatically.

## NoteTaker

The compiled `.exe` is portable at:
`C:\Users\Apex-Guest\Documents\Nizam\Sacofa\NoteTaker\NoteTaker.exe`

Can be run directly on any Windows machine. On first run it downloads the Whisper `large` model (~3 GB).
