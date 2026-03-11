# --- CONFIGURATION ---
$VENV_DIR = "venv"
$SPEC_FILE = "build.spec"

Write-Host "--- Starting Build Process for ThermalLabelStudio (Windows) ---" -ForegroundColor Cyan

# 1. Setup Virtual Environment
Write-Host "[1/4] Setting up virtual environment..." -ForegroundColor Yellow
if (!(Test-Path -Path $VENV_DIR)) {
    python -m venv $VENV_DIR
    Write-Host "Virtual environment created."
}

# 2. Activate Virtual Environment
# Note: This allows the script to run pip inside the venv
$VENV_PATH = "$VENV_DIR\Scripts\Activate.ps1"
& $VENV_PATH

# 3. Install Python Packages
Write-Host "[2/4] Installing requirements..." -ForegroundColor Yellow
python -m pip install --upgrade pip
pip install customtkinter pillow python-escpos numpy pyusb libusb-package pyinstaller

# 4. Run PyInstaller
Write-Host "[3/4] Compiling with PyInstaller..." -ForegroundColor Yellow
if (Test-Path -Path $SPEC_FILE) {
    pyinstaller --noconfirm $SPEC_FILE
} else {
    Write-Host "Warning: Spec file not found. Using manual flags."
    pyinstaller --noconfirm --onefile --windowed `
        --collect-all customtkinter `
        --collect-all libusb_package `
        label_designer.py
}

# 5. Finalize
Write-Host "[4/4] Build complete!" -ForegroundColor Green
Write-Host "------------------------------------------------"
Write-Host "Your executable is in: $(Get-Location)\dist\"
Write-Host "------------------------------------------------"

Deactivate