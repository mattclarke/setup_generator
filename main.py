import os
import sys

from PyQt5 import QtWidgets, uic
from PyQt5.QtCore import Qt, pyqtSlot
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import QApplication, QFileDialog, QShortcut, QTableView

from combo_widget import ComboWidget
from model import GeneratorModel
from utils import (convert_table_to_clipboard_text, extract_jira_table,
                   extract_table_from_clipboard_text)


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

        combo = ComboWidget(
            self,
            options=[
                "Readable",
                "AnalogMoveable",
                "DigitalMoveable",
                "MappedMoveable",
                "StringReadable",
                "StringMoveable",
            ],
        )
        self.tableView.setItemDelegateForColumn(6, combo)

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

    @pyqtSlot()
    def on_btnGenerate_clicked(self):
        filename = QFileDialog.getSaveFileName(
            self,
            "Save setup",
            os.path.expanduser("~"),
            "Setup files (*.py)",
            initialFilter="*.py",
        )[0]

        if not filename:
            return

        lines = [
            f"description = '{self.txtDescription.text()}'",
            "",
            f"pv_root = '{self.txtPvRoot.text()}:'",
            "",
            "devices = dict(",
        ]
        # This is the "clever" part
        table_data = self.model.get_data()
        for row in table_data:
            desc = row[0]
            pv = row[2]
            name = row[5]
            ntype = row[6]
            write = row[7]
            target = row[8]
            lowlevel = True if row[9] else False
            if not name:
                continue

            lines.append(f"\t{name}=device(")
            if ntype == "Readable":
                lines.append("\t\t'nicos_ess.devices.epics.pva.EpicsReadable',")
                lines.append(f"\t\tdescription='{desc}',")
                lines.append(f"\t\treadpv='{{}}{pv}'.format(pv_root),")
            elif ntype == "StringReadable":
                lines.append("\t\t'nicos_ess.devices.epics.pva.EpicsStringReadable',")
                lines.append(f"\t\tdescription='{desc}',")
                lines.append(f"\t\treadpv='{{}}{pv}'.format(pv_root),")
            elif ntype == "AnalogMoveable":
                lines.append("\t\t'nicos_ess.devices.epics.pva.EpicsAnalogMoveable',")
                lines.append(f"\t\tdescription='{desc}',")
                lines.append(f"\t\treadpv='{{}}{pv}'.format(pv_root),")
                lines.append(f"\t\twritepv='{{}}{write}'.format(pv_root),")
                if target:
                    lines.append(f"\t\ttargetpv='{{}}{target}'.format(pv_root),")
            elif ntype == "DigitalMoveable":
                lines.append("\t\t'nicos_ess.devices.epics.pva.EpicsDigitalMoveable',")
                lines.append(f"\t\tdescription='{desc}',")
                lines.append(f"\t\treadpv='{{}}{pv}'.format(pv_root),")
                lines.append(f"\t\twritepv='{{}}{write}'.format(pv_root),")
                if target:
                    lines.append(f"\t\ttargetpv='{{}}{target}'.format(pv_root),")
            elif ntype == "MappedMoveable":
                lines.append("\t\t'nicos_ess.devices.epics.pva.EpicsDigitalMoveable',")
                lines.append(f"\t\tdescription='{desc}',")
                lines.append(f"\t\treadpv='{{}}{pv}'.format(pv_root),")
                lines.append(f"\t\twritepv='{{}}{write}'.format(pv_root),")
            elif ntype == "StringMoveable":
                lines.append("\t\t'nicos_ess.devices.epics.pva.EpicsDigitalMoveable',")
                lines.append(f"\t\tdescription='{desc}',")
                lines.append(f"\t\treadpv='{{}}{pv}'.format(pv_root),")
                lines.append(f"\t\twritepv='{{}}{write}'.format(pv_root),")
            if lowlevel:
                lines.append("\t\tlowlevel=True,")
            lines.append("\t),")
        lines.append(")")
        print("\n".join(lines))
        with open(filename, "w") as file:
            file.write("\n".join(lines))


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = GeneratorUI()
    window.show()
    app.exec_()
