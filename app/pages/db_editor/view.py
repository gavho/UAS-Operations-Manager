import sys
import os
from PyQt5.QtWidgets import (
    QWidget, QApplication, QFileDialog, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QTreeWidget, QTreeWidgetItem,
    QHBoxLayout, QLabel, QToolBar, QAction, QMessageBox,
    QHeaderView, QMenu, QToolButton
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QKeySequence, QColor, QIcon
from app.database import db_manager
from app.database.core import get_session_and_models
from sqlalchemy import text, inspect
import clipboard


class NumericTableWidgetItem(QTableWidgetItem):
    """
    A custom QTableWidgetItem that implements proper numerical sorting.
    It attempts to convert its text to a float and uses that for comparison.
    If the text is not numeric, it falls back to standard string comparison.
    """

    def __init__(self, text):
        super(NumericTableWidgetItem, self).__init__(text)
        # We try to convert the text to a float once, when the item is created.
        try:
            self.numeric_value = float(text)
            self.is_numeric = True
        except (ValueError, TypeError):
            self.is_numeric = False

    def __lt__(self, other):
        """
        Override the default 'less than' operator, which is used for sorting.
        """
        # 'other' will also be a NumericTableWidgetItem
        if self.is_numeric and hasattr(other, 'is_numeric') and other.is_numeric:
            # If both items are numeric, compare their float values.
            return self.numeric_value < other.numeric_value

        # If one or both items are not numeric, fall back to the standard
        # string-based comparison provided by the parent QTableWidgetItem.
        return super().__lt__(other)


class DBEditorWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.db_path = ""

        # Internal state
        self.edited_cells = {}
        self.undo_stack = []
        self.redo_stack = []
        self.current_table_name = None
        self.error_rows = set()
        self.edited_rows = set()
        self.new_rows = {}
        self.new_row_counter = 0

        # View options
        self.show_required_fields = False
        self.highlight_nulls = False
        self.highlight_empty_strings = False

        self.error_details = {}

        self.main_layout = QVBoxLayout(self)

        self.setup_toolbar()
        self.setup_ui()
        self.setup_status_bar()

        db_manager.connection_set.connect(self.populate_db_tree)
        self.populate_db_tree()

    def setup_ui(self):
        """
        Sets up the UI components. Sorting is now enabled on the table view.
        """
        content_layout = QHBoxLayout()

        self.db_tree_widget = QTreeWidget()
        self.db_tree_widget.setHeaderLabels(['Databases'])
        self.db_tree_widget.currentItemChanged.connect(self.on_tree_item_selected)
        self.db_tree_widget.setContextMenuPolicy(Qt.CustomContextMenu)
        self.db_tree_widget.customContextMenuRequested.connect(self.open_tree_menu)
        self.db_tree_widget.setMaximumWidth(350)
        content_layout.addWidget(self.db_tree_widget, 1)

        right_panel = QVBoxLayout()
        right_panel.addWidget(QLabel("Data:"))
        self.table_view = QTableWidget()
        self.table_view.itemChanged.connect(self.handle_item_changed)
        self.table_view.cellClicked.connect(self.display_error_info)
        self.table_view.setSelectionBehavior(QTableWidget.SelectItems)
        self.table_view.setSelectionMode(QTableWidget.ExtendedSelection)
        self.table_view.setEditTriggers(QTableWidget.DoubleClicked | QTableWidget.SelectedClicked)
        self.table_view.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_view.customContextMenuRequested.connect(self.open_table_menu)

        # MODIFIED: Enable sorting on the table
        self.table_view.setSortingEnabled(True)

        right_panel.addWidget(self.table_view)
        content_layout.addLayout(right_panel, 4)
        self.main_layout.addLayout(content_layout)

    def setup_toolbar(self):
        """
        Creates a toolbar. The "Clear Filters" button has been removed.
        """
        toolbar = QToolBar("DB Editor Toolbar")
        self.main_layout.addWidget(toolbar)

        self.open_db_action = QAction("Open DB", self)
        self.open_db_action.setShortcut(QKeySequence("Ctrl+O"))
        self.open_db_action.triggered.connect(self.open_db_file)
        toolbar.addAction(self.open_db_action)

        toolbar.addSeparator()


        self.save_action = QAction("Save Edits", self)
        self.save_action.setShortcut(QKeySequence("Ctrl+S"))
        self.save_action.triggered.connect(self.save_edits)
        toolbar.addAction(self.save_action)

        self.refresh_action = QAction("Refresh", self)
        self.refresh_action.setShortcut(QKeySequence("Ctrl+R"))
        self.refresh_action.triggered.connect(self.refresh_data)
        toolbar.addAction(self.refresh_action)

        toolbar.addSeparator()

        self.new_row_action = QAction("Create New Row", self)
        self.new_row_action.setShortcut(QKeySequence("Ctrl+N"))
        self.new_row_action.triggered.connect(self.create_new_row)
        toolbar.addAction(self.new_row_action)

        self.duplicate_row_action = QAction("Duplicate Row", self)
        self.duplicate_row_action.setShortcut(QKeySequence("Ctrl+D"))
        self.duplicate_row_action.triggered.connect(self.duplicate_selected_row)
        toolbar.addAction(self.duplicate_row_action)

        self.delete_action = QAction("Delete Row", self)
        self.delete_action.setShortcut(QKeySequence("Del"))
        self.delete_action.triggered.connect(self.delete_selected_rows)
        toolbar.addAction(self.delete_action)

        toolbar.addSeparator()

        self.undo_action = QAction("Undo", self)
        self.undo_action.setShortcut(QKeySequence("Ctrl+Z"))
        self.undo_action.triggered.connect(self.undo_edit)
        toolbar.addAction(self.undo_action)

        self.redo_action = QAction("Redo", self)
        self.redo_action.setShortcut(QKeySequence("Ctrl+Y"))
        self.redo_action.triggered.connect(self.redo_edit)
        toolbar.addAction(self.redo_action)

        toolbar.addSeparator()

        view_options_menu = QMenu(self)
        view_options_menu.setTitle("View Options")

        self.show_required_action = QAction("Show Required Fields", self)
        self.show_required_action.setCheckable(True)
        self.show_required_action.triggered.connect(self.toggle_required_fields)
        view_options_menu.addAction(self.show_required_action)

        self.highlight_nulls_action = QAction("Highlight NULLs", self)
        self.highlight_nulls_action.setCheckable(True)
        self.highlight_nulls_action.triggered.connect(self.toggle_highlight_nulls)
        view_options_menu.addAction(self.highlight_nulls_action)

        self.highlight_empty_action = QAction("Highlight Empty Strings", self)
        self.highlight_empty_action.setCheckable(True)
        self.highlight_empty_action.triggered.connect(self.toggle_highlight_empty_strings)
        view_options_menu.addAction(self.highlight_empty_action)

        view_options_button = QToolButton()
        view_options_button.setText("View Options")
        view_options_button.setMenu(view_options_menu)
        view_options_button.setPopupMode(QToolButton.InstantPopup)
        toolbar.addWidget(view_options_button)

        self.undo_action.setEnabled(False)
        self.redo_action.setEnabled(False)

    def populate_table_view(self, model_name):
        """
        MODIFIED: Now populates the table using the NumericTableWidgetItem
        and disables sorting during population for better performance.
        """
        self.table_view.setSortingEnabled(False)  # Disable sorting for performance
        self.table_view.itemChanged.disconnect()
        self.table_view.clear()
        self.table_view.setRowCount(0)
        self.table_view.setColumnCount(0)

        # (State clearing logic is the same)
        self.edited_cells.clear()
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.undo_action.setEnabled(False)
        self.redo_action.setEnabled(False)
        self.error_rows.clear()
        self.edited_rows.clear()
        self.new_rows.clear()
        self.error_details.clear()
        self.error_label.setText("Click on a red cell to see the error details.")
        self.value_label.setText("Value: None")

        if db_manager.models and model_name in db_manager.models:
            TableClass = db_manager.models[model_name]
            session = db_manager.session
            engine = session.bind
            headers = [c.key for c in TableClass.__table__.columns]
            self.table_view.setColumnCount(len(headers))
            self.table_view.setHorizontalHeaderLabels(headers)
            self.table_view.verticalHeader().setSectionsClickable(True)
            self.table_view.verticalHeader().sectionClicked.connect(self.display_row_error_info)
            self.update_required_fields_headers()

            # The query is now simple again, without the WHERE clause
            try:
                with engine.connect() as connection:
                    statement = text(f'SELECT * FROM "{model_name}"')
                    result = connection.execute(statement)
                    rows = result.fetchall()
            except Exception as e:
                QMessageBox.critical(self, "Query Error", f"Failed to query table '{model_name}': {e}")
                self.table_view.itemChanged.connect(self.handle_item_changed)
                return

            inspector = inspect(engine)
            column_info = {c['name']: c for c in inspector.get_columns(model_name)}
            self.table_view.setRowCount(len(rows))

            for row_idx, row_tuple in enumerate(rows):
                self.table_view.setVerticalHeaderItem(row_idx, QTableWidgetItem(str(row_idx + 1)))
                is_row_invalid = False
                for col_idx, value in enumerate(row_tuple):
                    header = headers[col_idx]
                    col_info = column_info.get(header)
                    column_type = str(col_info['type']).upper() if col_info else 'TEXT'
                    column_nullable = col_info['nullable'] if col_info else True
                    is_null, is_empty_string = (value is None), (isinstance(value, str) and value == "")
                    value_str = str(value) if value is not None else ""

                    # MODIFIED: Use the new NumericTableWidgetItem
                    item = NumericTableWidgetItem(value_str)

                    is_invalid = False
                    if not is_null and not is_empty_string:
                        try:
                            if "INTEGER" in column_type:
                                int(value)
                            elif "REAL" in column_type or "FLOAT" in column_type:
                                float(value)
                        except (ValueError, TypeError):
                            is_invalid = True
                            tooltip_text = f"Data type mismatch! Expected {column_type}, found '{value_str}'."
                            self.error_details[(row_idx, col_idx)] = {"message": tooltip_text, "value": value}
                    if not is_invalid and not column_nullable and (is_null or is_empty_string):
                        is_invalid = True
                        tooltip_text = f"Non-nullable field '{header}' is empty."
                        self.error_details[(row_idx, col_idx)] = {"message": tooltip_text, "value": value}
                    if is_invalid:
                        item.setBackground(QColor(255, 100, 100))
                        item.setToolTip(tooltip_text)
                        is_row_invalid = True
                    if not is_invalid:
                        if self.highlight_nulls and is_null:
                            item.setBackground(QColor(255, 230, 230))
                        elif self.highlight_empty_strings and is_empty_string:
                            item.setBackground(QColor(255, 230, 230))
                    self.table_view.setItem(row_idx, col_idx, item)
                if is_row_invalid:
                    self.error_rows.add(row_idx)
                    header_item = self.table_view.verticalHeaderItem(row_idx)
                    header_item.setBackground(QColor(255, 100, 100))

        self.table_view.itemChanged.connect(self.handle_item_changed)
        self.table_view.setSortingEnabled(True)  # Re-enable sorting

    def open_db_file(self):
        db_path, _ = QFileDialog.getOpenFileName(self, "Open Database File", "",
                                                   "Database Files (*.db *.sqlite *.sqlite3)")
        if db_path:
            try:
                session, models = get_session_and_models(db_path)
                db_manager.set_connection(session, models)
                self.populate_db_tree()
            except Exception as e:
                QMessageBox.critical(self, "DB Error", f"Failed to open database: {e}")

    def on_tree_item_selected(self, current_item, previous_item):
        if current_item is None:
            return

        item_data = current_item.data(0, Qt.UserRole)

        if item_data and item_data.get('type') == 'table':
            table_name = item_data['table']

            if self.has_unsaved_changes():
                reply = self.prompt_for_unsaved_changes()
                if reply == QMessageBox.Save:
                    self.save_edits()
                elif reply == QMessageBox.Cancel:
                    self.db_tree_widget.blockSignals(True)
                    self.db_tree_widget.setCurrentItem(previous_item)
                    self.db_tree_widget.blockSignals(False)
                    return

            if db_manager.session:
                self.current_table_name = table_name
                self.populate_table_view(table_name)

    def setup_status_bar(self):
        status_bar_layout = QHBoxLayout()
        self.error_label = QLabel("Tip: Open a database file to begin.")
        self.value_label = QLabel("Value: None")
        self.value_label.setAlignment(Qt.AlignRight)
        status_bar_layout.addWidget(self.error_label)
        status_bar_layout.addWidget(self.value_label)
        self.main_layout.addLayout(status_bar_layout)

    def show_status_message(self, message, timeout=2000):
        self.error_label.setText(message)


    def populate_db_tree(self):
        self.db_tree_widget.clear()
        if db_manager.session:
            self.db_tree_widget.setHeaderLabels(['Database'])
            db_path = db_manager.session.bind.url.database
            db_name = os.path.basename(db_path)
            db_node = QTreeWidgetItem(self.db_tree_widget, [db_name])
            db_node.setData(0, Qt.UserRole, {'path': db_path, 'type': 'db'})
            models_dict = db_manager.models
            for table_name in sorted(models_dict.keys()):
                table_node = QTreeWidgetItem(db_node, [table_name])
                table_node.setData(0, Qt.UserRole, {'path': db_path, 'table': table_name, 'type': 'table'})
            self.db_tree_widget.expandAll()
        else:
            self.db_tree_widget.setHeaderLabels(['No Database'])

    def open_tree_menu(self, position):
        item = self.db_tree_widget.itemAt(position)
        if not item or not item.data(0, Qt.UserRole): return
        item_data = item.data(0, Qt.UserRole)
        menu = QMenu()
        if item_data.get('type') == 'db':
            close_action = QAction("Close Database", self)
            close_action.triggered.connect(lambda: self.close_database(item_data.get('path')))
            menu.addAction(close_action)
        menu.exec_(self.db_tree_widget.mapToGlobal(position))

    def close_database(self, db_path):
        if self.has_unsaved_changes():
            reply = self.prompt_for_unsaved_changes()
            if reply == QMessageBox.Save:
                self.save_edits()
            elif reply == QMessageBox.Cancel:
                return
        db_manager.close_connection()
        self.populate_db_tree()
        self.table_view.clear()
        self.table_view.setRowCount(0)
        self.table_view.setColumnCount(0)

    def has_unsaved_changes(self):
        return bool(self.edited_cells or self.new_rows)

    def prompt_for_unsaved_changes(self):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Unsaved Changes")
        msg_box.setText("You have unsaved changes. Do you want to save them before proceeding?")
        msg_box.setStandardButtons(QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
        msg_box.setDefaultButton(QMessageBox.Save)
        return msg_box.exec_()

    def refresh_data(self):
        if self.has_unsaved_changes():
            reply = self.prompt_for_unsaved_changes()
            if reply == QMessageBox.Save:
                self.save_edits()
            elif reply == QMessageBox.Cancel:
                return
        if self.current_table_name: self.populate_table_view(self.current_table_name)

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.Copy):
            self.copy_selected_cells()
        elif event.matches(QKeySequence.Paste):
            self.paste_from_clipboard()
        else:
            super().keyPressEvent(event)

    def copy_selected_cells(self):
        selected_items = self.table_view.selectedItems()
        if not selected_items: return
        sorted_items = sorted(selected_items, key=lambda x: (x.row(), x.column()))
        min_row, max_row = sorted_items[0].row(), sorted_items[-1].row()
        min_col, max_col = min(item.column() for item in sorted_items), max(item.column() for item in sorted_items)
        data = [['' for _ in range(max_col - min_col + 1)] for _ in range(max_row - min_row + 1)]
        for item in sorted_items:
            data[item.row() - min_row][item.column() - min_col] = item.text()
        clipboard_text = "\n".join(["\t".join(row) for row in data])
        QApplication.clipboard().setText(clipboard_text)
        self.show_status_message(f"Copied {len(selected_items)} cells to clipboard.")

    def paste_from_clipboard(self):
        clipboard_text = QApplication.clipboard().text()
        if not clipboard_text: return
        selected_items = self.table_view.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Paste Error", "Please select a starting cell to paste.")
            return
        start_item = sorted(selected_items, key=lambda x: (x.row(), x.column()))[0]
        start_row, start_col = start_item.row(), start_item.column()
        rows_to_paste = clipboard_text.split('\n')
        self.table_view.itemChanged.disconnect()
        headers = [c.key for c in db_manager.models[self.current_table_name].__table__.columns]
        try:
            for i, row_data in enumerate(rows_to_paste):
                values = row_data.split('\t')
                for j, value in enumerate(values):
                    target_row, target_col = start_row + i, start_col + j
                    if target_row >= self.table_view.rowCount() or target_col >= self.table_view.columnCount(): continue
                    item = self.table_view.item(target_row, target_col)
                    if not item:
                        item = NumericTableWidgetItem("")  # Use the new item
                        self.table_view.setItem(target_row, target_col, item)
                    original_value = item.text()
                    column_name = headers[target_col]
                    column_obj = db_manager.models[self.current_table_name].__table__.columns.get(column_name)
                    converted_value = None
                    try:
                        if "INTEGER" in str(column_obj.type).upper():
                            converted_value = int(value)
                        elif "REAL" in str(column_obj.type).upper() or "FLOAT" in str(column_obj.type).upper():
                            converted_value = float(value)
                        elif "BOOLEAN" in str(column_obj.type).upper():
                            converted_value = value.lower() in ('true', 't', '1')
                        else:
                            converted_value = value
                    except (ValueError, TypeError):
                        QMessageBox.warning(self, "Paste Error",
                                            f"Cannot paste '{value}' into column '{column_name}' due to a type mismatch.")
                        self.table_view.itemChanged.connect(self.handle_item_changed)
                        return
                    if (target_row, target_col) not in self.edited_cells:
                        self.edited_cells[(target_row, target_col)] = original_value
                        self.undo_stack.append({"row": target_row, "col": target_col, "original": original_value,
                                                "new": str(converted_value)})
                        self.undo_action.setEnabled(True)
                        if len(self.undo_stack) > 10: self.undo_stack.pop(0)
                    item.setText(str(converted_value))
                    item.setBackground(QColor(255, 255, 150))
                    self.edited_rows.add(target_row)
                    header_item = self.table_view.verticalHeaderItem(target_row)
                    if not header_item:
                        header_item = QTableWidgetItem()
                        self.table_view.setVerticalHeaderItem(target_row, header_item)
                    if not header_item.text().endswith(' *'): header_item.setText(str(target_row + 1) + ' *')
        finally:
            self.table_view.itemChanged.connect(self.handle_item_changed)

    def make_null_selected_cells(self):
        selected_items = self.table_view.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "Warning", "Please select one or more cells to make NULL.")
            return

        self.table_view.itemChanged.disconnect()

        for item in selected_items:
            row, col = item.row(), item.column()

            if (row, col) not in self.edited_cells:
                original_value = item.text()
                self.edited_cells[(row, col)] = original_value

                self.undo_stack.append({
                    "row": row, "col": col,
                    "original": original_value,
                    "new": ""
                })
                self.undo_action.setEnabled(True)
                self.redo_stack.clear()
                self.redo_action.setEnabled(False)

                if len(self.undo_stack) > 10:
                    self.undo_stack.pop(0)

            item.setText("")
            item.setBackground(QColor(255, 255, 150))
            self.edited_rows.add(row)

        self.table_view.itemChanged.connect(self.handle_item_changed)
        self.show_status_message(f"Set {len(selected_items)} cells to NULL. Don't forget to save.")

    def update_required_fields_headers(self):
        if not self.current_table_name or not db_manager.models:
            return

        headers = [column.key for column in db_manager.models[self.current_table_name].__table__.columns]
        header_labels = []
        if self.show_required_fields:
            for column in db_manager.models[self.current_table_name].__table__.columns:
                label = column.key
                if not column.nullable and not column.primary_key:
                    label += " *"
                header_labels.append(label)
        else:
            header_labels = headers
        self.table_view.setHorizontalHeaderLabels(header_labels)

    def toggle_required_fields(self, checked):
        self.show_required_fields = checked
        self.update_required_fields_headers()

    def toggle_highlight_nulls(self, checked):
        self.highlight_nulls = checked
        if self.current_table_name:
            self.populate_table_view(self.current_table_name)

    def toggle_highlight_empty_strings(self, checked):
        self.highlight_empty_strings = checked
        if self.current_table_name:
            self.populate_table_view(self.current_table_name)

    def create_new_row(self):
        if not self.current_table_name:
            QMessageBox.warning(self, "Warning", "Please select a table from the left panel before creating a new row.")
            return

        row_count = self.table_view.rowCount()
        self.table_view.insertRow(row_count)

        self.new_row_counter += 1
        temp_id = f"NEW_{self.new_row_counter}"
        self.new_rows[row_count] = temp_id

        header_item = QTableWidgetItem(f"{row_count + 1} *")
        header_item.setBackground(QColor(255, 255, 150))
        self.table_view.setVerticalHeaderItem(row_count, header_item)

        for col_idx in range(self.table_view.columnCount()):
            item = NumericTableWidgetItem("")  # Use the new item
            self.table_view.setItem(row_count, col_idx, item)

        self.edited_rows.add(row_count)
        self.table_view.scrollToBottom()

    def duplicate_selected_row(self):
        selected_rows = sorted(list(set(item.row() for item in self.table_view.selectedItems())))
        if not selected_rows or len(selected_rows) > 1:
            QMessageBox.warning(self, "Warning", "Please select exactly one row to duplicate.")
            return

        row_to_duplicate = selected_rows[0]
        row_count = self.table_view.rowCount()
        self.table_view.insertRow(row_count)

        self.new_row_counter += 1
        temp_id = f"NEW_{self.new_row_counter}"
        self.new_rows[row_count] = temp_id

        header_item = QTableWidgetItem(f"{row_count + 1} *")
        header_item.setBackground(QColor(255, 255, 150))
        self.table_view.setVerticalHeaderItem(row_count, header_item)

        primary_key_column_idx = self.get_primary_key_column_index()

        for col_idx in range(self.table_view.columnCount()):
            original_item = self.table_view.item(row_to_duplicate, col_idx)
            if original_item:
                new_item_text = original_item.text()
                if col_idx == primary_key_column_idx:
                    new_item_text = ""

                new_item = NumericTableWidgetItem(new_item_text)  # Use the new item
                new_item.setBackground(QColor(255, 255, 150))
                self.table_view.setItem(row_count, col_idx, new_item)

        self.edited_rows.add(row_count)
        self.table_view.scrollToBottom()

    def display_error_info(self, row, col):
        item = self.table_view.item(row, col)

        value = "NULL" if item is None or item.text() == "" else item.text()
        self.value_label.setText(f"Value: '{value}'")

        if (row, col) in self.error_details:
            self.error_label.setText(self.error_details[(row, col)]["message"])
        else:
            self.error_label.setText("No data type error in this cell.")

    def display_row_error_info(self, row):
        header_item = self.table_view.verticalHeaderItem(row)
        if header_item and header_item.background().color() == QColor(255, 100, 100):
            for col in range(self.table_view.columnCount()):
                if (row, col) in self.error_details:
                    self.display_error_info(row, col)
                    return
        else:
            self.error_label.setText("Click on a red cell to see the error details.")
            self.value_label.setText("Value: None")

    def handle_item_changed(self, item):
        row = item.row()
        col = item.column()

        self.table_view.itemChanged.disconnect()

        if (row, col) not in self.edited_cells:
            original_value = self.get_original_value(row, col)
            self.edited_cells[(row, col)] = original_value

            self.undo_stack.append({
                "row": row, "col": col,
                "original": original_value,
                "new": item.text()
            })
            self.undo_action.setEnabled(True)
            self.redo_stack.clear()
            self.redo_action.setEnabled(False)

            if len(self.undo_stack) > 10:
                self.undo_stack.pop(0)

        item.setBackground(QColor(255, 255, 150))

        header_item = self.table_view.verticalHeaderItem(row)
        if not header_item:
            header_item = QTableWidgetItem(str(row + 1))
            self.table_view.setVerticalHeaderItem(row, header_item)

        if not header_item.text().endswith(' *'):
            header_item.setText(header_item.text() + ' *')
            header_item.setBackground(QColor(255, 255, 150))
            self.edited_rows.add(row)

    def open_table_menu(self, position):
        menu = QMenu()
        make_null_action = QAction("Make NULL", self)
        make_null_action.triggered.connect(self.make_null_selected_cells)
        menu.addAction(make_null_action)
        menu.exec_(self.table_view.viewport().mapToGlobal(position))

    def get_original_value(self, row, col):
        if not self.current_table_name or not db_manager.models: return ""
        TableClass = db_manager.models[self.current_table_name]
        session = db_manager.session
        engine = session.bind
        headers = [c.key for c in TableClass.__table__.columns]
        column_name = headers[col]
        primary_key_column = TableClass.__table__.primary_key.columns.values()[0].key
        primary_key_item = self.table_view.item(row, headers.index(primary_key_column))
        if primary_key_item:
            primary_key_value = primary_key_item.text().strip(' *')
            if not primary_key_value:  # Not a saved row
                return ""
            try:
                with engine.connect() as connection:
                    result = connection.execute(
                        text(f"SELECT {column_name} FROM {self.current_table_name} WHERE {primary_key_column} = :pk"),
                        {"pk": primary_key_value}).scalar()
                    return str(result) if result is not None else ""
            except Exception as e:
                print(f"Error fetching original value: {e}")
                return ""
        return ""

    def get_primary_key_column_index(self):
        if self.current_table_name and db_manager.models:
            TableClass = db_manager.models[self.current_table_name]
            try:
                primary_key_column = TableClass.__table__.primary_key.columns.values()[0].key
                headers = [column.key for column in TableClass.__table__.columns]
                return headers.index(primary_key_column)
            except (KeyError, IndexError):
                return None
        return None

    def save_edits(self):
        if not self.edited_cells and not self.new_rows:
            QMessageBox.information(self, "No Edits", "There are no unsaved changes to commit.")
            return

        if not self.current_table_name or not db_manager.session:
            QMessageBox.warning(self, "Warning", "Please select a table and ensure a database is connected.")
            return

        TableClass = db_manager.models[self.current_table_name]
        session = db_manager.session

        current_scroll_position = self.table_view.verticalScrollBar().value()
        validation_errors = []
        headers = [c.key for c in TableClass.__table__.columns]
        inspector = inspect(session.bind)
        column_info = {c['name']: c for c in inspector.get_columns(self.current_table_name)}
        all_changed_rows = self.edited_rows.union(self.new_rows.keys())
        for row_index in sorted(list(all_changed_rows)):
            for col_index, column_name in enumerate(headers):
                item = self.table_view.item(row_index, col_index)
                if not item: continue
                value = item.text()
                col_info = column_info.get(column_name)
                column_type, column_nullable = str(col_info['type']).upper(), col_info['nullable']
                is_null_or_empty = (value == "" or value == "None")
                if not column_nullable and is_null_or_empty: validation_errors.append(
                    f"Row {row_index + 1}, Col '{column_name}': Non-nullable field is empty.")
                if not is_null_or_empty:
                    try:
                        if "INTEGER" in column_type:
                            int(value)
                        elif "REAL" in column_type or "FLOAT" in column_type:
                            float(value)
                    except (ValueError, TypeError):
                        validation_errors.append(
                            f"Row {row_index + 1}, Col '{column_name}': Type mismatch. Expected {column_type}, got '{value}'.")
        if validation_errors:
            QMessageBox.warning(self, "Validation Error",
                                "Errors must be fixed before saving:\n\n" + "\n".join(validation_errors))
            return
        try:
            for row_index, temp_id in self.new_rows.items():
                new_object_data = {}
                for col_index, column_name in enumerate(headers):
                    if column_name == TableClass.__table__.primary_key.columns.values()[0].key: continue
                    item = self.table_view.item(row_index, col_index)
                    value = item.text() if item else None
                    column_obj = TableClass.__table__.columns.get(column_name)
                    if value in ["", "None", None]:
                        new_object_data[column_name] = None
                        continue
                    try:
                        if "INTEGER" in str(column_obj.type).upper():
                            new_object_data[column_name] = int(value)
                        elif "REAL" in str(column_obj.type).upper() or "FLOAT" in str(column_obj.type).upper():
                            new_object_data[column_name] = float(value)
                        elif "BOOLEAN" in str(column_obj.type).upper():
                            new_object_data[column_name] = value.lower() in ('true', 't', '1')
                        else:
                            new_object_data[column_name] = value
                    except (ValueError, TypeError):
                        pass
                session.add(TableClass(**new_object_data))
            for (row, col), original_value in self.edited_cells.items():
                if row in self.new_rows: continue
                column_name = headers[col]
                primary_key_column = TableClass.__table__.primary_key.columns.values()[0].key
                primary_key_item = self.table_view.item(row, headers.index(primary_key_column))
                if not primary_key_item: continue
                primary_key_value = primary_key_item.text().strip(' *')
                obj_to_update = session.query(TableClass).filter_by(**{primary_key_column: primary_key_value}).one()
                new_value = self.table_view.item(row, col).text()
                column_obj = TableClass.__table__.columns.get(column_name)
                if new_value in ["", "None", None]:
                    setattr(obj_to_update, column_name, None)
                    continue
                try:
                    if "INTEGER" in str(column_obj.type).upper():
                        setattr(obj_to_update, column_name, int(new_value))
                    elif "REAL" in str(column_obj.type).upper() or "FLOAT" in str(column_obj.type).upper():
                        setattr(obj_to_update, column_name, float(new_value))
                    elif "BOOLEAN" in str(column_obj.type).upper():
                        setattr(obj_to_update, column_name, new_value.lower() in ('true', 't', '1'))
                    else:
                        setattr(obj_to_update, column_name, new_value)
                except (ValueError, TypeError):
                    pass
            session.commit()
            QMessageBox.information(self, "Success", "Changes saved to database.")
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "Database Error", f"Failed to save changes: {e}")
            print(f"Error during save: {e}")
        finally:
            self.edited_cells.clear()
            self.new_rows.clear()
            self.undo_stack.clear()
            self.redo_stack.clear()
            self.undo_action.setEnabled(False)
            self.redo_action.setEnabled(False)
            self.edited_rows.clear()
            if self.current_table_name: self.populate_table_view(self.current_table_name)
            self.table_view.verticalScrollBar().setValue(current_scroll_position)

    def delete_selected_rows(self):
        selected_rows = sorted(list(set(item.row() for item in self.table_view.selectedItems())), reverse=True)
        if not selected_rows:
            QMessageBox.warning(self, "No Selection", "Please select one or more rows to delete.")
            return
        reply = QMessageBox.question(self, "Confirm Deletion",
                                     f"Are you sure you want to delete {len(selected_rows)} row(s)? This cannot be undone.",
                                     QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            session = models.DB_SESSION
            TableClass = models.DB_MODELS[self.current_table_name]
            primary_key_column = TableClass.__table__.primary_key.columns.values()[0].key
            rows_to_delete_from_db, new_rows_to_remove = [], []
            headers = [c.key for c in TableClass.__table__.columns]
            pk_col_idx = headers.index(primary_key_column)
            for row_idx in selected_rows:
                if row_idx in self.new_rows:
                    new_rows_to_remove.append(row_idx)
                else:
                    item = self.table_view.item(row_idx, pk_col_idx)
                    if item: rows_to_delete_from_db.append(item.text().strip(' *'))
            try:
                for pk_value in rows_to_delete_from_db:
                    obj_to_delete = session.query(TableClass).filter_by(**{primary_key_column: pk_value}).one()
                    session.delete(obj_to_delete)
                session.commit()
                QMessageBox.information(self, "Success",
                                        f"Deleted {len(rows_to_delete_from_db)} row(s) from the database.")
            except Exception as e:
                session.rollback()
                QMessageBox.critical(self, "Database Error", f"Failed to delete rows: {e}")
                print(f"Error during delete: {e}")
                return
            for row_idx in sorted(selected_rows, reverse=True): self.table_view.removeRow(row_idx)
            self.new_rows = {k if k < row_idx else k - 1: v for k, v in self.new_rows.items() if
                             k not in new_rows_to_remove}
            self.edited_cells = {(r if r < row_idx else r - 1, c): v for (r, c), v in self.edited_cells.items() if
                                 r not in selected_rows}

    def undo_edit(self):
        if not self.undo_stack: return
        last_edit = self.undo_stack.pop()
        self.redo_stack.append(last_edit)
        row, col, original_value = last_edit["row"], last_edit["col"], last_edit["original"]
        self.table_view.itemChanged.disconnect()
        item = self.table_view.item(row, col)
        if item:
            item.setText(original_value)
            # This logic can be simplified. If the cell is no longer in edited_cells, revert its color.
            if (row, col) in self.edited_cells:
                # If we reverted to the original value, remove it from the edited list
                if self.edited_cells[(row, col)] == original_value:
                    self.edited_cells.pop((row, col))

            # Check if any other cell in this row is still edited
            is_still_edited = any(r == row for r, c in self.edited_cells) or row in self.new_rows

            if not is_still_edited:
                self.edited_rows.discard(row)
                header_item = self.table_view.verticalHeaderItem(row)
                if header_item and header_item.text().endswith(' *'):
                    header_item.setText(header_item.text().strip(' *'))
                    header_item.setBackground(QColor(255, 255, 255))

            # Revert color if the cell is no longer considered "edited"
            if (row, col) not in self.edited_cells:
                item.setBackground(QColor(255, 255, 255))

        self.table_view.itemChanged.connect(self.handle_item_changed)
        self.undo_action.setEnabled(len(self.undo_stack) > 0)
        self.redo_action.setEnabled(True)

    def redo_edit(self):
        if not self.redo_stack: return
        last_undone_edit = self.redo_stack.pop()
        self.undo_stack.append(last_undone_edit)
        row, col, new_value = last_undone_edit["row"], last_undone_edit["col"], last_undone_edit["new"]
        self.table_view.itemChanged.disconnect()
        item = self.table_view.item(row, col)
        if item:
            item.setText(new_value)
            item.setBackground(QColor(255, 255, 150))
            self.edited_rows.add(row)
            self.edited_cells[(row, col)] = new_value  # Re-add to edited_cells
            header_item = self.table_view.verticalHeaderItem(row)
            if header_item and not header_item.text().endswith(' *'):
                header_item.setText(header_item.text() + ' *')
                header_item.setBackground(QColor(255, 255, 150))
        self.table_view.itemChanged.connect(self.handle_item_changed)
        self.undo_action.setEnabled(True)
        self.redo_action.setEnabled(len(self.redo_stack) > 0)