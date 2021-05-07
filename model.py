import copy

from PyQt5.QtCore import QAbstractTableModel, QModelIndex, Qt


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

    def get_data(self):
        return copy.deepcopy(self._table_data)
