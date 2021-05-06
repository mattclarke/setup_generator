import re
import sys

from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import QAbstractTableModel, QModelIndex, Qt, pyqtSlot
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QApplication, QShortcut, QTableView

NUM_COLUMNS_IN_JIRA = 12
JIRA_COLUMNS_TO_INCLUDE = {2, 4, 7, 8, 9}


def extract_jira_table(text):
    table_data = []

    col_index = 0
    row = []
    for d in [x for x in re.split("\t\n*", text)]:
        if col_index < NUM_COLUMNS_IN_JIRA:
            row.append(d.strip())
            col_index += 1
        else:
            masked_row = [x for i, x in enumerate(row) if i in JIRA_COLUMNS_TO_INCLUDE]
            table_data.append(masked_row)
            row = [d.strip()]
            col_index = 1
    if row:
        masked_row = [x for i, x in enumerate(row) if i in JIRA_COLUMNS_TO_INCLUDE]
        table_data.append(masked_row)

    return table_data


def extract_table_from_clipboard_text(text):
    """
    Extracts 2-D tabular data from clipboard text.

    When sent to the clipboard, tabular data from Excel, etc. is represented as
    a text string with tabs for columns and newlines for rows.

    :param text: The clipboard text
    :return: tabular data
    """
    # Uses re.split because "A\n" represents two vertical cells one
    # containing "A" and one being empty.
    # str.splitlines will lose the empty cell but re.split won't
    return [[x for x in row.split("\t")] for row in re.split("\r?\n", text)]


def convert_table_to_clipboard_text(table_data):
    """
    Converts 2-D tabular data to clipboard text.

    :param table_data: 2D tabular data
    :return: clipboard text
    """
    return "\n".join(["\t".join(row) for row in table_data])


class GeneratorModel(QAbstractTableModel):
    def __init__(self, header_data, num_rows=25):
        super().__init__()

        self._header_data = header_data
        self._default_num_rows = num_rows
        self._table_data = self.empty_table(num_rows, len(header_data))

    def empty_table(self, rows, columns):
        return [[""] * columns for _ in range(rows)]

    def data(self, index, role):
        if role == Qt.DisplayRole or role == Qt.EditRole:
            return self._table_data[index.row()][index.column()]

    def setData(self, index, value, role):
        if role == Qt.EditRole:
            self._table_data[index.row()][index.column()] = value
            return True

    def rowCount(self, index):
        return len(self._table_data)

    def columnCount(self, index):
        return len(self._header_data)

    def flags(self, index):
        return Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsEditable

    def headerData(self, section, orientation, role):
        if role == Qt.DisplayRole and orientation == Qt.Horizontal:
            return self._header_data[section]
        if role == Qt.DisplayRole and orientation == Qt.Vertical:
            return section + 1

    def update_data_at_index(self, row, column, value):
        self._table_data[row][column] = value
        self.layoutChanged.emit()

    def update_data_from_clipboard(self, copied_data, top_left_index):
        # Copied data is tabular so insert at top-left most position
        for row_index, row_data in enumerate(copied_data):
            col_index = 0
            current_row = top_left_index[0] + row_index
            if current_row >= len(self._table_data):
                self.create_empty_row(current_row)

            index = 0
            while index < len(row_data):
                if top_left_index[1] + col_index < len(self._header_data):
                    current_column = top_left_index[1] + col_index
                    col_index += 1
                    self._table_data[current_row][current_column] = row_data[index]
                    index += 1
                else:
                    break

        self.layoutChanged.emit()

    def create_empty_row(self, position):
        self._table_data.insert(position, [""] * len(self._header_data))

    def removeRows(self, rows, index=QModelIndex()):
        for row in sorted(rows, reverse=True):
            self.beginRemoveRows(QModelIndex(), row, row)
            del self._table_data[row]
            self.endRemoveRows()
        return True

    def select_data(self, selected_indices):
        curr_row = -1
        row_data = []
        selected_data = []
        for row, column in selected_indices:
            if row != curr_row:
                if row_data:
                    selected_data.append(row_data)
                    row_data = []
            curr_row = row
            row_data.append(self._table_data[row][column])
        if row_data:
            selected_data.append(row_data)
        return selected_data


class GeneratorUI(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        uic.loadUi("form.ui", self)
        self._setup_table()

    def _setup_table(self):
        headers = [
            "Description",
            "NICOS Integration",
            "PV",
            "PV Type",
            "Read/Write",
            "NICOS name",
            "NICOS type",
            "Write PV",
            "Target PV",
            "Low level",
        ]

        self.model = GeneratorModel(headers)
        self.tableView.setModel(self.model)
        self.tableView.setSelectionMode(QTableView.ContiguousSelection)

        self._create_keyboard_shortcuts()

    def _create_keyboard_shortcuts(self):
        for key, to_call in [
            (QKeySequence.Paste, self._handle_table_paste),
            (QKeySequence.Cut, self._handle_cut_cells),
            (QKeySequence.Copy, self._handle_copy_cells),
            ("Ctrl+Backspace", self._delete_rows),
        ]:
            self._create_shortcut_key(key, to_call)

    def _create_shortcut_key(self, shortcut_keys, to_call):
        shortcut = QShortcut(shortcut_keys, self.tableView)
        shortcut.activated.connect(to_call)
        shortcut.setContext(Qt.WidgetShortcut)

    def _handle_table_paste(self):
        indices = []
        for index in self.tableView.selectedIndexes():
            indices.append((index.row(), index.column()))

        if not indices:
            return
        top_left = indices[0]

        data_type = QApplication.instance().clipboard().mimeData()

        if not data_type.hasText():
            # Don't paste images etc.
            return

        clipboard_text = QApplication.instance().clipboard().text()
        copied_table = extract_table_from_clipboard_text(clipboard_text)

        if len(copied_table) == 1:
            # Only one value, so put it in all selected cells
            self._do_bulk_update(copied_table[0][0])
            return

        self.model.update_data_from_clipboard(copied_table, top_left)

    def _handle_cut_cells(self):
        self._handle_copy_cells()
        self._handle_delete_cells()

    def _handle_delete_cells(self):
        for index in self.tableView.selectedIndexes():
            self.model.update_data_at_index(index.row(), index.column(), "")

    def _handle_copy_cells(self):
        selected_data = self._extract_selected_data()
        clipboard_text = convert_table_to_clipboard_text(selected_data)
        QApplication.instance().clipboard().setText(clipboard_text)

    def _delete_rows(self):
        rows_to_remove = set()
        for index in self.tableView.selectedIndexes():
            rows_to_remove.add(index.row())
        rows_to_remove = list(rows_to_remove)
        self.model.removeRows(rows_to_remove)

    def _do_bulk_update(self, value):
        for index in self.tableView.selectedIndexes():
            self.model.update_data_at_index(index.row(), index.column(), value)

    @pyqtSlot()
    def on_btnSanitise_clicked(self):
        sanitised = extract_table_from_clipboard_text(
            convert_table_to_clipboard_text(extract_jira_table(self.txtRawJira.text()))
        )

        self.model.update_data_from_clipboard(sanitised, (0, 0))

    def _extract_selected_data(self):
        selected_indices = []
        for index in self.tableView.selectedIndexes():
            selected_indices.append((index.row(), index.column()))

        selected_data = self.model.select_data(selected_indices)
        return selected_data


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GeneratorUI()
    window.show()
    app.exec_()
