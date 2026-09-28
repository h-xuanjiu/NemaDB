# NemaDB

<!-- badges: start -->
[![License](https://img.shields.io/badge/license-GPL%20%3E%3D%203-brightgreen.svg?style=flat)](https://www.gnu.org/licenses/gpl-3.0.html)
[![Last Commit](https://img.shields.io/github/last-commit/h-xuanjiu/NemaDB)](https://github.com/h-xuanjiu/NemaDB)
[![Release](https://img.shields.io/github/v/release/h-xuanjiu/NemaDB?color=brightgreen)](https://github.com/h-xuanjiu/NemaDB/releases)
<!-- badges: end -->

A lightweight nematode data utility built with [Flet](https://flet.dev/).

## Features

- **🔍 Search** – Search by Genus (Chinese/Latin) or Family with live suggestions
- **📋 Copy & download** – Select table text, copy complete result sets, or export them as CSV
- **🗃️ Full database view** – Open the record-count badge to browse and download all records
- **📥 Input** – Create samples and record genus abundances with auto-complete
- **💾 Export** – Export to `total_abundance.csv` and `genus_abundance.csv`

## Requirements

- Python 3.10+
- Flet 1.0.1 (installed with the project)



## Files

```
.
├── main.py              # Main application
├── i18n.py              # Interface translations
├── nematode.info.csv    # Reference nematode data
├── assets/              # Application icon
└── pyproject.toml       # Project configuration
```

## Usage

Install the project dependencies, then start the app:

```bash
python -m pip install -e .
python main.py
```

The first source run may take longer while Flet prepares its desktop client.

A pre-built Windows executable can be downloaded and run without installing Python.

To build from source:

```bash
flet build windows
```

## Authors

- **He Yuxuan** – Development & Testing
- **Zhao Jinmeng, Zhang Yudan, Qi Xinyu** – Data Collection & Testing
- **Wang Dong, Miao Yuan** – Supervisors

© All rights reserved by the authors.
