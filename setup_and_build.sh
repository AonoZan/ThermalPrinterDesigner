#!/bin/bash

# --- CONFIGURATION ---
APP_NAME="ThermalLabelStudio"
SPEC_FILE="build.spec"
VENV_DIR="venv"
VID="ea62"
PID="1115"

echo "--- Starting Build & Hardware Setup for $APP_NAME ---"

# 1. System Dependencies
echo "[1/6] Installing system dependencies..."
sudo apt update && sudo apt install -y python3-tk python3-venv build-essential usbutils

# 2. Hardware Permissions (Your Udev Rules)
echo "[2/6] Setting up USB permissions..."
echo "SUBSYSTEM==\"usb\", ATTR{idVendor}==\"$VID\", ATTR{idProduct}==\"$PID\", MODE=\"0666\", GROUP=\"lp\"" | sudo tee /etc/udev/rules.d/99-openlabel.rules
sudo udevadm control --reload-rules
sudo udevadm trigger
sudo usermod -aG lp $USER
echo "Udev rules applied and user added to 'lp' group."

# 3. Setup Virtual Environment
echo "[3/6] Setting up virtual environment..."
[ ! -d "$VENV_DIR" ] && python3 -m venv $VENV_DIR
source $VENV_DIR/bin/activate

# 4. Install Python Packages
echo "[4/6] Installing requirements..."
pip install --upgrade pip
pip install customtkinter pillow python-escpos numpy pyusb libusb-package pyinstaller

# 5. Run PyInstaller
echo "[5/6] Compiling with PyInstaller..."
if [ -f "$SPEC_FILE" ]; then
    pyinstaller --noconfirm "$SPEC_FILE"
else
    pyinstaller --noconfirm --onefile --windowed \
        --collect-all customtkinter \
        --collect-all libusb_package \
        --hidden-import PIL._tkinter_finder \
        label_designer.py
fi

# 6. Verification
echo "[6/6] Verifying Hardware Connection..."
if lsusb -d $VID:$PID > /dev/null; then
    echo "SUCCESS: Printer found on USB bus."
else
    echo "WARNING: Printer ($VID:$PID) not detected. Check cables/power."
fi

echo "------------------------------------------------"
echo "Build complete! Executable is in: $(pwd)/dist/"
echo "NOTE: You may need to log out and back in for 'lp' group changes to take effect."
echo "------------------------------------------------"

deactivate