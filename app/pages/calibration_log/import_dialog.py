from PyQt5.QtWidgets import QDialog, QVBoxLayout, QDialogButtonBox, QLabel, QFormLayout, QComboBox
from PyQt5.QtCore import Qt

class ImportCalibrationMappingDialog(QDialog):
    """
    Presents combo boxes to map parsed metrics (by type) to Installed_IDs.
    Expects `options_by_type` as { 'VNIR': [(label, installed_id), ...], 'SWIR': [...], 'RGB': [...], 'LiDAR': [...] }
    and `present_types` as list of metric types present in the parsed doc.
    """
    def __init__(self, options_by_type, present_types, parent=None, preselect=None):
        super().__init__(parent)
        self.setWindowTitle("Map Calibration Metrics to Sensors")
        self.setModal(True)

        self._combos = {}
        layout = QVBoxLayout(self)

        form = QFormLayout()
        preselect = preselect or {}
        for t in present_types:
            opts = options_by_type.get(t, [])
            combo = QComboBox()
            for label, iid in opts:
                combo.addItem(label, iid)
            if combo.count() == 0:
                combo.addItem("No matching sensors available", None)
                combo.setEnabled(False)
            else:
                # Apply preselection if provided
                target_iid = preselect.get(t)
                if target_iid is not None:
                    for idx in range(combo.count()):
                        if combo.itemData(idx) == target_iid:
                            combo.setCurrentIndex(idx)
                            break
            self._combos[t] = combo
            form.addRow(QLabel(f"{t} target sensor:"), combo)
        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons, alignment=Qt.AlignRight)

    def selections(self):
        """Return a dict mapping type -> selected Installed_ID (or None)."""
        out = {}
        for t, combo in self._combos.items():
            iid = combo.currentData()
            out[t] = iid
        return out
