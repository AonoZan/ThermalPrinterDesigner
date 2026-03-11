# -*- mode: python ; coding: utf-8 -*-
import sys
import os
import escpos
from PyInstaller.utils.hooks import collect_all

is_win = sys.platform.startswith('win')

# Dynamically find where escpos is installed
escpos_dir = os.path.dirname(escpos.__file__)

# The file might be in the root of escpos or in a capabilities subfolder in your site-packages
# We check both to be safe
cap_source = os.path.join(escpos_dir, 'capabilities.json')
if not os.path.exists(cap_source):
    cap_source = os.path.join(escpos_dir, 'capabilities', 'capabilities.json')

datas = []
binaries = []
hiddenimports = ['PIL._tkinter_finder']

# Map capabilities.json so that it can be found on different systems
if os.path.exists(cap_source):
    datas.append((cap_source, 'escpos/capabilities'))
    datas.append((cap_source, 'escpos'))

# Collect remaining package data
for pkg in ['customtkinter', 'libusb_package', 'escpos']:
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# Remove any potential duplicates from datas to prevent build warnings
datas = list(set(datas))

block_cipher = None

a = Analysis(
    ['label_designer.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ThermalLabelStudio',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False, 
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)