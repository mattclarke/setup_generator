from PyQt5.QtWidgets import QComboBox, QItemDelegate


class ComboWidget(QItemDelegate):
    def __init__(self, parent=None, options=None):
        super().__init__(parent)
        self._options = options

    def createEditor(self, parent, option, index):
        combobox = QComboBox(parent)
        combobox.addItems(self._options)
        return combobox

    def setEditorData(self, editor, index):
        value = index.data()
        if value:
            maxval = len(value)
            editor.setCurrentIndex(maxval - 1)

    def currentIndexChanged(self, index, value):
        pass
