# -*- coding: utf-8 -*-

import csv
import json
import math
import urllib.parse
from pathlib import Path
import flet as ft
import sys
import os
import tempfile
import uuid

from i18n import get_language_switch_copy, translate_text as translate_ui_text

os.environ["PYTHONUTF8"] = "1"


def get_version():
    if getattr(sys, 'frozen', False):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).parent

    toml_path = base_path / "pyproject.toml"
    if toml_path.exists():
        try:
            with open(toml_path, "r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if stripped.startswith("version"):
                        parts = stripped.split("=", 1)
                        if len(parts) == 2:
                            val = parts[1].strip()
                            if val.startswith('"') and val.endswith('"'):
                                val = val[1:-1]
                            elif val.startswith("'") and val.endswith("'"):
                                val = val[1:-1]
                            if "#" in val:
                                val = val.split("#")[0].strip()
                            if val:
                                return val
        except Exception:
            pass
    return "unknown"


version = get_version()
# ========== 数据文件路径 ==========
if getattr(sys, 'frozen', False):
    CSV_PATH = Path(sys._MEIPASS) / "nematode.info.csv"
else:
    CSV_PATH = Path(__file__).resolve().parent / "nematode.info.csv"

# ========== 搜索可用列 ==========
SEARCH_COLUMNS = {
    "Genus(zh)": 0,
    "Genus(la)": 1,
    "Family": 2,
}


# ========== 全局数据 ==========
def load_data():
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        headers = next(reader)
        rows = [row for row in reader]
    return headers, rows


HEADERS, ALL_ROWS = load_data()

# 构建属名双向映射
ZH_TO_LA = {}
LA_TO_ZH = {}
for row in ALL_ROWS:
    zh = row[0].strip()
    la = row[1].strip()
    if zh and la:
        ZH_TO_LA[zh] = la
        LA_TO_ZH[la] = zh

ALL_ZH = sorted(ZH_TO_LA.keys())
ALL_LA = sorted({row[1].strip() for row in ALL_ROWS if row[1].strip()})

# ========== 录入数据内存存储 ==========
samples_memory = {}  # {sample_name: total_abundance}
abundances_memory = []  # [(sample_name, genus_la, abundance), ...]
current_project = {"name": ""}
ui_state = {"language": "en", "page_index": 0, "welcome_shown": False}
DRAFT_FORMAT_NAME = "NemaDB Input Draft"
DRAFT_FORMAT_VERSION = 1
DRAFT_FILE_EXTENSION = ".nemadb"

# ========== Visual system ==========
# A restrained neutral palette with one indigo accent keeps the interface calm
# while still making primary actions and the current location obvious.
APP_BG = "#F5F7FB"
SURFACE = "#FFFFFF"
SURFACE_SUBTLE = "#F8FAFC"
TEXT_PRIMARY = "#182230"
TEXT_SECONDARY = "#667085"
TEXT_MUTED = "#98A2B3"
BORDER = "#E4E7EC"
BORDER_STRONG = "#D0D5DD"
PRIMARY = "#5B5CE2"
PRIMARY_DARK = "#4748C7"
PRIMARY_SOFT = "#EEEEFF"
SUCCESS = "#079455"
SUCCESS_SOFT = "#ECFDF3"
DANGER = "#D92D20"
DANGER_SOFT = "#FEF3F2"
LATIN_UI_FONT_FAMILY = "Segoe UI"
ZH_UI_FONT_FAMILY = "Microsoft YaHei"


def load_brand_mark():
    """Load the vector brand mark as bytes for source and packaged runs."""
    if getattr(sys, "frozen", False):
        app_root = Path(sys._MEIPASS)
    else:
        app_root = Path(__file__).resolve().parent
    return (app_root / "assets" / "nemadb-mark.svg").read_bytes()


BRAND_MARK = load_brand_mark()


def brand_mark(size):
    """Return a crisp, accessible NemaDB mark at the requested size."""
    return ft.Image(
        src=BRAND_MARK,
        width=size,
        height=size,
        fit=ft.BoxFit.CONTAIN,
        anti_alias=True,
        semantics_label="NemaDB",
    )


def translate_text(value):
    """Translate an interface string while leaving user and database data untouched."""
    return translate_ui_text(value, ui_state["language"])


def active_ui_font_family():
    """Use one native Windows family at a time to avoid Flutter fallback glitches."""
    return ZH_UI_FONT_FAMILY if ui_state["language"] == "zh" else LATIN_UI_FONT_FAMILY


def app_text_style(**kwargs):
    """Create a text style with a deterministic native Windows font."""
    return ft.TextStyle(
        font_family=active_ui_font_family(),
        **kwargs,
    )


def apply_control_font(control):
    """Apply the selected UI font explicitly to text and editable text controls."""
    if isinstance(control, ft.Text):
        control.font_family = active_ui_font_family()
        control.font_family_fallback = None

    style_attrs = (
        "text_style",
        "label_style",
        "hint_style",
        "helper_style",
        "counter_style",
        "error_style",
        "prefix_style",
        "suffix_style",
    )
    for attr in style_attrs:
        if not hasattr(control, attr):
            continue
        style = getattr(control, attr)
        if style is None:
            if isinstance(control, (ft.TextField, ft.Dropdown)) and attr in (
                "text_style",
                "label_style",
                "hint_style",
            ):
                setattr(control, attr, app_text_style())
        elif isinstance(style, ft.TextStyle):
            setattr(
                control,
                attr,
                style.copy(font_family=active_ui_font_family()),
            )


def localize_control(control, visited=None):
    """Apply the selected language and deterministic fonts to a control tree."""
    if control is None:
        return control
    if visited is None:
        visited = set()
    control_id = id(control)
    if control_id in visited:
        return control
    visited.add(control_id)
    apply_control_font(control)

    if isinstance(control, ft.Text):
        if ui_state["language"] == "zh":
            control.value = translate_text(control.value)

    for attr in ("content", "label", "hint_text", "helper", "tooltip", "title", "text"):
        if not hasattr(control, attr):
            continue
        value = getattr(control, attr)
        if isinstance(value, str):
            if ui_state["language"] == "zh":
                setattr(control, attr, translate_text(value))
        elif value is not None and not isinstance(value, (int, float, bool)):
            localize_control(value, visited)

    for attr in ("controls", "actions", "options", "columns", "rows", "cells"):
        values = getattr(control, attr, None)
        if isinstance(values, (list, tuple)):
            for value in values:
                localize_control(value, visited)
    return control


def build_app_theme():
    """Return the shared Flet 1.0.1 Material 3 theme."""
    button_shape = ft.RoundedRectangleBorder(radius=10)
    button_text = app_text_style(size=12.5, weight=ft.FontWeight.W_600)

    return ft.Theme(
        use_material3=True,
        font_family=active_ui_font_family(),
        color_scheme=ft.ColorScheme(
            primary=PRIMARY,
            on_primary=ft.Colors.WHITE,
            primary_container=PRIMARY_SOFT,
            on_primary_container=PRIMARY_DARK,
            secondary="#697586",
            on_secondary=ft.Colors.WHITE,
            secondary_container="#EEF2F6",
            on_secondary_container="#364152",
            error=DANGER,
            on_error=ft.Colors.WHITE,
            error_container=DANGER_SOFT,
            on_error_container="#912018",
            surface=SURFACE,
            on_surface=TEXT_PRIMARY,
            on_surface_variant=TEXT_SECONDARY,
            outline=BORDER_STRONG,
            outline_variant=BORDER,
            surface_container_low=APP_BG,
            surface_container=SURFACE_SUBTLE,
            surface_container_high="#F2F4F7",
            surface_container_highest="#EAECF0",
        ),
        scaffold_bgcolor=APP_BG,
        canvas_color=APP_BG,
        divider_theme=ft.DividerTheme(color=BORDER, thickness=1, space=1),
        card_theme=ft.CardTheme(
            color=SURFACE,
            elevation=0,
            shape=ft.RoundedRectangleBorder(radius=16),
            margin=0,
        ),
        filled_button_theme=ft.FilledButtonTheme(
            style=ft.ButtonStyle(
                bgcolor={
                    ft.ControlState.DISABLED: "#E4E7EC",
                    ft.ControlState.DEFAULT: PRIMARY,
                },
                color={
                    ft.ControlState.DISABLED: TEXT_MUTED,
                    ft.ControlState.DEFAULT: ft.Colors.WHITE,
                },
                shape=button_shape,
                padding=ft.Padding.symmetric(horizontal=17, vertical=11),
                text_style=button_text,
                elevation=0,
            )
        ),
        outlined_button_theme=ft.OutlinedButtonTheme(
            style=ft.ButtonStyle(
                color={
                    ft.ControlState.DISABLED: TEXT_MUTED,
                    ft.ControlState.DEFAULT: TEXT_PRIMARY,
                },
                shape=button_shape,
                side={
                    ft.ControlState.DISABLED: ft.BorderSide(1, BORDER),
                    ft.ControlState.DEFAULT: ft.BorderSide(1, BORDER_STRONG),
                },
                padding=ft.Padding.symmetric(horizontal=15, vertical=10),
                text_style=button_text,
            )
        ),
        text_button_theme=ft.TextButtonTheme(
            style=ft.ButtonStyle(
                color=PRIMARY,
                shape=button_shape,
                padding=ft.Padding.symmetric(horizontal=13, vertical=10),
                text_style=button_text,
            )
        ),
        icon_button_theme=ft.IconButtonTheme(
            style=ft.ButtonStyle(
                color=TEXT_SECONDARY,
                shape=ft.RoundedRectangleBorder(radius=9),
            )
        ),
        data_table_theme=ft.DataTableTheme(
            heading_row_color=SURFACE_SUBTLE,
            heading_text_style=app_text_style(
                size=12,
                weight=ft.FontWeight.W_600,
                color=TEXT_SECONDARY,
            ),
            data_text_style=app_text_style(size=13, color=TEXT_PRIMARY),
            data_row_min_height=44,
            data_row_max_height=52,
            divider_thickness=1,
            horizontal_margin=18,
            column_spacing=28,
        ),
        dialog_theme=ft.DialogTheme(
            bgcolor=SURFACE,
            elevation=16,
            shadow_color=ft.Colors.BLACK_12,
            shape=ft.RoundedRectangleBorder(radius=20),
        ),
        list_tile_theme=ft.ListTileTheme(
            icon_color=TEXT_SECONDARY,
            text_color=TEXT_PRIMARY,
            shape=ft.RoundedRectangleBorder(radius=10),
            content_padding=ft.Padding.symmetric(horizontal=12, vertical=2),
        ),
        scrollbar_theme=ft.ScrollbarTheme(
            thickness=6,
            radius=10,
            thumb_color=BORDER_STRONG,
            interactive=True,
        ),
        text_theme=ft.TextTheme(
            headline_large=app_text_style(size=28, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
            headline_medium=app_text_style(size=22, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
            title_large=app_text_style(size=18, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
            title_medium=app_text_style(size=15, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
            title_small=app_text_style(size=13, weight=ft.FontWeight.W_600, color=TEXT_SECONDARY),
            body_large=app_text_style(size=14, color=TEXT_SECONDARY),
            body_medium=app_text_style(size=13, color=TEXT_PRIMARY),
            body_small=app_text_style(size=12, color=TEXT_SECONDARY),
            label_large=button_text,
        ),
    )


def surface_panel(content, padding=16, expand=False, bgcolor=SURFACE):
    """Create a consistent low-contrast content surface."""
    return ft.Container(
        content=content,
        padding=padding,
        expand=expand,
        bgcolor=bgcolor,
        border=ft.Border.all(1, BORDER),
        border_radius=14,
        shadow=ft.BoxShadow(
            blur_radius=20,
            spread_radius=-8,
            color="#0A000000",
            offset=ft.Offset(0, 4),
        ),
    )


def section_title(title, subtitle=None, icon=None):
    title_row = []
    if icon is not None:
        title_row.append(
            ft.Container(
                content=ft.Icon(icon, size=18, color=PRIMARY),
                width=34,
                height=34,
                border_radius=10,
                bgcolor=PRIMARY_SOFT,
                alignment=ft.Alignment.CENTER,
            )
        )
    title_row.append(
        ft.Column(
            [
                ft.Text(title, size=15, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
                *([ft.Text(subtitle, size=12, color=TEXT_SECONDARY)] if subtitle else []),
            ],
            spacing=2,
        )
    )
    return ft.Row(
        title_row,
        spacing=10,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def sanitize_filename_prefix(name):
    invalid_chars = '<>:"/\\|?*'
    safe = "".join("_" if char in invalid_chars or ord(char) < 32 else char for char in name.strip())
    safe = "_".join(safe.split())
    safe = safe.strip(" ._")
    return safe or "nemadb_project"


def genus_name_error(value):
    """Return a user-facing error when a genus name contains any digit."""
    text = (value or "").strip()
    if any(character.isdigit() for character in text):
        return translate_text("Numbers are not allowed.")
    return None


def nonnegative_number_error(value):
    """Return a compact live-validation message for non-negative numbers."""
    text = (value or "").strip()
    if not text:
        return None
    try:
        number = float(text)
    except ValueError:
        return translate_text("Invalid number.")
    if not math.isfinite(number):
        return translate_text("Invalid number.")
    if number < 0:
        return translate_text("Must be ≥ 0.")
    return None


def build_draft_payload(project_name, samples, abundances):
    sample_records = []
    for name, total_abundance in samples.items():
        genera = [
            {
                "genus_la": genus_la,
                "genus_zh": LA_TO_ZH.get(genus_la, ""),
                "abundance": abundance,
            }
            for sample_name, genus_la, abundance in abundances
            if sample_name == name
        ]
        sample_records.append(
            {
                "name": name,
                "total_abundance": total_abundance,
                "genera": genera,
            }
        )

    return {
        "format": DRAFT_FORMAT_NAME,
        "version": DRAFT_FORMAT_VERSION,
        "app_version": version,
        "project_name": project_name,
        "samples": sample_records,
    }


def parse_draft_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError("Draft file must contain a JSON object.")
    if payload.get("format") != DRAFT_FORMAT_NAME:
        raise ValueError("This is not a NemaDB input draft file.")
    if payload.get("version") != DRAFT_FORMAT_VERSION:
        raise ValueError(
            f"Unsupported draft version: {payload.get('version')}. "
            f"Expected version {DRAFT_FORMAT_VERSION}."
        )

    sample_entries = payload.get("samples")
    if not isinstance(sample_entries, list):
        raise ValueError("Draft file is missing the samples list.")

    loaded_samples = {}
    loaded_abundances = []
    project_name = payload.get("project_name", "")
    if project_name is None:
        project_name = ""
    if not isinstance(project_name, str):
        raise ValueError("Draft file has an invalid project name.")
    project_name = project_name.strip()

    for sample_index, sample in enumerate(sample_entries, start=1):
        if not isinstance(sample, dict):
            raise ValueError(f"Sample #{sample_index} must be an object.")

        sample_name = sample.get("name")
        if not isinstance(sample_name, str) or not sample_name.strip():
            raise ValueError(f"Sample #{sample_index} is missing a valid name.")
        sample_name = sample_name.strip()
        if sample_name in loaded_samples:
            raise ValueError(f"Duplicate sample name in draft: {sample_name}.")

        try:
            total_abundance = float(sample.get("total_abundance"))
        except (TypeError, ValueError):
            raise ValueError(f"Sample '{sample_name}' has an invalid total abundance.")
        if total_abundance < 0:
            raise ValueError(f"Sample '{sample_name}' has a negative total abundance.")

        genera = sample.get("genera", [])
        if not isinstance(genera, list):
            raise ValueError(f"Sample '{sample_name}' has an invalid genera list.")

        loaded_samples[sample_name] = total_abundance

        for genus_index, genus in enumerate(genera, start=1):
            if not isinstance(genus, dict):
                raise ValueError(
                    f"Genus #{genus_index} in sample '{sample_name}' must be an object."
                )
            genus_la = genus.get("genus_la")
            if not isinstance(genus_la, str) or not genus_la.strip():
                raise ValueError(
                    f"Genus #{genus_index} in sample '{sample_name}' is missing genus_la."
                )
            try:
                abundance = float(genus.get("abundance"))
            except (TypeError, ValueError):
                raise ValueError(
                    f"Genus '{genus_la}' in sample '{sample_name}' has invalid abundance."
                )
            if abundance < 0:
                raise ValueError(
                    f"Genus '{genus_la}' in sample '{sample_name}' has negative abundance."
                )
            if abundance > 0:
                loaded_abundances.append((sample_name, genus_la.strip(), abundance))

    return project_name, loaded_samples, loaded_abundances


# ========== 主函数 ==========
def main(page: ft.Page):
    page.title = "NemaDB"
    page.padding = 0
    page.bgcolor = APP_BG
    page.horizontal_alignment = ft.CrossAxisAlignment.STRETCH
    page.vertical_alignment = ft.MainAxisAlignment.START
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme = build_app_theme()
    page.window.width = 1240
    page.window.height = 820
    page.window.min_width = 960
    page.window.min_height = 680

    def show_localized_dialog(dialog):
        localize_control(dialog)
        page.show_dialog(dialog)

    def toggle_language(e):
        ui_state["language"] = "zh" if ui_state["language"] == "en" else "en"
        page.controls.clear()
        page.overlay.clear()
        page.services.clear()
        main(page)
        page.update()

    # ==================== Search Page ====================
    col_dropdown = ft.Dropdown(
        label="Search by",
        options=[ft.DropdownOption(key=k, text=k) for k in SEARCH_COLUMNS],
        value="Genus(zh)",
        width=190,
        border=ft.OutlineInputBorder(border_radius=10),
        bgcolor=SURFACE,
    )
    keyword_field = ft.TextField(
        label="Keyword",
        hint_text="Search a genus or family",
        prefix_icon=ft.Icons.SEARCH,
        expand=True,
        border=ft.OutlineInputBorder(border_radius=10),
        bgcolor=SURFACE,
        on_change=lambda e: on_keyword_change(e.control.value),
    )
    suggestion_list = ft.ListView(spacing=2, padding=5)
    suggestion_container = ft.Container(
        content=suggestion_list,
        bgcolor=SURFACE,
        border=ft.Border.all(1, BORDER),
        border_radius=10,
        shadow=ft.BoxShadow(blur_radius=16, color=ft.Colors.BLACK_12, offset=ft.Offset(0, 4)),
        height=0,
        animate_size=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
    )
    result_table = ft.DataTable(
        columns=[ft.DataColumn(ft.Text(h)) for h in HEADERS],
        rows=[],
        border=ft.Border.all(1, BORDER),
        border_radius=12,
        horizontal_lines=ft.BorderSide(1, BORDER),
        heading_row_color=SURFACE_SUBTLE,
        data_row_min_height=44,
        data_row_max_height=52,
        column_spacing=28,
        bgcolor=SURFACE,
    )
    SEARCH_PAGE_SIZE = 50
    search_results = {"rows": [], "page": 0}
    result_summary = ft.Text("No results yet.", color=TEXT_SECONDARY, size=13)
    prev_page_btn = ft.OutlinedButton("Previous", icon=ft.Icons.CHEVRON_LEFT, disabled=True)
    next_page_btn = ft.OutlinedButton("Next", icon=ft.Icons.CHEVRON_RIGHT, disabled=True)
    page_indicator = ft.Text("Page 0 / 0", color=TEXT_SECONDARY, size=12)
    pagination_row = ft.Row(
        [prev_page_btn, page_indicator, next_page_btn],
        alignment=ft.MainAxisAlignment.END,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
        wrap=True,
    )
    table_area = ft.Column(
        [ft.Row([result_table], scroll="auto")],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    def render_search_page():
        matched = search_results["rows"]
        total = len(matched)
        if not total:
            result_table.rows = []
            result_summary.value = translate_text("No matching records.")
            page_indicator.value = translate_text("Page 0 / 0")
            prev_page_btn.disabled = True
            next_page_btn.disabled = True
            return

        max_page = (total - 1) // SEARCH_PAGE_SIZE
        search_results["page"] = max(0, min(search_results["page"], max_page))
        current_page = search_results["page"]
        start = current_page * SEARCH_PAGE_SIZE
        end = min(start + SEARCH_PAGE_SIZE, total)
        visible_rows = matched[start:end]

        result_table.rows = [
            ft.DataRow(cells=[ft.DataCell(ft.Text(cell)) for cell in row])
            for row in visible_rows
        ]
        result_summary.value = translate_text(
            f"Showing {start + 1}-{end} of {total} result(s)."
        )
        page_indicator.value = translate_text(f"Page {current_page + 1} / {max_page + 1}")
        prev_page_btn.disabled = current_page == 0
        next_page_btn.disabled = current_page >= max_page

    def on_keyword_change(text):
        text = text.strip().lower()
        if not text:
            suggestion_container.height = 0
            suggestion_list.controls.clear()
            page.update()
            return
        col_idx = SEARCH_COLUMNS[col_dropdown.value]
        seen = set()
        matches = []
        for row in ALL_ROWS:
            val = row[col_idx]
            if text in val.lower() and val not in seen:
                seen.add(val)
                matches.append(val)
        if not matches:
            suggestion_list.controls.clear()
            suggestion_container.height = 0
            page.update()
            return
        matches.sort(key=lambda x: (x.lower().find(text), x.lower()))
        suggestion_list.controls = [
            ft.ListTile(
                title=ft.Text(m),
                on_click=lambda e, val=m: select_suggestion(val),
                dense=True,
            )
            for m in matches
        ]
        suggestion_container.height = min(len(matches) * 40 + 10, 400)
        page.update()

    def select_suggestion(val):
        keyword_field.value = val
        suggestion_container.height = 0
        suggestion_list.controls.clear()
        page.update()

    def do_search(e):
        keyword = keyword_field.value.strip()
        suggestion_container.height = 0
        suggestion_list.controls.clear()
        if not keyword:
            search_results["rows"] = []
            search_results["page"] = 0
            result_table.rows = []
            result_summary.value = translate_text("No results yet.")
            page_indicator.value = translate_text("Page 0 / 0")
            prev_page_btn.disabled = True
            next_page_btn.disabled = True
            page.update()
            return
        col_idx = SEARCH_COLUMNS[col_dropdown.value]
        keyword_lower = keyword.lower()
        search_results["rows"] = [row for row in ALL_ROWS if keyword_lower in row[col_idx].lower()]
        search_results["page"] = 0
        render_search_page()
        page.update()

    keyword_field.on_submit = do_search

    search_btn = ft.FilledButton(
        "Search",
        icon=ft.Icons.FIND_IN_PAGE,
        on_click=do_search,
    )
    search_input_row = ft.Row(
        [keyword_field, search_btn],
        spacing=10,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    def go_to_previous_page(e):
        search_results["page"] -= 1
        render_search_page()
        page.update()

    def go_to_next_page(e):
        search_results["page"] += 1
        render_search_page()
        page.update()

    prev_page_btn.on_click = go_to_previous_page
    next_page_btn.on_click = go_to_next_page

    search_panel = surface_panel(
        ft.Column(
            [
                section_title(
                    "Find a record",
                    "Search the local reference database by Chinese genus, Latin genus, or family.",
                    ft.Icons.SEARCH_ROUNDED,
                ),
                ft.Container(height=4),
                ft.ResponsiveRow(
                    [
                        ft.Column([col_dropdown], col={"xs": 12, "sm": 4, "md": 3}),
                        ft.Column([search_input_row], col={"xs": 12, "sm": 8, "md": 9}),
                    ],
                    spacing=12,
                    run_spacing=12,
                ),
                suggestion_container,
            ],
            spacing=14,
        )
    )

    results_panel = surface_panel(
        ft.Column(
            [
                ft.Row(
                    [
                        section_title(
                            "Results",
                            "Matching records from nematode.info.csv",
                            ft.Icons.TABLE_ROWS_ROUNDED,
                        ),
                        ft.Column(
                            [result_summary, pagination_row],
                            spacing=8,
                            horizontal_alignment=ft.CrossAxisAlignment.END,
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    wrap=True,
                ),
                ft.Container(height=2),
                table_area,
            ],
            expand=True,
            spacing=14,
        ),
        expand=True,
    )

    search_page = ft.Column(
        [search_panel, results_panel],
        expand=True,
        spacing=12,
    )

    # ==================== Input Page ====================
    new_sample_btn = ft.FilledButton("New Sample", icon=ft.Icons.ADD_CARD, disabled=True)
    export_btn = ft.OutlinedButton("Export", icon=ft.Icons.DOWNLOAD, disabled=True)
    save_draft_btn = ft.OutlinedButton("Save Draft", icon=ft.Icons.SAVE, disabled=True)
    load_draft_btn = ft.OutlinedButton("Load Draft", icon=ft.Icons.UPLOAD_FILE)
    project_name_text = ft.Text(
        "No project selected",
        color=TEXT_SECONDARY,
        size=16,
        weight=ft.FontWeight.W_600,
    )
    edit_project_btn = ft.IconButton(
        icon=ft.Icons.EDIT,
        tooltip="Edit project name",
        disabled=True,
    )
    project_header = ft.Container(
        content=ft.Row(
            [
                ft.Row(
                    [
                        ft.Container(
                            content=ft.Icon(ft.Icons.FOLDER_OPEN_ROUNDED, color=PRIMARY, size=20),
                            width=40,
                            height=40,
                            bgcolor=PRIMARY_SOFT,
                            border_radius=11,
                            alignment=ft.Alignment.CENTER,
                        ),
                        ft.Column(
                            [
                                ft.Text("Current project", size=11, color=TEXT_MUTED),
                                project_name_text,
                            ],
                            spacing=1,
                        ),
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                edit_project_btn,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        bgcolor=SURFACE,
        border=ft.Border.all(1, BORDER),
        border_radius=14,
        padding=ft.Padding.symmetric(horizontal=16, vertical=14),
    )
    sample_form = ft.Column()
    sample_list_view = ft.ListView(spacing=8, padding=10, expand=True)

    # 简单对话框辅助函数
    def show_dialog(title, message):
        def close_dlg(e):
            page.pop_dialog()

        dlg = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[ft.TextButton("OK", on_click=close_dlg)],
        )
        show_localized_dialog(dlg)

    def validate_nonnegative_number_field(field):
        field.error = nonnegative_number_error(field.value)
        page.update()

    draft_file_picker = ft.FilePicker()
    page.services.append(draft_file_picker)

    def update_project_label():
        if current_project["name"]:
            project_name_text.value = current_project["name"]
            project_name_text.color = TEXT_PRIMARY
            edit_project_btn.disabled = False
        else:
            project_name_text.value = translate_text("No project selected")
            project_name_text.color = TEXT_SECONDARY
            edit_project_btn.disabled = True

    # ---- 样本列表操作 ----
    def delete_sample(name):
        if name in samples_memory:
            del samples_memory[name]
        new_abund = [(sn, la, a) for sn, la, a in abundances_memory if sn != name]
        abundances_memory.clear()
        abundances_memory.extend(new_abund)
        refresh_sample_list()
        snackbar = ft.SnackBar(ft.Text(f"Sample '{name}' has been deleted."), duration=3000)
        localize_control(snackbar)
        page.overlay.append(snackbar)
        snackbar.open = True
        page.update()

    def confirm_delete_sample(name):
        def on_confirm(e):
            page.pop_dialog()
            delete_sample(name)

        def on_cancel(e):
            page.pop_dialog()

        dlg = ft.AlertDialog(
            title=ft.Text("Delete Sample"),
            content=ft.Text(f"Are you sure you want to delete sample '{name}'?"),
            actions=[
                ft.TextButton("Cancel", on_click=on_cancel),
                ft.TextButton("Delete", on_click=on_confirm,
                              style=ft.ButtonStyle(color=DANGER)),
            ],
        )
        show_localized_dialog(dlg)

    def refresh_sample_list():
        sample_list_view.controls.clear()
        if not samples_memory:
            sample_list_view.controls.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Container(
                                content=ft.Icon(ft.Icons.INVENTORY_2_OUTLINED, color=TEXT_MUTED, size=24),
                                width=44,
                                height=44,
                                border_radius=12,
                                bgcolor=SURFACE_SUBTLE,
                                alignment=ft.Alignment.CENTER,
                            ),
                            ft.Text("No samples yet", weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
                            ft.Text(
                                "Create a project, then add your first sample.",
                                size=12,
                                color=TEXT_SECONDARY,
                            ),
                        ],
                        spacing=6,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=24,
                    alignment=ft.Alignment.CENTER,
                )
            )
        else:
            for name, total_abund in samples_memory.items():
                genus_count = sum(1 for s, _, _ in abundances_memory if s == name)
                card = ft.Container(
                    content=ft.Row(
                        [
                            ft.Row(
                                [
                                    ft.Container(
                                        content=ft.Icon(ft.Icons.SCIENCE_OUTLINED, color=PRIMARY, size=20),
                                        width=40,
                                        height=40,
                                        bgcolor=PRIMARY_SOFT,
                                        border_radius=10,
                                        alignment=ft.Alignment.CENTER,
                                    ),
                                    ft.Column(
                                        [
                                            ft.Text(name, weight=ft.FontWeight.W_600, size=14, color=TEXT_PRIMARY),
                                            ft.Text(
                                                f"{total_abund:g} total abundance  ·  {genus_count} genera",
                                                size=12,
                                                color=TEXT_SECONDARY,
                                            ),
                                        ],
                                        spacing=2,
                                    ),
                                ],
                                spacing=12,
                            ),
                            ft.Row(
                                [
                                    ft.IconButton(
                                        icon=ft.Icons.EDIT_OUTLINED,
                                        tooltip="Edit sample",
                                        on_click=lambda e, n=name: edit_sample(n),
                                    ),
                                    ft.IconButton(
                                        icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
                                        tooltip="Delete sample",
                                        icon_color=DANGER,
                                        on_click=lambda e, n=name: confirm_delete_sample(n),
                                    ),
                                ],
                                spacing=0,
                                alignment=ft.MainAxisAlignment.END,
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    padding=ft.Padding.symmetric(horizontal=14, vertical=12),
                    bgcolor=SURFACE,
                    border=ft.Border.all(1, BORDER),
                    border_radius=12,
                    ink=True,
                    on_click=lambda e, n=name: edit_sample(n),
                )
                sample_list_view.controls.append(card)
        localize_control(sample_list_view)
        page.update()

    # ======== 核心：属名行创建与重复检测 ========
    def create_genus_row(initial_zh="", initial_la="", initial_abund=""):
        uid = str(uuid.uuid4())
        row_key = f"genus_row_{uid}"

        index_text = ft.Text("", width=30, text_align=ft.TextAlign.RIGHT)

        zh_field = ft.TextField(
            label="Genus(zh)", width=200, hint_text="Type to search",
            value=initial_zh, autofocus=False,
            border=ft.OutlineInputBorder(border_radius=10),
        )
        la_field = ft.TextField(
            label="Genus(la)", width=200, hint_text="Type to search",
            value=initial_la, autofocus=False,
            border=ft.OutlineInputBorder(border_radius=10),
        )
        abundance_field = ft.TextField(
            label="Abundance", width=100,
            keyboard_type=ft.KeyboardType.NUMBER,
            value=initial_abund if initial_abund else "0",
            border=ft.OutlineInputBorder(border_radius=10),
        )
        abundance_field.on_change = lambda e: validate_nonnegative_number_field(abundance_field)

        # 中文建议框
        zh_suggestions = ft.ListView(spacing=2, padding=5)
        zh_suggestion_box = ft.Container(
            content=zh_suggestions,
            bgcolor=SURFACE,
            border=ft.Border.all(1, BORDER),
            border_radius=10,
            shadow=ft.BoxShadow(blur_radius=16, color=ft.Colors.BLACK_12, offset=ft.Offset(0, 4)),
            height=0,
            animate_size=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        )
        # 拉丁文建议框
        la_suggestions = ft.ListView(spacing=2, padding=5)
        la_suggestion_box = ft.Container(
            content=la_suggestions,
            bgcolor=SURFACE,
            border=ft.Border.all(1, BORDER),
            border_radius=10,
            shadow=ft.BoxShadow(blur_radius=16, color=ft.Colors.BLACK_12, offset=ft.Offset(0, 4)),
            height=0,
            animate_size=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        )

        # 行内警告容器
        warning_row = ft.Row([], visible=False)

        # 删除按钮（使用 uid 避免闭包错误）
        delete_btn = ft.IconButton(
            icon=ft.Icons.DELETE_OUTLINE_ROUNDED,
            icon_color=DANGER,
            tooltip="Remove row",
            on_click=lambda e, uid=uid: remove_row_by_uid(uid),
        )

        # 中文输入事件
        def on_zh_change(e):
            zh_field.error = genus_name_error(zh_field.value)
            val = zh_field.value.strip().lower()
            if not val:
                zh_suggestion_box.height = 0
                zh_suggestions.controls.clear()
                page.update()
                return
            matches = [name for name in ALL_ZH if val in name.lower()]
            if not matches:
                zh_suggestion_box.height = 0
                zh_suggestions.controls.clear()
            else:
                matches.sort(key=lambda x: (x.lower().find(val), x.lower()))
                zh_suggestions.controls = [
                    ft.ListTile(
                        title=ft.Text(m),
                        on_click=lambda e, name=m: select_zh_suggestion(name),
                        dense=True,
                    )
                    for m in matches
                ]
                zh_suggestion_box.height = min(len(matches) * 40 + 10, 350)
            if zh_field.value.strip() in ZH_TO_LA:
                la_field.value = ZH_TO_LA[zh_field.value.strip()]
                la_field.error = None
            update_all_status()
            page.update()

        def select_zh_suggestion(name):
            zh_field.value = name
            zh_field.error = None
            zh_suggestion_box.height = 0
            zh_suggestions.controls.clear()
            if name in ZH_TO_LA:
                la_field.value = ZH_TO_LA[name]
                la_field.error = None
            update_all_status()
            page.update()

        zh_field.on_change = on_zh_change

        # 拉丁文输入事件
        def on_la_change(e):
            la_field.error = genus_name_error(la_field.value)
            val = la_field.value.strip().lower()
            if not val:
                la_suggestion_box.height = 0
                la_suggestions.controls.clear()
                page.update()
                return
            matches = [name for name in ALL_LA if val in name.lower()]
            if not matches:
                la_suggestion_box.height = 0
                la_suggestions.controls.clear()
            else:
                matches.sort(key=lambda x: (x.lower().find(val), x.lower()))
                la_suggestions.controls = [
                    ft.ListTile(
                        title=ft.Text(m),
                        on_click=lambda e, name=m: select_la_suggestion(name),
                        dense=True,
                    )
                    for m in matches
                ]
                la_suggestion_box.height = min(len(matches) * 40 + 10, 350)
            if la_field.value.strip() in LA_TO_ZH:
                zh_field.value = LA_TO_ZH[la_field.value.strip()]
                zh_field.error = None
            update_all_status()
            page.update()

        def select_la_suggestion(name):
            la_field.value = name
            la_field.error = None
            la_suggestion_box.height = 0
            la_suggestions.controls.clear()
            if name in LA_TO_ZH:
                zh_field.value = LA_TO_ZH[name]
                zh_field.error = None
            update_all_status()
            page.update()

        la_field.on_change = on_la_change

        row_container = ft.Container(
            key=row_key,
            content=ft.Column([
                ft.Row([
                    index_text,
                    ft.Column([zh_field, zh_suggestion_box], spacing=0, width=210),
                    ft.Column([la_field, la_suggestion_box], spacing=0, width=210),
                    abundance_field,
                    delete_btn,
                    warning_row,
                ], vertical_alignment=ft.CrossAxisAlignment.START),
            ]),
            data={"uid": uid},
            padding=ft.Padding.symmetric(horizontal=12, vertical=10),
            bgcolor=SURFACE_SUBTLE,
            border=ft.Border.all(1, BORDER),
            border_radius=12,
        )
        return row_container, uid, index_text, zh_field, la_field, abundance_field, warning_row

    def get_all_genus_rows():
        result = []
        for ctrl in genus_rows.controls:
            uid = ctrl.data["uid"]
            col = ctrl.content
            top_row = col.controls[0]
            index_text = top_row.controls[0]
            zh_col = top_row.controls[1]
            la_col = top_row.controls[2]
            abund_field = top_row.controls[3]
            warning_row = top_row.controls[5]
            zh_field = zh_col.controls[0]
            la_field = la_col.controls[0]
            result.append((ctrl, uid, index_text, zh_field, la_field, abund_field, warning_row))
        return result

    def validate_genus_name_rows(rows):
        """Validate both name fields and mark every invalid row before saving."""
        is_valid = True
        for _, _, _, zh_field, la_field, _, _ in rows:
            zh_field.error = genus_name_error(zh_field.value)
            la_field.error = genus_name_error(la_field.value)
            if zh_field.error or la_field.error:
                is_valid = False

        if not is_valid:
            page.update()
            show_dialog(
                "Invalid Genus Name",
                "Chinese and Latin genus names cannot contain numbers. "
                "Please correct the highlighted fields before saving.",
            )
        return is_valid

    def update_all_status():
        rows = get_all_genus_rows()
        for i, (_, _, idx_text, _, _, _, _) in enumerate(rows, start=1):
            idx_text.value = f"{i}."
        first_occurrence = {}
        for i, (_, uid, _, _, la_field, _, _) in enumerate(rows, start=1):
            la = la_field.value.strip()
            if la:
                if la not in first_occurrence:
                    first_occurrence[la] = (uid, i)
        for i, (_, uid, _, _, la_field, _, warning_row) in enumerate(rows, start=1):
            la = la_field.value.strip()
            if la and la in first_occurrence:
                first_uid, first_idx = first_occurrence[la]
                if first_uid != uid:
                    warning_box = ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=DANGER, size=18),
                            ft.Text(f"Duplicate of #{first_idx}", color=DANGER, size=12,
                                    weight=ft.FontWeight.W_600),
                            ft.TextButton("Merge", on_click=make_merge(uid, first_uid)),
                        ], spacing=10),
                        border=ft.Border.all(1, "#FECDCA"),
                        bgcolor=DANGER_SOFT,
                        border_radius=10,
                        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                    )
                    warning_row.controls = [warning_box]
                    warning_row.visible = True
                    continue
            warning_row.controls.clear()
            warning_row.visible = False

    def make_merge(current_uid, target_uid):
        def merge(e):
            all_rows = get_all_genus_rows()
            target_abund = None
            current_abund = None
            for _, r_uid, _, _, _, r_abund, _ in all_rows:
                if r_uid == target_uid:
                    target_abund = r_abund
                if r_uid == current_uid:
                    current_abund = r_abund
            if target_abund and current_abund:
                try:
                    t_val = float(target_abund.value or 0)
                    c_val = float(current_abund.value or 0)
                    target_abund.value = str(t_val + c_val)
                except ValueError:
                    pass
            remove_row_by_uid(current_uid)

        return merge

    def remove_row_by_uid(uid):
        for ctrl in genus_rows.controls:
            if ctrl.data["uid"] == uid:
                genus_rows.controls.remove(ctrl)
                break
        update_all_status()
        page.update()

    genus_rows = ft.Column()

    # ---- 新建项目 ----
    def create_project(project_name):
        current_project["name"] = project_name
        samples_memory.clear()
        abundances_memory.clear()
        new_sample_btn.disabled = False
        export_btn.disabled = False
        save_draft_btn.disabled = False
        sample_form.controls.clear()
        sample_form_panel.visible = False
        update_project_label()
        refresh_sample_list()
        snackbar = ft.SnackBar(
            ft.Text(f"Project '{project_name}' created. Ready for input."),
            duration=3000,
        )
        localize_control(snackbar)
        page.overlay.append(snackbar)
        snackbar.open = True
        page.update()

    def new_project(e):
        project_name_field = ft.TextField(
            label="Project Name",
            autofocus=True,
            width=360,
            hint_text="e.g. greenhouse_2026_spring",
        )

        def on_cancel(event):
            page.pop_dialog()

        def on_create(event):
            project_name = project_name_field.value.strip()
            if not project_name:
                project_name_field.error = "Please enter a project name."
                page.update()
                return
            page.pop_dialog()
            create_project(project_name)

        dlg = ft.AlertDialog(
            title=ft.Text("New Project"),
            content=project_name_field,
            actions=[
                ft.TextButton("Cancel", on_click=on_cancel),
                ft.FilledButton("Create", on_click=on_create),
            ],
        )
        show_localized_dialog(dlg)

    new_project_btn = ft.FilledButton(
        "New Project",
        icon=ft.Icons.CREATE_NEW_FOLDER_OUTLINED,
        on_click=new_project,
    )

    def edit_project_name(e):
        if not current_project["name"]:
            return

        project_name_field = ft.TextField(
            label="Project Name",
            value=current_project["name"],
            autofocus=True,
            width=360,
        )

        def on_cancel(event):
            page.pop_dialog()

        def on_save(event):
            new_name = project_name_field.value.strip()
            if not new_name:
                project_name_field.error = "Please enter a project name."
                page.update()
                return
            old_name = current_project["name"]
            current_project["name"] = new_name
            update_project_label()
            page.pop_dialog()
            snackbar = ft.SnackBar(
                ft.Text(f"Project renamed from '{old_name}' to '{new_name}'."),
                duration=3000,
            )
            localize_control(snackbar)
            page.overlay.append(snackbar)
            snackbar.open = True
            page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("Edit Project Name"),
            content=project_name_field,
            actions=[
                ft.TextButton("Cancel", on_click=on_cancel),
                ft.FilledButton("Save", on_click=on_save),
            ],
        )
        show_localized_dialog(dlg)

    edit_project_btn.on_click = edit_project_name

    # ---- 新增样本 ----
    def start_new_sample(e):
        nonlocal genus_rows
        new_sample_btn.disabled = True
        sample_form.controls.clear()
        sample_form_panel.visible = True

        sample_name_field = ft.TextField(
            label="Sample Name",
            width=250,
            border=ft.OutlineInputBorder(border_radius=10),
        )
        total_abundance_field = ft.TextField(
            label="Total Abundance (count)", width=250,
            keyboard_type=ft.KeyboardType.NUMBER,
            border=ft.OutlineInputBorder(border_radius=10),
        )
        total_abundance_field.on_change = (
            lambda e: validate_nonnegative_number_field(total_abundance_field)
        )

        genus_rows = ft.Column()

        def add_row():
            row_container, *_ = create_genus_row()
            genus_rows.controls.append(row_container)
            update_all_status()
            page.update()

        add_row()

        add_row_btn = ft.OutlinedButton(
            "Add genus",
            icon=ft.Icons.ADD_ROUNDED,
            on_click=lambda e: add_row(),
        )

        def submit_sample(e):
            rows_data = get_all_genus_rows()
            if not validate_genus_name_rows(rows_data):
                return
            la_list = [la_f.value.strip() for _, _, _, _, la_f, _, _ in rows_data if la_f.value.strip()]
            duplicates = [la for la in set(la_list) if la_list.count(la) > 1]
            if duplicates:
                def on_confirm(e):
                    page.pop_dialog()
                    do_submit()

                def on_cancel(e):
                    page.pop_dialog()

                dup_str = ", ".join(duplicates)
                dlg = ft.AlertDialog(
                    title=ft.Text("Duplicate Genera Detected"),
                    content=ft.Text(
                        f"Duplicates found: {dup_str}.\nIf you continue, only the last occurrence of each duplicate will be kept (former ones discarded).\nDo you want to proceed?"),
                    actions=[
                        ft.TextButton("Cancel", on_click=on_cancel),
                        ft.FilledButton("Proceed", on_click=on_confirm),
                    ],
                )
                show_localized_dialog(dlg)
                return
            do_submit()

        def do_submit():
            sample_name = sample_name_field.value.strip()
            total_str = total_abundance_field.value.strip()

            if not sample_name:
                show_dialog("Missing Sample Name", "Please enter a sample name.")
                return

            if not total_str:
                show_dialog("Missing Total Abundance", "Please enter the total abundance.")
                return
            try:
                total_abundance = float(total_str)
                if not math.isfinite(total_abundance):
                    show_dialog("Invalid Total Abundance", "Total abundance must be a finite number.")
                    return
                if total_abundance < 0:
                    show_dialog("Invalid Total Abundance", "Total abundance cannot be negative.")
                    return
            except ValueError:
                show_dialog("Invalid Total Abundance", "Total abundance must be a number.")
                return

            if sample_name in samples_memory:
                def close_dlg(e):
                    page.pop_dialog()

                dlg = ft.AlertDialog(
                    title=ft.Text("Duplicate Sample Name"),
                    content=ft.Text(f"Sample '{sample_name}' already exists. Please use a different name."),
                    actions=[ft.TextButton("OK", on_click=close_dlg)],
                )
                show_localized_dialog(dlg)
                return

            rows_data = get_all_genus_rows()
            genus_dict = {}
            for _, _, _, _, la_field, abund_field, _ in rows_data:
                la_val = la_field.value.strip()
                abund_str = abund_field.value.strip()
                if not la_val:
                    continue
                if not abund_str:
                    abund_val = 0.0
                else:
                    try:
                        abund_val = float(abund_str)
                        if not math.isfinite(abund_val):
                            show_dialog("Invalid Abundance", f"Abundance for '{la_val}' must be a finite number.")
                            return
                        if abund_val < 0:
                            show_dialog("Invalid Abundance", f"Abundance for '{la_val}' cannot be negative.")
                            return
                    except ValueError:
                        show_dialog("Invalid Abundance", f"Abundance for '{la_val}' is not a valid number.")
                        return
                if abund_val > 0:
                    genus_dict[la_val] = abund_val

            if not genus_dict:
                show_dialog("Empty Sample", "Cannot add a sample with no genera (all abundances are 0 or empty).")
                return

            samples_memory[sample_name] = total_abundance
            new_list = [(sn, la, a) for sn, la, a in abundances_memory if sn != sample_name]
            abundances_memory.clear()
            abundances_memory.extend(new_list)
            for la, abund in genus_dict.items():
                abundances_memory.append((sample_name, la, abund))

            snackbar = ft.SnackBar(ft.Text(f"Sample '{sample_name}' added!"), duration=3000)
            localize_control(snackbar)
            page.overlay.append(snackbar)
            snackbar.open = True
            sample_form.controls.clear()
            sample_form_panel.visible = False
            new_sample_btn.disabled = False
            refresh_sample_list()
            page.update()

        submit_btn = ft.FilledButton("Add Sample", icon=ft.Icons.CHECK_ROUNDED, on_click=submit_sample)

        def cancel_new_sample(e):
            sample_form.controls.clear()
            sample_form_panel.visible = False
            new_sample_btn.disabled = False
            page.update()

        sample_form.controls = [
            section_title(
                "New sample",
                "Add the sample total, then enter one or more genus abundance rows.",
                ft.Icons.ADD_CHART_ROUNDED,
            ),
            ft.Row([sample_name_field, total_abundance_field], wrap=True, spacing=12, run_spacing=12),
            ft.Row(
                [
                    ft.Text("GENUS ABUNDANCES", size=11, weight=ft.FontWeight.W_600, color=TEXT_MUTED),
                    add_row_btn,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            genus_rows,
            ft.Row(
                [
                    ft.OutlinedButton("Cancel", on_click=cancel_new_sample),
                    submit_btn,
                ],
                alignment=ft.MainAxisAlignment.END,
                spacing=10,
            ),
        ]
        localize_control(sample_form)
        page.update()

    new_sample_btn.on_click = start_new_sample

    # ---- 编辑现有样本 ----
    def edit_sample(sample_name):
        nonlocal genus_rows
        sample_form.controls.clear()
        sample_form_panel.visible = True
        new_sample_btn.disabled = False
        total_abund = samples_memory[sample_name]

        sample_name_field = ft.TextField(
            label="Sample Name",
            value=sample_name,
            disabled=True,
            width=250,
            border=ft.OutlineInputBorder(border_radius=10),
        )
        total_abundance_field = ft.TextField(
            label="Total Abundance", value=str(total_abund),
            keyboard_type=ft.KeyboardType.NUMBER,
            width=250,
            border=ft.OutlineInputBorder(border_radius=10),
        )
        total_abundance_field.on_change = (
            lambda e: validate_nonnegative_number_field(total_abundance_field)
        )

        genus_rows = ft.Column()
        existing_records = [(la, abund) for s, la, abund in abundances_memory if s == sample_name]

        def add_edit_row(la="", abund=""):
            row_container, *_ = create_genus_row(
                initial_zh=LA_TO_ZH.get(la, ""), initial_la=la, initial_abund=str(abund) if abund else ""
            )
            genus_rows.controls.append(row_container)
            update_all_status()
            page.update()

        if existing_records:
            for la, abund in existing_records:
                add_edit_row(la, abund)
        else:
            add_edit_row()

        add_row_btn = ft.OutlinedButton(
            "Add genus",
            icon=ft.Icons.ADD_ROUNDED,
            on_click=lambda e: add_edit_row(),
        )

        def submit_edit(e):
            rows_data = get_all_genus_rows()
            if not validate_genus_name_rows(rows_data):
                return
            la_list = [la_f.value.strip() for _, _, _, _, la_f, _, _ in rows_data if la_f.value.strip()]
            duplicates = [la for la in set(la_list) if la_list.count(la) > 1]
            if duplicates:
                def on_confirm(e):
                    page.pop_dialog()
                    do_edit_submit()

                def on_cancel(e):
                    page.pop_dialog()

                dup_str = ", ".join(duplicates)
                dlg = ft.AlertDialog(
                    title=ft.Text("Duplicate Genera Detected"),
                    content=ft.Text(
                        f"Duplicates found: {dup_str}.\nIf you continue, only the last occurrence of each duplicate will be kept.\nDo you want to proceed?"),
                    actions=[
                        ft.TextButton("Cancel", on_click=on_cancel),
                        ft.FilledButton("Proceed", on_click=on_confirm),
                    ],
                )
                show_localized_dialog(dlg)
                return
            do_edit_submit()

        def do_edit_submit():
            new_total_str = total_abundance_field.value.strip()
            if not new_total_str:
                show_dialog("Missing Total Abundance", "Please enter the total abundance.")
                return
            try:
                new_total = float(new_total_str)
                if not math.isfinite(new_total):
                    show_dialog("Invalid Total Abundance", "Total abundance must be a finite number.")
                    return
                if new_total < 0:
                    show_dialog("Invalid Total Abundance", "Total abundance cannot be negative.")
                    return
            except ValueError:
                show_dialog("Invalid Total Abundance", "Total abundance must be a number.")
                return

            rows_data = get_all_genus_rows()
            genus_dict = {}
            for _, _, _, _, la_field, abund_field, _ in rows_data:
                la_val = la_field.value.strip()
                abund_str = abund_field.value.strip()
                if not la_val:
                    continue
                if not abund_str:
                    abund_val = 0.0
                else:
                    try:
                        abund_val = float(abund_str)
                        if not math.isfinite(abund_val):
                            show_dialog("Invalid Abundance", f"Abundance for '{la_val}' must be a finite number.")
                            return
                        if abund_val < 0:
                            show_dialog("Invalid Abundance", f"Abundance for '{la_val}' cannot be negative.")
                            return
                    except ValueError:
                        show_dialog("Invalid Abundance", f"Abundance for '{la_val}' is not a valid number.")
                        return
                if abund_val > 0:
                    genus_dict[la_val] = abund_val

            if not genus_dict:
                show_dialog("Empty Sample", "Cannot save a sample with no genera (all abundances are 0 or empty).")
                return

            samples_memory[sample_name] = new_total
            new_list = [(sn, la, a) for sn, la, a in abundances_memory if sn != sample_name]
            abundances_memory.clear()
            abundances_memory.extend(new_list)
            for la, abund in genus_dict.items():
                abundances_memory.append((sample_name, la, abund))

            snackbar = ft.SnackBar(ft.Text(f"Sample '{sample_name}' updated!"), duration=3000)
            localize_control(snackbar)
            page.overlay.append(snackbar)
            snackbar.open = True
            sample_form.controls.clear()
            sample_form_panel.visible = False
            refresh_sample_list()
            page.update()

        save_btn = ft.FilledButton("Save Changes", icon=ft.Icons.CHECK_ROUNDED, on_click=submit_edit)
        cancel_btn = ft.OutlinedButton("Cancel", on_click=lambda e: (
            sample_form.controls.clear(),
            setattr(sample_form_panel, "visible", False),
            page.update()
        ))

        sample_form.controls = [
            section_title(
                f"Edit {sample_name}",
                "Update the sample total or revise its genus abundance rows.",
                ft.Icons.EDIT_NOTE_ROUNDED,
            ),
            ft.Row([sample_name_field, total_abundance_field], wrap=True, spacing=12, run_spacing=12),
            ft.Row(
                [
                    ft.Text("GENUS ABUNDANCES", size=11, weight=ft.FontWeight.W_600, color=TEXT_MUTED),
                    add_row_btn,
                ],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            genus_rows,
            ft.Row([cancel_btn, save_btn], alignment=ft.MainAxisAlignment.END, spacing=10),
        ]
        localize_control(sample_form)
        page.update()

    # ---- 草稿保存 / 读取 ----
    def apply_loaded_draft(loaded_project_name, loaded_samples, loaded_abundances):
        current_project["name"] = loaded_project_name or "Imported draft"
        samples_memory.clear()
        samples_memory.update(loaded_samples)
        abundances_memory.clear()
        abundances_memory.extend(loaded_abundances)
        sample_form.controls.clear()
        sample_form_panel.visible = False
        new_sample_btn.disabled = False
        export_btn.disabled = False
        save_draft_btn.disabled = False
        update_project_label()
        refresh_sample_list()
        snackbar = ft.SnackBar(
            ft.Text(
                f"Draft loaded for project '{current_project['name']}'. "
                f"{len(samples_memory)} sample(s) ready for input."
            ),
            duration=3000,
        )
        localize_control(snackbar)
        page.overlay.append(snackbar)
        snackbar.open = True
        page.update()

    async def save_draft_clicked(e):
        if not samples_memory:
            show_dialog("No Samples", "There are no saved samples to save as a draft.")
            return

        project_prefix = sanitize_filename_prefix(current_project["name"])
        payload = build_draft_payload(current_project["name"], samples_memory, abundances_memory)
        draft_text = json.dumps(payload, ensure_ascii=False, indent=2)
        draft_bytes = draft_text.encode("utf-8")

        try:
            save_path = await draft_file_picker.save_file(
                dialog_title=translate_text("Save NemaDB Draft"),
                file_name=f"{project_prefix}{DRAFT_FILE_EXTENSION}",
                initial_directory=str(Path.home()),
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=[DRAFT_FILE_EXTENSION.lstrip(".")],
                src_bytes=draft_bytes,
            )
        except Exception as ex:
            show_dialog("Save Draft Failed", f"Could not open the save dialog.\nError: {ex}")
            return

        if not save_path:
            return

        draft_path = Path(save_path)
        if draft_path.suffix.lower() != DRAFT_FILE_EXTENSION:
            if draft_path.suffix:
                draft_path = draft_path.with_suffix(draft_path.suffix + DRAFT_FILE_EXTENSION)
            else:
                draft_path = draft_path.with_suffix(DRAFT_FILE_EXTENSION)

        try:
            draft_path.write_text(draft_text, encoding="utf-8")
            snackbar = ft.SnackBar(
                ft.Text(f"Draft saved to: {draft_path.resolve()}"), duration=3000
            )
            localize_control(snackbar)
            page.overlay.append(snackbar)
            snackbar.open = True
        except (OSError, PermissionError, IOError) as ex:
            show_dialog("Save Draft Failed", f"Could not save the draft file.\nError: {ex}")

        page.update()

    async def load_draft_clicked(e):
        try:
            files = await draft_file_picker.pick_files(
                dialog_title=translate_text("Load NemaDB Draft"),
                initial_directory=str(Path.home()),
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=[DRAFT_FILE_EXTENSION.lstrip(".")],
                allow_multiple=False,
                with_data=True,
            )
        except Exception as ex:
            show_dialog("Load Draft Failed", f"Could not open the file dialog.\nError: {ex}")
            return

        if not files:
            return

        selected_file = files[0]
        try:
            if selected_file.bytes is not None:
                draft_text = selected_file.bytes.decode("utf-8-sig")
            elif selected_file.path:
                draft_text = Path(selected_file.path).read_text(encoding="utf-8-sig")
            else:
                raise ValueError("The selected file could not be read.")
            payload = json.loads(draft_text)
            loaded_project_name, loaded_samples, loaded_abundances = parse_draft_payload(payload)
        except json.JSONDecodeError as ex:
            show_dialog("Invalid Draft File", f"The selected file is not valid JSON.\nError: {ex}")
            return
        except (OSError, PermissionError, IOError, UnicodeDecodeError, ValueError) as ex:
            show_dialog("Invalid Draft File", str(ex))
            return

        has_current_data = bool(samples_memory or abundances_memory or sample_form.controls)
        if not has_current_data:
            apply_loaded_draft(loaded_project_name, loaded_samples, loaded_abundances)
            return

        def on_confirm_load(event):
            page.pop_dialog()
            apply_loaded_draft(loaded_project_name, loaded_samples, loaded_abundances)

        def on_cancel_load(event):
            page.pop_dialog()

        dlg = ft.AlertDialog(
            title=ft.Text("Load Draft"),
            content=ft.Text(
                "Loading a draft will replace the current input data and any unsaved form changes. Continue?"
            ),
            actions=[
                ft.TextButton("Cancel", on_click=on_cancel_load),
                ft.FilledButton("Load Draft", on_click=on_confirm_load),
            ],
        )
        show_localized_dialog(dlg)

    save_draft_btn.on_click = lambda e: page.run_task(save_draft_clicked, e)
    load_draft_btn.on_click = lambda e: page.run_task(load_draft_clicked, e)

    # ---- 导出功能 ----
    def setup_export_button(page, samples_memory, abundances_memory):
        picker = ft.FilePicker()
        page.services.append(picker)

        async def export_clicked(e):
            folder_path = await picker.get_directory_path(
                dialog_title=translate_text("Select Export Folder"),
                initial_directory=str(Path.home())
            )
            if not folder_path:
                return

            out_dir = Path(folder_path)
            project_prefix = sanitize_filename_prefix(current_project["name"])
            try:
                total_file = out_dir / f"{project_prefix}_total_abundance.csv"
                with open(total_file, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["SampleID", "Abundance"])
                    for name, abund in samples_memory.items():
                        writer.writerow([name, abund])

                genus_file = out_dir / f"{project_prefix}_genus_abundance.csv"
                all_genera = sorted({la for _, la, _ in abundances_memory})
                sample_data = {}
                for sname, la, abund in abundances_memory:
                    if sname not in sample_data:
                        sample_data[sname] = {}
                    sample_data[sname][la] = abund

                with open(genus_file, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["SampleID"] + all_genera)
                    for sname in samples_memory.keys():
                        row = [sname]
                        for genus in all_genera:
                            row.append(sample_data.get(sname, {}).get(genus, ""))
                        writer.writerow(row)

                snackbar = ft.SnackBar(
                    ft.Text(f"Files saved to: {out_dir.resolve()}"), duration=3000
                )
                localize_control(snackbar)
                page.overlay.append(snackbar)
                snackbar.open = True

            except (OSError, PermissionError, IOError) as ex:
                show_dialog("Export Failed", f"Could not save files.\nError: {ex}")

            page.update()

        export_btn.on_click = lambda e: page.run_task(export_clicked, e)

    setup_export_button(page, samples_memory, abundances_memory)

    # ---- 数据提交邮件草稿 ----
    SUBMISSION_EMAIL = "heyuxuan0525@outlook.com"
    url_launcher = ft.UrlLauncher()
    page.services.append(url_launcher)
    clipboard = ft.Clipboard()

    def show_snackbar(message):
        snackbar = ft.SnackBar(ft.Text(message), duration=3000)
        localize_control(snackbar)
        page.overlay.append(snackbar)
        snackbar.open = True
        page.update()

    def open_submission_dialog(e):
        field_specs = [
            ("Your name", "your_name", False, False),
            ("Email", "email", False, False),
            ("Institution / Lab", "institution_lab", False, False),
            ("Genus(zh)", "genus_zh", False, False),
            ("Genus(la) *", "genus_la", True, False),
            ("Taxonomy (or only Family) *", "taxonomy", True, False),
            ("Feeding", "feeding", False, False),
            ("CP", "cp", False, False),
            ("Genus.Average.Mass", "genus_average_mass", False, False),
            ("Family.Average.Mass", "family_average_mass", False, False),
            ("Reference / source *", "reference_source", True, True),
            ("Notes", "notes", False, True),
        ]
        fields = {}
        for label, key, _, multiline in field_specs:
            fields[key] = ft.TextField(
                label=label,
                multiline=multiline,
                min_lines=2 if multiline else None,
                max_lines=4 if multiline else None,
            )
        validation_summary = ft.Text(
            "",
            color=DANGER,
            weight=ft.FontWeight.W_600,
            visible=False,
        )

        def validate_fields():
            is_valid = True

            def set_field_error(field, message=None):
                field.error = translate_text(message) if message else None

            for _, key, required, _ in field_specs:
                field = fields[key]
                if required and not (field.value or "").strip():
                    set_field_error(field, "Required")
                    is_valid = False
                else:
                    set_field_error(field)

            email_value = (fields["email"].value or "").strip()
            if email_value:
                email_parts = email_value.split("@")
                if (
                    len(email_parts) != 2
                    or not email_parts[0]
                    or "." not in email_parts[1]
                    or email_parts[1].startswith(".")
                    or email_parts[1].endswith(".")
                ):
                    set_field_error(fields["email"], "Enter a valid email address")
                    is_valid = False

            cp_value = (fields["cp"].value or "").strip()
            if cp_value:
                try:
                    int(cp_value)
                except ValueError:
                    set_field_error(fields["cp"], "Enter an integer")
                    is_valid = False

            for key in ["genus_average_mass", "family_average_mass"]:
                mass_value = (fields[key].value or "").strip()
                if mass_value:
                    try:
                        float(mass_value)
                    except ValueError:
                        set_field_error(fields[key], "Enter a number")
                        is_valid = False
            validation_summary.value = translate_text(
                "Please fix the highlighted fields before submitting."
            )
            validation_summary.visible = not is_valid
            page.update()
            return is_valid

        def build_email_parts():
            values = {key: (field.value or "").strip() for key, field in fields.items()}
            subject_genus = values["genus_la"] or "New record"
            subject = f"NemaDB Data Submission - {subject_genus}"
            body = "\n".join([
                "NemaDB Data Submission",
                "",
                "Contributor",
                f"Your name: {values['your_name']}",
                f"Email: {values['email']}",
                f"Institution / Lab: {values['institution_lab']}",
                "",
                "Data",
                f"Genus(zh): {values['genus_zh']}",
                f"Genus(la): {values['genus_la']}",
                f"Taxonomy (or only Family): {values['taxonomy']}",
                f"Feeding: {values['feeding']}",
                f"CP: {values['cp']}",
                f"Genus.Average.Mass: {values['genus_average_mass']}",
                f"Family.Average.Mass: {values['family_average_mass']}",
                f"Reference / source: {values['reference_source']}",
                f"Notes: {values['notes']}",
                "",
                f"Submitted from NemaDB version: {version}",
            ])
            return subject, body

        async def open_email_draft(event):
            if not validate_fields():
                return
            subject, body = build_email_parts()
            mailto_url = (
                f"mailto:{SUBMISSION_EMAIL}?"
                + urllib.parse.urlencode(
                    {"subject": subject, "body": body},
                    quote_via=urllib.parse.quote,
                )
            )
            try:
                await url_launcher.launch_url(mailto_url)
            except Exception as ex:
                show_dialog(
                    "Could Not Open Email",
                    "NemaDB could not open your default email app.\n"
                    "Please use 'Copy Email Template' instead.\n\n"
                    f"Error: {ex}",
                )

        async def copy_email_template(event):
            if not validate_fields():
                return
            subject, body = build_email_parts()
            template = "\n".join([
                f"To: {SUBMISSION_EMAIL}",
                f"Subject: {subject}",
                "",
                body,
            ])
            await clipboard.set(template)
            show_snackbar("Email template copied to clipboard.")

        def close_dialog(event):
            page.pop_dialog()

        form = ft.Column(
            [
                ft.Text("Contributor", theme_style=ft.TextThemeStyle.TITLE_SMALL),
                fields["your_name"],
                fields["email"],
                fields["institution_lab"],
                ft.Divider(),
                ft.Text("Data", theme_style=ft.TextThemeStyle.TITLE_SMALL),
                fields["genus_zh"],
                fields["genus_la"],
                fields["taxonomy"],
                ft.ResponsiveRow([
                    ft.Column([fields["feeding"]], col={"xs": 12, "sm": 6}),
                    ft.Column([fields["cp"]], col={"xs": 12, "sm": 6}),
                ]),
                ft.ResponsiveRow([
                    ft.Column([fields["genus_average_mass"]], col={"xs": 12, "sm": 6}),
                    ft.Column([fields["family_average_mass"]], col={"xs": 12, "sm": 6}),
                ]),
                fields["reference_source"],
                fields["notes"],
                validation_summary,
            ],
            scroll=ft.ScrollMode.AUTO,
            spacing=8,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

        dlg = ft.AlertDialog(
            title=ft.Text("Submit Data", size=20, weight=ft.FontWeight.W_600),
            content=ft.Container(content=form, width=680, height=520),
            actions=[
                ft.TextButton("Cancel", on_click=close_dialog),
                ft.OutlinedButton(
                    "Copy Email Template",
                    icon=ft.Icons.CONTENT_COPY,
                    on_click=lambda event: page.run_task(copy_email_template, event),
                ),
                ft.FilledButton(
                    "Open Email Draft",
                    icon=ft.Icons.EMAIL,
                    on_click=lambda event: page.run_task(open_email_draft, event),
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        show_localized_dialog(dlg)

    submit_data_btn = ft.FilledButton(
        "Submit Data",
        icon=ft.Icons.EMAIL,
        on_click=open_submission_dialog,
    )

    # ---- Input 页面布局 ----
    project_workspace_panel = surface_panel(
        ft.Column(
            [
                section_title(
                    "Project workspace",
                    "Create or load a project before adding sample abundance data.",
                    ft.Icons.FOLDER_COPY_OUTLINED,
                ),
                project_header,
                ft.Row(
                    [new_project_btn, new_sample_btn, save_draft_btn, load_draft_btn, export_btn],
                    wrap=True,
                    spacing=10,
                    run_spacing=10,
                ),
            ],
            spacing=14,
        )
    )

    samples_panel = surface_panel(
        ft.Column(
            [
                section_title(
                    "Saved samples",
                    "Select a sample to edit its details.",
                    ft.Icons.INVENTORY_2_OUTLINED,
                ),
                ft.Container(
                    content=sample_list_view,
                    height=220,
                    bgcolor=SURFACE_SUBTLE,
                    border=ft.Border.all(1, BORDER),
                    border_radius=12,
                    padding=8,
                ),
            ],
            spacing=14,
        )
    )

    sample_form_panel = surface_panel(sample_form)
    sample_form_panel.visible = False

    input_page = ft.Column(
        [project_workspace_panel, samples_panel, sample_form_panel, ft.Container(height=8)],
        expand=True,
        scroll=ft.ScrollMode.AUTO,
        spacing=12,
    )

    # ==================== Help Page ====================
    def help_section(icon, title, lines):
        return ft.Container(
            content=ft.Row(
                [
                    ft.Container(
                        content=ft.Icon(icon, color=PRIMARY, size=20),
                        width=38,
                        height=38,
                        border_radius=10,
                        bgcolor=PRIMARY_SOFT,
                        alignment=ft.Alignment.CENTER,
                    ),
                    ft.Column(
                        [
                            ft.Text(title, size=14, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
                            ft.Column(
                                [
                                    ft.Row(
                                        [
                                            ft.Container(
                                                content=ft.Container(
                                                    width=5,
                                                    height=5,
                                                    border_radius=3,
                                                    bgcolor=TEXT_MUTED,
                                                ),
                                                width=5,
                                                height=19,
                                                alignment=ft.Alignment.CENTER,
                                            ),
                                            ft.Text(line, color=TEXT_SECONDARY, size=12.5, expand=True),
                                        ],
                                        spacing=9,
                                        vertical_alignment=ft.CrossAxisAlignment.START,
                                    )
                                    for line in lines
                                ],
                                spacing=7,
                            ),
                        ],
                        spacing=8,
                        expand=True,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
            bgcolor=SURFACE,
            border=ft.Border.all(1, BORDER),
            border_radius=14,
            padding=16,
        )

    submit_data_panel = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Container(
                            content=ft.Icon(ft.Icons.OUTBOX_ROUNDED, color=PRIMARY, size=21),
                            width=42,
                            height=42,
                            bgcolor=SURFACE,
                            border_radius=11,
                            alignment=ft.Alignment.CENTER,
                        ),
                        ft.Column(
                            [
                                ft.Text(
                                    "Contribute a record",
                                    size=15,
                                    weight=ft.FontWeight.W_600,
                                    color=TEXT_PRIMARY,
                                ),
                                ft.Text(
                                    "Send missing or corrected nematode data for review.",
                                    color=TEXT_SECONDARY,
                                    size=12.5,
                                ),
                            ],
                            spacing=2,
                            expand=True,
                        ),
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Row(
                    [
                        ft.Text(
                            "The form checks required fields before opening your email client.",
                            color=TEXT_SECONDARY,
                            size=12,
                            expand=True,
                        ),
                        submit_data_btn,
                    ],
                    spacing=12,
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            spacing=12,
            tight=True,
        ),
        bgcolor=PRIMARY_SOFT,
        border=ft.Border.all(1, "#D9D8FF"),
        border_radius=14,
        padding=16,
    )

    help_page = ft.Column([
        surface_panel(
            ft.Row(
                [
                    ft.Container(
                        content=ft.Icon(ft.Icons.MENU_BOOK_ROUNDED, size=26, color=PRIMARY),
                        width=52,
                        height=52,
                        border_radius=14,
                        bgcolor=PRIMARY_SOFT,
                        alignment=ft.Alignment.CENTER,
                    ),
                    ft.Column(
                        [
                            ft.Text("Quick guide", size=18, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
                            ft.Text(
                                "Search reference data and prepare sample abundance files for downstream analysis.",
                                color=TEXT_SECONDARY,
                            ),
                        ],
                        spacing=3,
                        expand=True,
                    ),
                    ft.Container(
                        content=ft.Text(f"v{version}", size=11, color=PRIMARY, weight=ft.FontWeight.W_600),
                        padding=ft.Padding.symmetric(horizontal=10, vertical=6),
                        bgcolor=PRIMARY_SOFT,
                        border_radius=20,
                    ),
                ],
                spacing=14,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        ),
        submit_data_panel,
        help_section(
            ft.Icons.SEARCH,
            "Search",
            [
                "Choose a search column: Genus(zh), Genus(la), or Family.",
                "Type a keyword to see fuzzy-match suggestions, then select a suggestion or keep your own keyword.",
                "Click the search icon at the right side of the keyword field to display matching records.",
                "Results are paginated at 50 rows per page for smoother browsing.",
            ],
        ),
        help_section(
            ft.Icons.INPUT,
            "Input Samples",
            [
                "Click New Project to create a project. This clears any current input data.",
                "Use the edit icon beside the project name if you need to rename the project later.",
                "Click New Sample, then enter Sample Name and Total Abundance.",
                "For each genus, enter Genus(zh) or Genus(la); matching suggestions can auto-fill the paired name.",
                "Enter abundance values, use + to add rows, and use the trash icon to remove rows.",
                "Duplicate genus entries are detected, and you can merge duplicate rows before saving.",
                "Saved samples appear in the list; click a sample card to edit it or use the red trash icon to delete it.",
            ],
        ),
        help_section(
            ft.Icons.SAVE,
            "Drafts",
            [
                "Save Draft writes the current project and saved samples to a .nemadb draft file.",
                "Load Draft restores a saved .nemadb file so you can continue editing later.",
                "Loading a draft replaces the current input data after confirmation.",
            ],
        ),
        help_section(
            ft.Icons.DOWNLOAD,
            "Export",
            [
                "Export asks you to choose an output folder.",
                "NemaDB writes <project>_total_abundance.csv with SampleID and total abundance.",
                "NemaDB also writes <project>_genus_abundance.csv with SampleID as rows and genus names as columns.",
                "The project name is used as the filename prefix, so rename the project before exporting if needed.",
            ],
        ),
        help_section(
            ft.Icons.INFO,
            "Data Source",
            [
                "The built-in reference data is loaded from nematode.info.csv.",
                "Search suggestions and genus name mapping are based on this file.",
                "Submitted data is not added automatically; it should be reviewed before being included in future releases.",
            ],
        ),
        help_section(
            ft.Icons.GROUP_OUTLINED,
            "Credits",
            [
                "He Yuxuan — Development & Testing.",
                "Zhao Jinmeng, Zhang Yudan, Qi Xinyu — Data Collection & Testing.",
                "Wang Dong, Miao Yuan — Supervisors.",
                "Names are listed without a particular order.",
            ],
        ),
        ft.Container(height=8),
    ], expand=True, scroll=ft.ScrollMode.AUTO, spacing=12)



    # ==================== 页面切换 ====================
    content_area = ft.Container(content=search_page, expand=True)

    page_title_text = ft.Text(
        "Database search",
        size=22,
        weight=ft.FontWeight.W_600,
        color=TEXT_PRIMARY,
    )
    page_subtitle_text = ft.Text(
        "Find nematode taxonomy and trait records.",
        size=12.5,
        color=TEXT_SECONDARY,
    )

    pages = [search_page, input_page, help_page]
    page_meta = [
        ("Database search", "Find nematode taxonomy and trait records."),
        ("Sample workspace", "Prepare, save, and export abundance datasets."),
        ("Help & contribution", "Learn the workflow or submit a missing record."),
    ]
    selected_page_index = ui_state["page_index"]
    content_area.content = pages[selected_page_index]
    page_title_text.value, page_subtitle_text.value = page_meta[selected_page_index]

    nav_items = []

    def switch_page(selected_index):
        ui_state["page_index"] = selected_index
        localize_control(pages[selected_index])
        content_area.content = pages[selected_index]
        page_title_text.value = translate_text(page_meta[selected_index][0])
        page_subtitle_text.value = translate_text(page_meta[selected_index][1])
        for index, item in enumerate(nav_items):
            is_selected = index == selected_index
            item.bgcolor = PRIMARY_SOFT if is_selected else ft.Colors.TRANSPARENT
            item.content.controls[0].color = PRIMARY if is_selected else TEXT_SECONDARY
            item.content.controls[1].color = PRIMARY_DARK if is_selected else TEXT_SECONDARY
            item.content.controls[1].weight = (
                ft.FontWeight.W_600 if is_selected else ft.FontWeight.W_500
            )
        page.update()

    def create_nav_item(icon, label, index):
        is_selected = index == selected_page_index
        item = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(icon, size=20, color=PRIMARY if is_selected else TEXT_SECONDARY),
                    ft.Text(
                        label,
                        size=12.5,
                        color=PRIMARY_DARK if is_selected else TEXT_SECONDARY,
                        weight=ft.FontWeight.W_600 if is_selected else ft.FontWeight.W_500,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            width=200,
            height=46,
            padding=ft.Padding.symmetric(horizontal=13, vertical=0),
            bgcolor=PRIMARY_SOFT if is_selected else ft.Colors.TRANSPARENT,
            border_radius=11,
            ink=True,
            data=index,
            on_click=lambda e, page_index=index: switch_page(page_index),
        )
        nav_items.append(item)
        return item

    brand = ft.Container(
        content=ft.Row(
            [
                ft.Container(
                    content=brand_mark(42),
                    width=42,
                    height=42,
                    border_radius=12,
                    alignment=ft.Alignment.CENTER,
                    shadow=ft.BoxShadow(
                        blur_radius=12,
                        spread_radius=-4,
                        color="#405B5CE2",
                        offset=ft.Offset(0, 4),
                    ),
                ),
                ft.Column(
                    [
                        ft.Text("NemaDB", size=16, weight=ft.FontWeight.W_700, color=TEXT_PRIMARY),
                        ft.Text("Research utility", size=11, color=TEXT_MUTED),
                    ],
                    spacing=0,
                ),
            ],
            spacing=11,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        width=204,
        padding=ft.Padding(left=6, top=10, right=0, bottom=18),
    )

    sidebar_footer = ft.Container(
        content=ft.Column(
            [
                ft.Divider(),
                ft.Row(
                    [
                        ft.Container(width=7, height=7, border_radius=4, bgcolor=SUCCESS),
                        ft.Text("Local database", size=11, color=TEXT_SECONDARY),
                        ft.Text(f"v{version}", size=10, color=TEXT_MUTED),
                    ],
                    spacing=7,
                ),
            ],
            spacing=12,
        ),
        width=196,
        padding=ft.Padding(left=8, top=0, right=8, bottom=12),
    )

    sidebar = ft.Container(
        content=ft.Column(
            [
                brand,
                ft.Text(
                    "WORKSPACE",
                    size=10,
                    weight=ft.FontWeight.W_600,
                    color=TEXT_MUTED,
                ),
                ft.Container(height=2),
                create_nav_item(ft.Icons.TRAVEL_EXPLORE_ROUNDED, "Search database", 0),
                create_nav_item(ft.Icons.EDIT_NOTE_ROUNDED, "Sample input", 1),
                create_nav_item(ft.Icons.HELP_OUTLINE_ROUNDED, "Help & contribute", 2),
                ft.Container(expand=True),
                sidebar_footer,
            ],
            spacing=6,
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        width=232,
        padding=ft.Padding(left=10, top=8, right=10, bottom=0),
        bgcolor=SURFACE,
        border=ft.Border.only(right=ft.BorderSide(1, BORDER)),
    )

    database_badge = ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.STORAGE_ROUNDED, size=15, color=PRIMARY),
                ft.Text(f"{len(ALL_ROWS):,} records", size=12, color=TEXT_SECONDARY),
            ],
            spacing=7,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        padding=ft.Padding.symmetric(horizontal=11, vertical=7),
        bgcolor=SURFACE_SUBTLE,
        border=ft.Border.all(1, BORDER),
        border_radius=20,
    )

    language_switch_copy = get_language_switch_copy(ui_state["language"])
    language_button = ft.OutlinedButton(
        language_switch_copy["label"],
        icon=ft.Icons.LANGUAGE_ROUNDED,
        tooltip=language_switch_copy["tooltip"],
        on_click=toggle_language,
    )

    top_bar = ft.Container(
        content=ft.Row(
            [
                ft.Column([page_title_text, page_subtitle_text], spacing=2),
                ft.Row([language_button, database_badge], spacing=10),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        height=80,
        padding=ft.Padding.symmetric(horizontal=20, vertical=12),
        bgcolor=SURFACE,
        border=ft.Border.only(bottom=ft.BorderSide(1, BORDER)),
    )

    main_workspace = ft.Column(
        [
            top_bar,
            ft.Container(
                content=content_area,
                expand=True,
                padding=ft.Padding(left=18, top=14, right=18, bottom=18),
            ),
        ],
        spacing=0,
        expand=True,
    )

    if current_project["name"]:
        new_sample_btn.disabled = False
        export_btn.disabled = False
        save_draft_btn.disabled = False
        update_project_label()

    app_root = ft.Row([sidebar, main_workspace], spacing=0, expand=True)
    localize_control(app_root)
    page.add(app_root)
    refresh_sample_list()

    welcome_dialog = ft.AlertDialog(
        modal=True,
        title=ft.Row(
            [
                ft.Container(
                    content=brand_mark(40),
                    width=40,
                    height=40,
                    border_radius=11,
                    alignment=ft.Alignment.CENTER,
                ),
                ft.Column(
                    [
                        ft.Text("Welcome to NemaDB", size=18, weight=ft.FontWeight.W_600),
                        ft.Text("Nematode reference and sample utility", size=12, color=TEXT_SECONDARY),
                    ],
                    spacing=1,
                    tight=True,
                ),
            ],
            spacing=12,
            tight=True,
        ),
        content=ft.Container(
            width=480,
            content=ft.Column(
                [
                    ft.Text(
                        "Search curated taxonomy records, organize abundance samples, and export analysis-ready files.",
                        size=13,
                        color=TEXT_SECONDARY,
                    ),
                    ft.Container(
                        content=ft.Column(
                            [
                                ft.Text("Project team", size=12, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
                                ft.Text("He Yuxuan — Development & Testing", size=11.5, color=TEXT_SECONDARY),
                                ft.Text(
                                    "Zhao Jinmeng, Zhang Yudan, Qi Xinyu — Data Collection & Testing",
                                    size=11.5,
                                    color=TEXT_SECONDARY,
                                ),
                                ft.Text("Wang Dong, Miao Yuan — Supervisors", size=11.5, color=TEXT_SECONDARY),
                            ],
                            spacing=5,
                            tight=True,
                        ),
                        padding=12,
                        bgcolor=SURFACE_SUBTLE,
                        border=ft.Border.all(1, BORDER),
                        border_radius=11,
                    ),
                    ft.Text(
                        f"Version {version}  ·  © All rights reserved by the authors",
                        size=10.5,
                        color=TEXT_MUTED,
                    ),
                ],
                spacing=12,
                tight=True,
            ),
        ),
        actions=[
            ft.FilledButton(
                "Get started",
                icon=ft.Icons.ARROW_FORWARD_ROUNDED,
                on_click=lambda e: page.pop_dialog(),
            )
        ],
        actions_alignment=ft.MainAxisAlignment.END,
        inset_padding=20,
    )
    if not ui_state["welcome_shown"]:
        ui_state["welcome_shown"] = True
        show_localized_dialog(welcome_dialog)

def run_app():
    """Start NemaDB without letting a packaged build shadow Flet's dev client.

    Flet 1.0.1 looks for ``build/windows/*.exe`` in the current working
    directory before using its normal desktop client.  After a Windows build,
    that makes source runs from PyCharm launch the packaged NemaDB executable
    as the preview client, which exits immediately with code 0.  A neutral
    runtime directory keeps development runs independent from build outputs.
    """
    if getattr(sys, "frozen", False):
        ft.run(main)
        return

    original_cwd = Path.cwd()
    runtime_dir = Path(tempfile.gettempdir()) / "nemadb-flet-dev"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    try:
        os.chdir(runtime_dir)
        ft.run(main)
    finally:
        os.chdir(original_cwd)


if __name__ == "__main__":
    run_app()
