# NemaDB News

## Version 1.2.0 (2026-05-28)

### New Features

- **Search Pagination** – Show search results in pages of 50 rows for smoother browsing
- **Inline Search Action** – Move the search action beside the keyword field
- **Project Rename** – Edit the current project name without clearing saved samples
- **Data Submission** – Add a Help page form for submitting missing or supplemental nematode data by email template
- **Submission Validation** – Validate required fields, email format, CP integers, and mass numeric values
- **Help Page Refresh** – Reorganize Help content into clearer sections covering Search, Input, Drafts, Export, Submit Data, and Data Source
- **Reference Data Update** – Added Chinese genus names for selected nematodes and filled in expected family average mass values

### Files

- `main.py` – Added search pagination, project rename, data submission, validation, and updated Help layout
- `nematode.info.csv` – Added selected Chinese genus names and completed family average mass values
- `pyproject.toml` – Updated project and build versions to 1.2.0
- `NEWS.md` – Added release notes for version 1.2.0

## Version 1.1.0 (2026-05-10)

### New Features

- **Project Name** – Create input projects with a project name and show the current project in the Input page
- **Draft Save/Load** – Save added samples to `.nemadb` draft files and load them later to continue input
- **Project-Prefixed Files** – Use the project name as the prefix for draft and exported CSV filenames
- **Draft Metadata** – Store the project name, app version, draft format, and sample data in `.nemadb` files

### Files

- `main.py` – Added project naming, `.nemadb` draft handling, and project-prefixed export filenames
- `pyproject.toml` – Updated project and build versions to 1.1.0
- `NEWS.md` – Added release notes for version 1.1.0

## Version 1.0.0 (2026-05-07)

### New Features

- **Search** – Search nematode data by Genus (Chinese/Latin) or Family with live suggestions
- **Input** – Create samples and record genus abundances with auto-complete for genus names
- **Export** – Export data to `total_abundance.csv` and `genus_abundance.csv`
- **Welcome Dialog** – Show authors and version info on startup

### Files

- `main.py` – Main Flet application
- `nematode.info.csv` – Reference nematode database
- `pyproject.toml` – Project version metadata
