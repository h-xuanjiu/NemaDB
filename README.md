# NemaDB

<!-- badges: start -->
[![License](https://img.shields.io/badge/license-GPL%20%3E%3D%203-brightgreen.svg?style=flat)](https://www.gnu.org/licenses/gpl-3.0.html)
[![Last Commit](https://img.shields.io/github/last-commit/h-xuanjiu/NemaDB)](https://github.com/h-xuanjiu/NemaDB)
[![Release](https://img.shields.io/github/v/release/h-xuanjiu/NemaDB?color=brightgreen)](https://github.com/h-xuanjiu/NemaDB/releases)
<!-- badges: end -->

A lightweight nematode data utility built with [Flet](https://flet.dev/).

## Features

- **🔍 Search** – Search by Genus (Chinese/Latin) or Family with live suggestions
- **📥 Input** – Create samples and record genus abundances with auto-complete
- **💾 Export** – Export to `total_abundance.csv` and `genus_abundance.csv`

## Requirements

- Python 3.8+
- Flet



## Files

```
.
├── main.py              # Main application
├── nematode.info.csv    # Reference nematode data
└── pyproject.toml       # Version info
```

## Usage

```bash
python main.py
```
A pre-built Windows executable is available. Download and run directly without installing Python.

To build from source:

```bash
flet build windows
```

## Authors

- **He Yuxuan** – Development & Testing
- **Zhao Jinmeng, Zhang Yudan, Qi Xinyu** – Data Collection & Testing
- **Wang Dong, Miao Yuan** – Supervisors

© All rights reserved by the authors.
