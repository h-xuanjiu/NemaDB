import csv
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
    table_area = ft.Column(
        [ft.Row([result_table], scroll="auto")],
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

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
            return
        col_idx = SEARCH_COLUMNS[col_dropdown.value]
        keyword_lower = keyword.lower()
        matched = [row for row in ALL_ROWS if keyword_lower in row[col_idx].lower()]
        result_table.rows = [
            ft.DataRow(cells=[ft.DataCell(ft.Text(cell)) for cell in row])
            for row in matched
        ]
        page.update()

    search_btn = ft.Button("Search", icon=ft.Icons.FIND_IN_PAGE, on_click=do_search)
    search_page = ft.Column([
        ft.Text("Search Nematode Data", theme_style=ft.TextThemeStyle.HEADLINE_MEDIUM),
        ft.Divider(),
        ft.ResponsiveRow([
            ft.Column([col_dropdown], col={"xs": 12, "sm": 4, "md": 3}),
            ft.Column([keyword_field], col={"xs": 12, "sm": 8, "md": 9}),
        ]),
        suggestion_container,
        ft.Row([search_btn], alignment=ft.MainAxisAlignment.END),
        ft.Divider(),
        ft.Text("Results:", theme_style=ft.TextThemeStyle.TITLE_SMALL),
        table_area,
    ], expand=True, spacing=10)

    # ==================== Input Page ====================
    new_sample_btn = ft.Button("New Sample", icon=ft.Icons.ADD_CARD, disabled=True)
    export_btn = ft.Button("Export", icon=ft.Icons.DOWNLOAD, disabled=True)
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
    def new_project(e):
        samples_memory.clear()
        abundances_memory.clear()
        new_sample_btn.disabled = False
        export_btn.disabled = False
        sample_form.controls.clear()
        refresh_sample_list()
        page.snack_bar = ft.SnackBar(ft.Text("New project created. Ready for input."), duration=3000)
        page.snack_bar.open = True
        page.update()

    new_project_btn = ft.Button("New Project", icon=ft.Icons.CREATE_NEW_FOLDER, on_click=new_project)

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

    # ---- 导出功能 ----
    def setup_export_button(page, samples_memory, abundances_memory):
        async def export_clicked(e):
            picker = ft.FilePicker()
            folder_path = await picker.get_directory_path(
                dialog_title="Select Export Folder",
                initial_directory=str(Path.home())
            )
            if not folder_path:
                return

            out_dir = Path(folder_path)
            try:
                total_file = out_dir / "total_abundance.csv"
                with open(total_file, "w", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow(["SampleID", "Abundance"])
                    for name, abund in samples_memory.items():
                        writer.writerow([name, abund])

                genus_file = out_dir / "genus_abundance.csv"
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

    # ---- Input 页面布局 ----
    input_page = ft.Column([
        ft.Text("Input Data", theme_style=ft.TextThemeStyle.HEADLINE_MEDIUM),
        ft.Divider(),
        ft.Row([new_project_btn, new_sample_btn, export_btn]),
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
    help_page = ft.Column([
        ft.Text("Help", theme_style=ft.TextThemeStyle.HEADLINE_MEDIUM),
        ft.Divider(),
        ft.Text("Welcome to NemaDB – a lightweight nematode data utility.",
                theme_style=ft.TextThemeStyle.BODY_LARGE),
        ft.Container(height=10),
        ft.Text("🔍 Search", theme_style=ft.TextThemeStyle.TITLE_SMALL),
        ft.Text("• Choose a column from the dropdown (Genus(zh), Genus(la), Family)."),
        ft.Text(
            "• Start typing in the keyword field – a suggestion list will appear with the best matches (ordered by match position)."),
        ft.Text("• Click a suggestion to fill the field, then press 'Search' to see all matching records in a table."),
        ft.Container(height=10),
        ft.Text("📥 Input", theme_style=ft.TextThemeStyle.TITLE_SMALL),
        ft.Text("1. Start by clicking 'New Project' (this clears any previously entered data)."),
        ft.Text("2. Click 'New Sample' to open the input form."),
        ft.Text("3. Enter a Sample Name and Total Abundance (total count of nematodes)."),
        ft.Text("4. For each genus found in the sample, fill in a row:"),
        ft.Text(
            "   - Type in Genus(zh) or Genus(la); as you type, matching suggestions will appear. Click a suggestion to select it – the other genus field will auto-fill."),
        ft.Text("   - Enter the Abundance (count) for that genus."),
        ft.Text("5. Use the '+' button to add more genus rows, and the trash icon to remove a row."),
        ft.Text("6. After all genera are entered, click 'Add Sample' to save it to memory."),
        ft.Text("7. Saved samples appear in the list above; click on a sample to edit it."),
        ft.Text("8. Click the red trash icon on a sample card to delete it (with confirmation)."),
        ft.Container(height=10),
        ft.Text("💾 Export", theme_style=ft.TextThemeStyle.TITLE_SMALL),
        ft.Text("• Click 'Export' and choose a folder. Two CSV files will be saved there:"),
        ft.Text("   - total_abundance.csv: SampleID, Abundance"),
        ft.Text(
            "   - genus_abundance.csv: A table with SampleID as rows and genus (Latin names) as columns, abundances filled in."),
        ft.Container(height=10),
        ft.Text("📄 Data source", theme_style=ft.TextThemeStyle.TITLE_SMALL),
        ft.Text("• The reference data is loaded from 'nematode.info.csv'."),
        ft.Text("• Search and genus suggestions are based on this file."),
        ft.Container(height=20),  # 一些间距
        ft.Container(
            content=ft.Text(f"Version: {version}", italic=True, color=ft.Colors.GREY_500)
        )
    ], expand=True, scroll=ft.ScrollMode.AUTO)



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
