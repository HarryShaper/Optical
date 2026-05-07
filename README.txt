# 🎬 Optical — Automated Folder Renaming for VFX Workflows

OPTICAL is a desktop application designed for on-set VFX and imaging workflows.

It automatically detects slate text from images using OCR (Optical Character Recognition) and renames folders based on detected slate IDs.

Built with Python, EasyOCR, OpenCV, and PySide6.

---

# ✨ Features

✅ Automatic slate detection from image sequences  
✅ OCR-powered folder renaming  
✅ GPU acceleration support:
- NVIDIA CUDA (Windows)
- Apple Silicon MPS (macOS)

✅ CPU fallback support for unsupported systems  
✅ Cross-platform support:
- Windows
- macOS (Apple Silicon + Intel)

✅ Offline OCR support (no internet required after install)

---

# 💻 Supported Systems

## 🪟 Windows
- Windows 10 / 11
- Recommended:
  - NVIDIA GPU with CUDA support
- CPU mode supported

## 🍎 macOS
- Apple Silicon (M1 / M2 / M3) — Recommended
- Intel Macs — Supported (CPU mode)

---

# 📦 Installation

## 🪟 Windows

1. Download the latest Windows installer
2. Run:

Optical_Windows_Setup.exe

3. Follow the installer steps
4. Launch Optical from the Start Menu or Desktop shortcut

---

## 🍎 macOS

### Apple Silicon
Download:

Optical_macOS_AppleSilicon.dmg

### Intel Mac
Download:

Optical_macOS_Intel.dmg

---

# 🔐 macOS First Launch Security Warning

Because Optical is currently unsigned, macOS may block the application on first launch.

If you see:

“Optical cannot be opened because the developer cannot be verified”

Do the following:

1. Open the .dmg
2. Drag Optical into Applications
3. Open Applications
4. Right-click Optical.app
5. Click:
   Open
6. Click:
   Open Anyway

You only need to do this once.

---

# 🚀 Basic Usage

1. Launch Optical
2. Select a target folder containing image folders
3. Click:

AUTO-RUN

4. Optical will:
- scan the images
- detect slate text
- rename folders automatically

---

# ⚡ Performance Notes

Optical works on all supported systems.

Best performance is achieved with:

- NVIDIA CUDA GPUs (Windows)
- Apple Silicon GPUs using MPS (macOS)

Systems without supported GPU acceleration will run using CPU mode.

---

# 🧪 Sample Data

Sample test data is available on the website for quick testing and evaluation.

---

# 📜 License

Copyright (c) 2026 Harry Shaper

All rights reserved.

This software may not be redistributed, modified, reverse engineered, or used commercially without written permission from the author.

---

# 📧 Contact

harryshaper@gmail.com

---

# 🌐 Website

https://www.shapervfx.com