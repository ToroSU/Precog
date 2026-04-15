# 🔮 Precog & 🧭 Dowsing

A lightweight driver / device diagnostic toolkit for Windows platforms.

---

## 📌 Overview

This project consists of two tools:

### 🔮 Precog (Viewer)
- HTML-based visualization tool
- Drag & drop logs to analyze system / driver status
- Focus on:
  - Driver installation state
  - Device matching status
  - Problem detection (PnP / Non-WHQL / No Device)

### 🧭 Dowsing (Collector)
- PowerShell-based log collection tool
- Designed for frontline / remote debugging
- One-click execution to collect system information
- Outputs structured logs for Precog analysis

---

## 🎯 Purpose

Designed to simplify debugging workflow between:

- Frontline engineers  
- QA / DQA  
- RD (Driver / OS integration)  

Instead of:
- Manually running commands  
- Collecting scattered logs  
- Interpreting raw data  

👉 Use **Dowsing** to collect  
👉 Use **Precog** to visualize  

---

## ⚙️ Workflow

1. Run Dowsing on target machine:

    ```powershell
    Dowsing_v1.0.ps1
    ```

2. Collect output logs (zip / folder)  
3. Open Precog (`Precog_v1.0.html`)  
4. Drag logs into browser  
5. Analyze results  

---

## 🔍 Key Features

### Driver Analysis
- Installed / No Device classification  
- Non-WHQL detection  
- Driver Store vs active device mapping  

### Device Matching Insight
- HWID-based matching visualization  
- Supports:
  - PCI devices  
  - ACPI devices  
  - Wildcard matching (`*XXXX`)  

### Problem Detection
- PnP problem devices  
- Driver mismatch / outrank situations  

### Windows System Insight
- OS build / version parsing  
- Secure Boot status  
- BIOS / SKU identification  

---

## 🧠 Naming Concept

- **Precog** → Predict / analyze system state  
- **Dowsing** → Locate hidden signals (logs)  

Inspired by:
- Diagnostic intuition  
- Signal discovery  
- Pattern recognition  

---

## 📁 Project Structure
```
Precog/
├─ Precog_v1.0.html # Viewer
├─ Dowsing_v1.0.ps1 # Collector
├─ README.md
└─ .gitignore
```

---

## 🚀 Roadmap

- [ ] Match-level detection (Exact / Compatible / Wildcard)  
- [ ] Driver ranking visualization  
- [ ] Advanced filtering / search  
- [ ] UI refinement (dashboard mode)  
- [ ] Export analysis report  

---

## 🧪 Status

Current version: **v1.0**

- Basic workflow complete  
- Core driver analysis implemented  
- UI actively being refined  

---

## ⚠️ Notes

- Designed for internal debugging / engineering usage  
- Some data (e.g. registry fields) are filtered for readability  
- Requires Windows environment  

---

## 👤 Author

Toro

---

## 📄 License

Currently not specified