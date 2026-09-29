# NemaDB News

## Version 1.6.0 (2026-09-30)

### New Features

- **Project Genus Annotations** – Save one deduplicated annotation per recorded Latin genus, including Chinese name, family, feeding type, CP value, genus average fresh weight, and family average fresh weight
- **Stored Relative Abundance** – Calculate each genus abundance divided by its sample genus-abundance sum during data entry and save the result in `.nemadb` drafts
- **Trophic-Group Proportions** – Calculate abundance-weighted Ba, Fu, Pp, Op, and Other proportions during data entry, store them in version 4 `.nemadb` drafts, and export them beside Abundance
- **Single Excel Export** – Export one `.xlsx` workbook in the order Genus Annotations, Abundance, Genus Abundance, and Genus Relative Abundance
- **Excel Numeric Display** – Keep integers unchanged while displaying non-integer values to two decimal places in the Abundance and Genus Relative Abundance sheets without reducing stored precision
- **Draft Compatibility** – Continue loading version 1, 2, and 3 `.nemadb` drafts, enriching annotations and calculating missing relative or trophic-group proportions during loading

### Files

- `main.py` – Added project annotation snapshots, stored relative and trophic-group proportions, version 4 draft handling, legacy draft compatibility, and four-sheet Excel workbook export
- `i18n.py` – Updated Chinese help and export messages
- `pyproject.toml` – Added OpenPyXL 3.0.9+ for workbook generation and updated project and Windows build versions to 1.6.0
- `README.md` – Documented project annotations and the new Excel export
- `NEWS.md` – Added release notes for version 1.6.0
- `tests/test_project_exports.py` – Added coverage for annotations, relative abundance, trophic groups, draft compatibility, workbook layout, and numeric display formats

## Version 1.5.0 (2026-09-29)

### New Features

- **Batch Genus Search** – Search multiple mixed Chinese and Latin genus names at once, with case-insensitive Latin matching, optional trailing 属 for Chinese names, and explicit not-found markers
- **Smart Input Splitting** – Accept mixed line breaks, spaces, tabs, common Chinese or English punctuation, and zero-width characters in pasted lists
- **Positional Pair Check** – Compare two mixed-language lists in order, show matched standard Chinese and Latin names with their complete records, and split mismatches into per-input detail rows
- **Unequal List Handling** – Mark unpaired extra items while retaining any corresponding database information that can be found
- **Persistent Search on Language Switch** – Keep the selected field, keyword, batch inputs, result set, result mode, and current result page when switching between English and Chinese

### Files

- `main.py` – Added intelligent batch parsing, genus lookup and positional comparison, detailed result tables, CSV export support, and persistent Search-page state across language switches
- `i18n.py` – Added Chinese translations for the batch-search interface, comparison statuses, help content, and dynamic result summaries
- `pyproject.toml` – Updated project and Windows build versions to 1.5.0
- `README.md` – Documented batch search and pair checking
- `NEWS.md` – Added release notes for version 1.5.0

## Version 1.4.0 (2026-09-28)

### New Features

- **Copyable Search Results** – Select table text or copy all matching rows with headers for spreadsheet use
- **Search CSV Export** – Download all matching rows as an Excel-compatible CSV file, including results beyond the current page
- **Full Database View** – Click the record count to browse, copy, and download all reference records
- **Search Layout** – Reduce the spacing between the search-field selector and keyword input
- **Chinese Interface** – Add translations and Help instructions for the new search actions
- **Release Link** – Open GitHub Releases from Help to download updates manually
- **Startup Notice** – Show a bilingual initialization message and spinner in the packaged app's startup window, and print the same notice before source runs; explain that the first launch may take longer

### Files

- `main.py` – Added copy and download actions, the full database view, search layout refinements, and an early console startup notice
- `i18n.py` – Added Chinese translations for the new actions and guidance
- `pyproject.toml` – Updated project and Windows build versions to 1.4.0 and configured the bilingual boot screen
- `README.md` – Corrected requirements and startup instructions
- `NEWS.md` – Added release notes for version 1.4.0

## Version 1.3.0 (2026-09-28)

### New Features

- **Flet 1.0.1 Upgrade** – Upgrade the application framework to Flet 1.0.1
- **Non-ASCII Path Support** – Removed the custom build template because Flet 1.0.1 now supports project paths containing non-ASCII characters
- **UI Refresh** – Comprehensively redesign and optimize the interface, layout, spacing, typography, and visual hierarchy
- **Chinese Interface** – Add Chinese localization and an English/Chinese language switch
- **Temporary Application Icon** – Add a custom temporary SVG icon for the sidebar brand area and welcome dialog

### Files

- `main.py` – Updated the interface, localization integration, typography, validation behavior, and application branding
- `i18n.py` – Added English-to-Chinese interface translations and dynamic localization rules
- `assets/nemadb-mark.svg` – Added the temporary NemaDB vector icon
- `pyproject.toml` – Updated the project to version 1.3.0, pinned Flet 1.0.1, and restored the official Flet build workflow
- `flet_build_template/` – Removed the legacy custom build template because it is no longer required with Flet 1.0.1
- `NEWS.md` – Added release notes for version 1.3.0

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
