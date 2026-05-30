import csv
import json
import urllib.parse
from pathlib import Path
import flet as ft
import sys
import os
import uuid

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
    CSV_PATH = Path("nematode.info.csv")

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
DRAFT_FORMAT_NAME = "NemaDB Input Draft"
DRAFT_FORMAT_VERSION = 1
DRAFT_FILE_EXTENSION = ".nemadb"


def sanitize_filename_prefix(name):
    invalid_chars = '<>:"/\\|?*'
    safe = "".join("_" if char in invalid_chars or ord(char) < 32 else char for char in name.strip())
    safe = "_".join(safe.split())
    safe = safe.strip(" ._")
    return safe or "nemadb_project"


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
    page.padding = 20

    # ==================== Search Page ====================
    col_dropdown = ft.Dropdown(
        label="Search by",
        options=[ft.dropdown.Option(k) for k in SEARCH_COLUMNS],
        value="Genus(zh)",
        width=180,
    )
    keyword_field = ft.TextField(
        label="Keyword",
        prefix_icon=ft.Icons.SEARCH,
        expand=True,
        on_change=lambda e: on_keyword_change(e.control.value),
    )
    suggestion_list = ft.ListView(spacing=2, padding=5)
    suggestion_container = ft.Container(
        content=suggestion_list,
        bgcolor=ft.Colors.WHITE,
        border=ft.Border.all(1, ft.Colors.GREY_400),
        border_radius=5,
        shadow=ft.BoxShadow(blur_radius=5, color=ft.Colors.BLACK12),
        height=0,
        animate_size=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
    )
    result_table = ft.DataTable(
        columns=[ft.DataColumn(ft.Text(h, weight=ft.FontWeight.BOLD)) for h in HEADERS],
        rows=[],
        border=ft.Border.all(1, ft.Colors.GREY_400),
        border_radius=5,
        vertical_lines=ft.BorderSide(1, ft.Colors.GREY_300),
        horizontal_lines=ft.BorderSide(1, ft.Colors.GREY_300),
        heading_row_color=ft.Colors.BLUE_GREY_50,
        data_row_min_height=36,
        column_spacing=20,
    )
    SEARCH_PAGE_SIZE = 50
    search_results = {"rows": [], "page": 0}
    result_summary = ft.Text("No results yet.", color=ft.Colors.GREY_600)
    prev_page_btn = ft.Button("Previous", icon=ft.Icons.CHEVRON_LEFT, disabled=True)
    next_page_btn = ft.Button("Next", icon=ft.Icons.CHEVRON_RIGHT, disabled=True)
    page_indicator = ft.Text("Page 0 / 0", color=ft.Colors.GREY_700)
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
            result_summary.value = "No matching records."
            page_indicator.value = "Page 0 / 0"
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
        result_summary.value = f"Showing {start + 1}-{end} of {total} result(s)."
        page_indicator.value = f"Page {current_page + 1} / {max_page + 1}"
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
            result_summary.value = "No results yet."
            page_indicator.value = "Page 0 / 0"
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

    search_btn = ft.IconButton(
        icon=ft.Icons.FIND_IN_PAGE,
        tooltip="Search",
        on_click=do_search,
    )
    search_input_row = ft.Row(
        [keyword_field, search_btn],
        spacing=6,
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

    search_page = ft.Column([
        ft.Text("Search Nematode Data", theme_style=ft.TextThemeStyle.HEADLINE_MEDIUM),
        ft.Divider(),
        ft.ResponsiveRow([
            ft.Column([col_dropdown], col={"xs": 12, "sm": 3, "md": 2}),
            ft.Column([search_input_row], col={"xs": 12, "sm": 9, "md": 10}),
        ]),
        suggestion_container,
        ft.Divider(),
        ft.Text("Results:", theme_style=ft.TextThemeStyle.TITLE_SMALL),
        ft.Row(
            [result_summary, pagination_row],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            wrap=True,
        ),
        table_area,
    ], expand=True, spacing=10)

    # ==================== Input Page ====================
    new_sample_btn = ft.Button("New Sample", icon=ft.Icons.ADD_CARD, disabled=True)
    export_btn = ft.Button("Export", icon=ft.Icons.DOWNLOAD, disabled=True)
    save_draft_btn = ft.Button("Save Draft", icon=ft.Icons.SAVE, disabled=True)
    load_draft_btn = ft.Button("Load Draft", icon=ft.Icons.UPLOAD_FILE)
    current_project = {"name": ""}
    project_name_text = ft.Text(
        "Project: not created",
        color=ft.Colors.GREY_600,
        size=20,
        weight=ft.FontWeight.BOLD,
    )
    edit_project_btn = ft.IconButton(
        icon=ft.Icons.EDIT,
        tooltip="Edit project name",
        disabled=True,
    )
    project_header = ft.Container(
        content=ft.Row(
            [ft.Icon(ft.Icons.FOLDER_OPEN, color=ft.Colors.BLUE_GREY_600),
             project_name_text,
             edit_project_btn],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            wrap=True,
        ),
        bgcolor=ft.Colors.BLUE_GREY_50,
        border=ft.Border.all(1, ft.Colors.BLUE_GREY_100),
        border_radius=8,
        padding=ft.Padding.symmetric(horizontal=14, vertical=10),
    )
    sample_form = ft.Column()
    sample_list_view = ft.ListView(spacing=8, padding=10, expand=True)

    # 简单对话框辅助函数
    def show_dialog(title, message):
        def close_dlg(e):
            dlg.open = False
            page.update()

        dlg = ft.AlertDialog(
            title=ft.Text(title),
            content=ft.Text(message),
            actions=[ft.TextButton("OK", on_click=close_dlg)],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    draft_file_picker = ft.FilePicker()
    page.services.append(draft_file_picker)

    def update_project_label():
        if current_project["name"]:
            project_name_text.value = f"Project: {current_project['name']}"
            project_name_text.color = ft.Colors.BLUE_GREY_700
            edit_project_btn.disabled = False
        else:
            project_name_text.value = "Project: not created"
            project_name_text.color = ft.Colors.GREY_600
            edit_project_btn.disabled = True

    # ---- 样本列表操作 ----
    def delete_sample(name):
        if name in samples_memory:
            del samples_memory[name]
        new_abund = [(sn, la, a) for sn, la, a in abundances_memory if sn != name]
        abundances_memory.clear()
        abundances_memory.extend(new_abund)
        refresh_sample_list()
        page.snack_bar = ft.SnackBar(ft.Text(f"Sample '{name}' has been deleted."), duration=3000)
        page.snack_bar.open = True
        page.update()

    def confirm_delete_sample(name):
        def on_confirm(e):
            dlg.open = False
            page.update()
            delete_sample(name)

        def on_cancel(e):
            dlg.open = False
            page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("Delete Sample"),
            content=ft.Text(f"Are you sure you want to delete sample '{name}'?"),
            actions=[
                ft.TextButton("Cancel", on_click=on_cancel),
                ft.TextButton("Delete", on_click=on_confirm,
                              style=ft.ButtonStyle(color=ft.Colors.RED)),
            ],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    def refresh_sample_list():
        sample_list_view.controls.clear()
        if not samples_memory:
            sample_list_view.controls.append(
                ft.Container(
                    content=ft.Text("No samples added yet.", italic=True, color=ft.Colors.GREY_500),
                    padding=20,
                    alignment=ft.Alignment(0, 0),
                )
            )
        else:
            for name, total_abund in samples_memory.items():
                genus_count = sum(1 for s, _, _ in abundances_memory if s == name)
                card = ft.Card(
                    content=ft.Container(
                        content=ft.Row([
                            ft.Icon(ft.Icons.SCIENCE, color=ft.Colors.TEAL),
                            ft.Column([
                                ft.Text(name, weight=ft.FontWeight.BOLD, size=16),
                                ft.Text(f"Total abundance: {total_abund}  •  Genera: {genus_count}",
                                        style=ft.TextStyle(color=ft.Colors.GREY_700)),
                            ], spacing=2),
                            ft.Row([
                                ft.IconButton(
                                    icon=ft.Icons.EDIT,
                                    tooltip="Edit sample",
                                    on_click=lambda e, n=name: edit_sample(n),
                                ),
                                ft.IconButton(
                                    icon=ft.Icons.DELETE,
                                    tooltip="Delete sample",
                                    icon_color=ft.Colors.RED_400,
                                    on_click=lambda e, n=name: confirm_delete_sample(n),
                                ),
                            ], alignment=ft.MainAxisAlignment.END),
                        ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER),
                        padding=15,
                        bgcolor=ft.Colors.WHITE,
                        border_radius=10,
                    ),
                    elevation=1,
                    margin=4,
                )
                card.content.on_click = lambda e, n=name: edit_sample(n)
                sample_list_view.controls.append(card)
        page.update()

    # ======== 核心：属名行创建与重复检测 ========
    def create_genus_row(initial_zh="", initial_la="", initial_abund=""):
        uid = str(uuid.uuid4())
        row_key = f"genus_row_{uid}"

        index_text = ft.Text("", width=30, text_align=ft.TextAlign.RIGHT)

        zh_field = ft.TextField(
            label="Genus(zh)", width=200, hint_text="Type to search",
            value=initial_zh, autofocus=False
        )
        la_field = ft.TextField(
            label="Genus(la)", width=200, hint_text="Type to search",
            value=initial_la, autofocus=False
        )
        abundance_field = ft.TextField(
            label="Abundance", width=100,
            keyboard_type=ft.KeyboardType.NUMBER,
            value=initial_abund if initial_abund else "0",
        )

        # 中文建议框
        zh_suggestions = ft.ListView(spacing=2, padding=5)
        zh_suggestion_box = ft.Container(
            content=zh_suggestions,
            bgcolor=ft.Colors.WHITE,
            border=ft.Border.all(1, ft.Colors.GREY_400),
            border_radius=5,
            height=0,
            animate_size=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        )
        # 拉丁文建议框
        la_suggestions = ft.ListView(spacing=2, padding=5)
        la_suggestion_box = ft.Container(
            content=la_suggestions,
            bgcolor=ft.Colors.WHITE,
            border=ft.Border.all(1, ft.Colors.GREY_400),
            border_radius=5,
            height=0,
            animate_size=ft.Animation(200, ft.AnimationCurve.EASE_OUT),
        )

        # 行内警告容器
        warning_row = ft.Row([], visible=False)

        # 删除按钮（使用 uid 避免闭包错误）
        delete_btn = ft.IconButton(icon=ft.Icons.DELETE, on_click=lambda e, uid=uid: remove_row_by_uid(uid))

        # 中文输入事件
        def on_zh_change(e):
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
            update_all_status()
            page.update()

        def select_zh_suggestion(name):
            zh_field.value = name
            zh_suggestion_box.height = 0
            zh_suggestions.controls.clear()
            if name in ZH_TO_LA:
                la_field.value = ZH_TO_LA[name]
            update_all_status()
            page.update()

        zh_field.on_change = on_zh_change

        # 拉丁文输入事件
        def on_la_change(e):
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
            update_all_status()
            page.update()

        def select_la_suggestion(name):
            la_field.value = name
            la_suggestion_box.height = 0
            la_suggestions.controls.clear()
            if name in LA_TO_ZH:
                zh_field.value = LA_TO_ZH[name]
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
            data={"uid": uid}
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
                            ft.Text(f"Duplicate of #{first_idx}", color=ft.Colors.RED, size=16,
                                    weight=ft.FontWeight.BOLD),
                            ft.TextButton("Merge", on_click=make_merge(uid, first_uid)),
                        ], spacing=10),
                        border=ft.Border.all(2, ft.Colors.RED),
                        bgcolor=ft.Colors.RED_50,
                        border_radius=8,
                        padding=ft.Padding.symmetric(horizontal=10, vertical=5),
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
        update_project_label()
        refresh_sample_list()
        page.snack_bar = ft.SnackBar(
            ft.Text(f"Project '{project_name}' created. Ready for input."),
            duration=3000,
        )
        page.snack_bar.open = True
        page.update()

    def new_project(e):
        project_name_field = ft.TextField(
            label="Project Name",
            autofocus=True,
            width=360,
            hint_text="e.g. greenhouse_2026_spring",
        )

        def on_cancel(event):
            dlg.open = False
            page.update()

        def on_create(event):
            project_name = project_name_field.value.strip()
            if not project_name:
                project_name_field.error_text = "Please enter a project name."
                page.update()
                return
            dlg.open = False
            page.update()
            create_project(project_name)

        dlg = ft.AlertDialog(
            title=ft.Text("New Project"),
            content=project_name_field,
            actions=[
                ft.TextButton("Cancel", on_click=on_cancel),
                ft.TextButton("Create", on_click=on_create),
            ],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    new_project_btn = ft.Button("New Project", icon=ft.Icons.CREATE_NEW_FOLDER, on_click=new_project)

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
            dlg.open = False
            page.update()

        def on_save(event):
            new_name = project_name_field.value.strip()
            if not new_name:
                project_name_field.error_text = "Please enter a project name."
                page.update()
                return
            old_name = current_project["name"]
            current_project["name"] = new_name
            update_project_label()
            dlg.open = False
            page.snack_bar = ft.SnackBar(
                ft.Text(f"Project renamed from '{old_name}' to '{new_name}'."),
                duration=3000,
            )
            page.snack_bar.open = True
            page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("Edit Project Name"),
            content=project_name_field,
            actions=[
                ft.TextButton("Cancel", on_click=on_cancel),
                ft.TextButton("Save", on_click=on_save),
            ],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    edit_project_btn.on_click = edit_project_name

    # ---- 新增样本 ----
    def start_new_sample(e):
        nonlocal genus_rows
        new_sample_btn.disabled = True
        sample_form.controls.clear()

        sample_name_field = ft.TextField(label="Sample Name", width=250)
        total_abundance_field = ft.TextField(
            label="Total Abundance (count)", width=250,
            keyboard_type=ft.KeyboardType.NUMBER
        )

        genus_rows = ft.Column()

        def add_row():
            row_container, *_ = create_genus_row()
            genus_rows.controls.append(row_container)
            update_all_status()
            page.update()

        add_row()

        add_row_btn = ft.IconButton(icon=ft.Icons.ADD, on_click=lambda e: add_row())

        def submit_sample(e):
            rows_data = get_all_genus_rows()
            la_list = [la_f.value.strip() for _, _, _, _, la_f, _, _ in rows_data if la_f.value.strip()]
            duplicates = [la for la in set(la_list) if la_list.count(la) > 1]
            if duplicates:
                def on_confirm(e):
                    dlg.open = False
                    page.update()
                    do_submit()

                def on_cancel(e):
                    dlg.open = False
                    page.update()

                dup_str = ", ".join(duplicates)
                dlg = ft.AlertDialog(
                    title=ft.Text("Duplicate Genera Detected"),
                    content=ft.Text(
                        f"Duplicates found: {dup_str}.\nIf you continue, only the last occurrence of each duplicate will be kept (former ones discarded).\nDo you want to proceed?"),
                    actions=[
                        ft.TextButton("Cancel", on_click=on_cancel),
                        ft.TextButton("Proceed", on_click=on_confirm),
                    ],
                )
                page.overlay.append(dlg)
                dlg.open = True
                page.update()
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
                if total_abundance < 0:
                    show_dialog("Invalid Total Abundance", "Total abundance cannot be negative.")
                    return
            except ValueError:
                show_dialog("Invalid Total Abundance", "Total abundance must be a number.")
                return

            if sample_name in samples_memory:
                def close_dlg(e):
                    dlg.open = False
                    page.update()

                dlg = ft.AlertDialog(
                    title=ft.Text("Duplicate Sample Name"),
                    content=ft.Text(f"Sample '{sample_name}' already exists. Please use a different name."),
                    actions=[ft.TextButton("OK", on_click=close_dlg)],
                )
                page.overlay.append(dlg)
                dlg.open = True
                page.update()
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

            page.snack_bar = ft.SnackBar(ft.Text(f"Sample '{sample_name}' added!"), duration=3000)
            page.snack_bar.open = True
            sample_form.controls.clear()
            new_sample_btn.disabled = False
            refresh_sample_list()
            page.update()

        submit_btn = ft.Button("Add Sample", icon=ft.Icons.SAVE, on_click=submit_sample)

        sample_form.controls = [
            ft.Divider(),
            ft.Text("New Sample", theme_style=ft.TextThemeStyle.TITLE_LARGE),
            ft.Row([sample_name_field, total_abundance_field]),
            ft.Text("Genus abundances:", theme_style=ft.TextThemeStyle.TITLE_SMALL),
            genus_rows,
            add_row_btn,
            submit_btn,
        ]
        page.update()

    new_sample_btn.on_click = start_new_sample

    # ---- 编辑现有样本 ----
    def edit_sample(sample_name):
        nonlocal genus_rows
        sample_form.controls.clear()
        total_abund = samples_memory[sample_name]

        sample_name_field = ft.TextField(label="Sample Name", value=sample_name, disabled=True, width=250)
        total_abundance_field = ft.TextField(
            label="Total Abundance", value=str(total_abund),
            keyboard_type=ft.KeyboardType.NUMBER, width=250
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

        add_row_btn = ft.IconButton(icon=ft.Icons.ADD, on_click=lambda e: add_edit_row())

        def submit_edit(e):
            rows_data = get_all_genus_rows()
            la_list = [la_f.value.strip() for _, _, _, _, la_f, _, _ in rows_data if la_f.value.strip()]
            duplicates = [la for la in set(la_list) if la_list.count(la) > 1]
            if duplicates:
                def on_confirm(e):
                    dlg.open = False
                    page.update()
                    do_edit_submit()

                def on_cancel(e):
                    dlg.open = False
                    page.update()

                dup_str = ", ".join(duplicates)
                dlg = ft.AlertDialog(
                    title=ft.Text("Duplicate Genera Detected"),
                    content=ft.Text(
                        f"Duplicates found: {dup_str}.\nIf you continue, only the last occurrence of each duplicate will be kept.\nDo you want to proceed?"),
                    actions=[
                        ft.TextButton("Cancel", on_click=on_cancel),
                        ft.TextButton("Proceed", on_click=on_confirm),
                    ],
                )
                page.overlay.append(dlg)
                dlg.open = True
                page.update()
                return
            do_edit_submit()

        def do_edit_submit():
            new_total_str = total_abundance_field.value.strip()
            if not new_total_str:
                show_dialog("Missing Total Abundance", "Please enter the total abundance.")
                return
            try:
                new_total = float(new_total_str)
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

            page.snack_bar = ft.SnackBar(ft.Text(f"Sample '{sample_name}' updated!"), duration=3000)
            page.snack_bar.open = True
            sample_form.controls.clear()
            refresh_sample_list()
            page.update()

        save_btn = ft.Button("Save Changes", icon=ft.Icons.SAVE, on_click=submit_edit)
        cancel_btn = ft.Button("Cancel", on_click=lambda e: (
            sample_form.controls.clear(),
            page.update()
        ))

        sample_form.controls = [
            ft.Divider(),
            ft.Text(f"Edit Sample: {sample_name}", theme_style=ft.TextThemeStyle.TITLE_LARGE),
            ft.Row([sample_name_field, total_abundance_field]),
            ft.Text("Genus abundances:", theme_style=ft.TextThemeStyle.TITLE_SMALL),
            genus_rows,
            add_row_btn,
            ft.Row([save_btn, cancel_btn]),
        ]
        page.update()

    # ---- 草稿保存 / 读取 ----
    def apply_loaded_draft(loaded_project_name, loaded_samples, loaded_abundances):
        current_project["name"] = loaded_project_name or "Imported draft"
        samples_memory.clear()
        samples_memory.update(loaded_samples)
        abundances_memory.clear()
        abundances_memory.extend(loaded_abundances)
        sample_form.controls.clear()
        new_sample_btn.disabled = False
        export_btn.disabled = False
        save_draft_btn.disabled = False
        update_project_label()
        refresh_sample_list()
        page.snack_bar = ft.SnackBar(
            ft.Text(
                f"Draft loaded for project '{current_project['name']}'. "
                f"{len(samples_memory)} sample(s) ready for input."
            ),
            duration=3000,
        )
        page.snack_bar.open = True
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
                dialog_title="Save NemaDB Draft",
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
            page.snack_bar = ft.SnackBar(
                ft.Text(f"Draft saved to: {draft_path.resolve()}"), duration=3000
            )
            page.snack_bar.open = True
        except (OSError, PermissionError, IOError) as ex:
            show_dialog("Save Draft Failed", f"Could not save the draft file.\nError: {ex}")

        page.update()

    async def load_draft_clicked(e):
        try:
            files = await draft_file_picker.pick_files(
                dialog_title="Load NemaDB Draft",
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
            dlg.open = False
            page.update()
            apply_loaded_draft(loaded_project_name, loaded_samples, loaded_abundances)

        def on_cancel_load(event):
            dlg.open = False
            page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("Load Draft"),
            content=ft.Text(
                "Loading a draft will replace the current input data and any unsaved form changes. Continue?"
            ),
            actions=[
                ft.TextButton("Cancel", on_click=on_cancel_load),
                ft.TextButton("Load Draft", on_click=on_confirm_load),
            ],
        )
        page.overlay.append(dlg)
        dlg.open = True
        page.update()

    save_draft_btn.on_click = lambda e: page.run_task(save_draft_clicked, e)
    load_draft_btn.on_click = lambda e: page.run_task(load_draft_clicked, e)

    # ---- 导出功能 ----
    def setup_export_button(page, samples_memory, abundances_memory):
        picker = ft.FilePicker()
        page.services.append(picker)

        async def export_clicked(e):
            folder_path = await picker.get_directory_path(
                dialog_title="Select Export Folder",
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

                page.snack_bar = ft.SnackBar(
                    ft.Text(f"Files saved to: {out_dir.resolve()}"), duration=3000
                )
                page.snack_bar.open = True

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
            color=ft.Colors.RED,
            weight=ft.FontWeight.BOLD,
            visible=False,
        )

        def validate_fields():
            is_valid = True

            def set_field_error(field, message=None):
                field.error_text = message
                field.border_color = ft.Colors.RED if message else None
                field.focused_border_color = ft.Colors.RED if message else None

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
            validation_summary.value = "Please fix the highlighted fields before submitting."
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
        )

        dlg = ft.AlertDialog(
            title=ft.Text("Submit Data"),
            content=ft.Container(content=form, width=720, height=560),
            actions=[
                ft.TextButton("Cancel", on_click=close_dialog),
                ft.Button("Copy Email Template", icon=ft.Icons.CONTENT_COPY,
                          on_click=lambda event: page.run_task(copy_email_template, event)),
                ft.Button("Open Email Draft", icon=ft.Icons.EMAIL,
                          on_click=lambda event: page.run_task(open_email_draft, event)),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        page.show_dialog(dlg)

    submit_data_btn = ft.Button(
        "Submit Data",
        icon=ft.Icons.EMAIL,
        on_click=open_submission_dialog,
    )

    # ---- Input 页面布局 ----
    input_page = ft.Column([
        ft.Text("Input Data", theme_style=ft.TextThemeStyle.HEADLINE_MEDIUM),
        project_header,
        ft.Divider(),
        ft.Row([new_project_btn, new_sample_btn, save_draft_btn, load_draft_btn, export_btn], wrap=True),
        ft.Divider(height=10),
        ft.Text("Saved Samples", theme_style=ft.TextThemeStyle.TITLE_SMALL),
        ft.Container(
            content=sample_list_view,
            height=200,
            bgcolor=ft.Colors.GREY_50,
            border_radius=10,
            padding=5,
        ),
        ft.Divider(height=10),
        sample_form,
        ft.Container(height=100),
    ], expand=True, scroll=ft.ScrollMode.AUTO)

    # ==================== Help Page ====================
    def help_section(icon, title, lines):
        return ft.Container(
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Icon(icon, color=ft.Colors.BLUE_GREY_700),
                            ft.Text(title, theme_style=ft.TextThemeStyle.TITLE_MEDIUM),
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Column(
                        [ft.Text(line, color=ft.Colors.BLUE_GREY_800) for line in lines],
                        spacing=5,
                    ),
                ],
                spacing=8,
            ),
            bgcolor=ft.Colors.BLUE_GREY_50,
            border=ft.Border.all(1, ft.Colors.BLUE_GREY_100),
            border_radius=8,
            padding=ft.Padding.symmetric(horizontal=14, vertical=12),
        )

    submit_data_panel = ft.Container(
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Icon(ft.Icons.EMAIL, color=ft.Colors.BLUE_GREY_700),
                        ft.Text("Submit Data", theme_style=ft.TextThemeStyle.TITLE_MEDIUM),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Text(
                    "If you notice missing or incomplete nematode records while using NemaDB, "
                    "you can submit supplemental data for review.",
                    color=ft.Colors.BLUE_GREY_800,
                ),
                ft.Text(
                    "The form checks required fields and basic data types, then opens an email draft "
                    "or copies a ready-to-send email template.",
                    color=ft.Colors.BLUE_GREY_800,
                ),
                submit_data_btn,
            ],
            spacing=8,
        ),
        bgcolor=ft.Colors.BLUE_50,
        border=ft.Border.all(1, ft.Colors.BLUE_100),
        border_radius=8,
        padding=ft.Padding.symmetric(horizontal=14, vertical=12),
    )

    help_page = ft.Column([
        ft.Text("Help", theme_style=ft.TextThemeStyle.HEADLINE_MEDIUM),
        ft.Text(
            "NemaDB is a lightweight utility for searching nematode reference data and preparing "
            "sample abundance files for downstream analysis.",
            theme_style=ft.TextThemeStyle.BODY_LARGE,
        ),
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
        submit_data_panel,
        help_section(
            ft.Icons.INFO,
            "Data Source",
            [
                "The built-in reference data is loaded from nematode.info.csv.",
                "Search suggestions and genus name mapping are based on this file.",
                "Submitted data is not added automatically; it should be reviewed before being included in future releases.",
            ],
        ),
        ft.Container(
            content=ft.Text(f"Version: {version}", italic=True, color=ft.Colors.GREY_500),
            padding=ft.Padding.symmetric(vertical=8, horizontal=0),
        ),
    ], expand=True, scroll=ft.ScrollMode.AUTO, spacing=12)



    # ==================== 页面切换 ====================
    content_area = ft.Container(content=search_page, expand=True)

    def switch_page(e):
        pages = [search_page, input_page, help_page]
        content_area.content = pages[e.control.selected_index]
        page.update()

    page.navigation_bar = ft.NavigationBar(
        selected_index=0,
        on_change=switch_page,
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.SEARCH, label="Search"),
            ft.NavigationBarDestination(icon=ft.Icons.INPUT, label="Input"),
            ft.NavigationBarDestination(icon=ft.Icons.HELP, label="Help"),
        ],
    )

    page.add(content_area)

    # ==================== 启动欢迎弹窗（修复后） ====================
    # 先创建对话框，但不设置 actions（或设为空列表），然后定义关闭函数，再设置 actions
    welcome_dialog = ft.AlertDialog(
        title=ft.Text("🎉 Welcome to NemaDB"),
        content=ft.Column(
            [
                ft.Text("Nematode Database Utility", size=16, weight=ft.FontWeight.BOLD),
                ft.Text(f"Version: {version}", italic=True, size=12),
                ft.Divider(),
                ft.Text("Authors:", weight=ft.FontWeight.BOLD),
                ft.Text("He Yuxuan (Development & Testing)"),
                ft.Text("Zhao Jinmeng, Zhang Yudan, Qi Xinyu (Data Collection & Testing)"),
                ft.Text("Wang Dong, Miao Yuan (Supervisors)"),
                ft.Text("(Names not in particular order)"),
                ft.Divider(),
                ft.Text("© All rights reserved by the authors.", italic=True),
                ft.Container(height=10),
                ft.Text("Thank you for using NemaDB!", size=14, weight=ft.FontWeight.BOLD),
            ],
            spacing=6,
            scroll=ft.ScrollMode.AUTO,
        ),
        # 先不设置 actions，后面再设置
    )

    # 定义关闭函数
    def close_welcome(e=None):
        welcome_dialog.open = False
        page.update()

    # 为对话框添加关闭按钮
    welcome_dialog.actions = [
        ft.TextButton("OK", on_click=close_welcome),
    ]
    welcome_dialog.actions_alignment = ft.MainAxisAlignment.END

    # 显示对话框
    page.show_dialog(welcome_dialog)


ft.run(main)
