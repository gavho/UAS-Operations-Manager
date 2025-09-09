# The following code is a Python representation of your flight_log.ui file.
# It was generated using the command: pyuic5 flight_log.ui -o flight_log_page.py
# Note: In a real application, you'd generate this file, but you'd
# typically create a separate class that inherits from it for your logic.

from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QWidget, QAction, QMessageBox, QTableWidgetItem

from app.database.manager import db_manager


class Ui_FlightLogPage(object):
    """
    Generated UI class from flight_log.ui.
    """
    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(1100, 800)
        MainWindow.setWindowTitle("Mission Log")
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.verticalLayout = QtWidgets.QVBoxLayout(self.centralwidget)
        self.verticalLayout.setObjectName("verticalLayout")
        self.missionTable = QtWidgets.QTableWidget(self.centralwidget)
        self.missionTable.setEditTriggers(
            QtWidgets.QAbstractItemView.DoubleClicked | QtWidgets.QAbstractItemView.SelectedClicked)
        self.missionTable.setAlternatingRowColors(True)
        self.missionTable.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.missionTable.setSortingEnabled(True)
        self.missionTable.setObjectName("missionTable")
        self.missionTable.setColumnCount(0)
        self.missionTable.setRowCount(0)
        self.missionTable.horizontalHeader().setCascadingSectionResizes(False)
        self.missionTable.horizontalHeader().setSortIndicatorShown(True)
        self.missionTable.horizontalHeader().setStretchLastSection(True)
        self.missionTable.verticalHeader().setCascadingSectionResizes(False)
        self.verticalLayout.addWidget(self.missionTable)
        self.groupBox = QtWidgets.QGroupBox(self.centralwidget)
        self.groupBox.setObjectName("groupBox")
        self.gridLayout = QtWidgets.QGridLayout(self.groupBox)
        self.gridLayout.setObjectName("gridLayout")
        self.missionIdLineEdit = QtWidgets.QLineEdit(self.groupBox)
        self.missionIdLineEdit.setEnabled(False)
        self.missionIdLineEdit.setObjectName("missionIdLineEdit")
        self.gridLayout.addWidget(self.missionIdLineEdit, 0, 1, 1, 1)
        self.missionIdLabel = QtWidgets.QLabel(self.groupBox)
        self.missionIdLabel.setObjectName("missionIdLabel")
        self.gridLayout.addWidget(self.missionIdLabel, 0, 0, 1, 1)
        self.missionNameLabel = QtWidgets.QLabel(self.groupBox)
        self.missionNameLabel.setObjectName("missionNameLabel")
        self.gridLayout.addWidget(self.missionNameLabel, 1, 0, 1, 1)
        self.missionNameLineEdit = QtWidgets.QLineEdit(self.groupBox)
        self.missionNameLineEdit.setObjectName("missionNameLineEdit")
        self.gridLayout.addWidget(self.missionNameLineEdit, 1, 1, 1, 1)
        self.missionDescriptionLabel = QtWidgets.QLabel(self.groupBox)
        self.missionDescriptionLabel.setObjectName("missionDescriptionLabel")
        self.gridLayout.addWidget(self.missionDescriptionLabel, 2, 0, 1, 1)
        self.missionDescriptionPlainTextEdit = QtWidgets.QPlainTextEdit(self.groupBox)
        self.missionDescriptionPlainTextEdit.setObjectName("missionDescriptionPlainTextEdit")
        self.gridLayout.addWidget(self.missionDescriptionPlainTextEdit, 2, 1, 1, 1)
        self.horizontalLayout = QtWidgets.QHBoxLayout()
        self.horizontalLayout.setObjectName("horizontalLayout")
        spacerItem = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem)
        self.updateMissionButton = QtWidgets.QPushButton(self.groupBox)
        self.updateMissionButton.setObjectName("updateMissionButton")
        self.horizontalLayout.addWidget(self.updateMissionButton)
        self.saveNewMissionButton = QtWidgets.QPushButton(self.groupBox)
        self.saveNewMissionButton.setObjectName("saveNewMissionButton")
        self.horizontalLayout.addWidget(self.saveNewMissionButton)
        spacerItem1 = QtWidgets.QSpacerItem(40, 20, QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Minimum)
        self.horizontalLayout.addItem(spacerItem1)
        self.gridLayout.addLayout(self.horizontalLayout, 3, 0, 1, 2)
        self.verticalLayout.addWidget(self.groupBox)
        MainWindow.setCentralWidget(self.centralwidget)

        self.retranslateUi(MainWindow)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        self.groupBox.setTitle(_translate("MainWindow", "Mission Details"))
        self.missionIdLabel.setText(_translate("MainWindow", "Mission ID:"))
        self.missionNameLabel.setText(_translate("MainWindow", "Mission Name:"))
        self.missionDescriptionLabel.setText(_translate("MainWindow", "Mission Description:"))
        self.updateMissionButton.setText(_translate("MainWindow", "Update Mission"))
        self.saveNewMissionButton.setText(_translate("MainWindow", "Save New Mission"))


class FlightLogPage(QWidget):
    """
    A QWidget representing the Flight Log page.
    This class inherits from the generated UI and adds application logic.
    """
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.ui = Ui_FlightLogPage()
        self.ui.setupUi(self)

        # Actions for the toolbar
        self.update_mission_action = QAction("Update Mission", self)
        self.update_mission_action.triggered.connect(self.update_mission)

        self.save_new_mission_action = QAction("Save New Mission", self)
        self.save_new_mission_action.triggered.connect(self.save_new_mission)

        # Connect UI buttons
        self.ui.updateMissionButton.clicked.connect(self.update_mission)
        self.ui.saveNewMissionButton.clicked.connect(self.save_new_mission)

        db_manager.connection_set.connect(self.load_missions)
        self.load_missions()

    def load_missions(self):
        if not db_manager.session:
            self.ui.missionTable.setRowCount(0)
            return

        missions = db_manager.get_all_missions()
        self.ui.missionTable.setRowCount(len(missions))
        self.ui.missionTable.setColumnCount(3)  # Assuming ID, Name, Description
        self.ui.missionTable.setHorizontalHeaderLabels(['ID', 'Name', 'Description'])

        for row, mission in enumerate(missions):
            self.ui.missionTable.setItem(row, 0, QTableWidgetItem(str(mission.get('id'))))
            self.ui.missionTable.setItem(row, 1, QTableWidgetItem(mission.get('name')))
            self.ui.missionTable.setItem(row, 2, QTableWidgetItem(mission.get('description')))

    def update_mission(self):
        """
        Placeholder function for updating a mission.
        """
        # Add your logic here to update the mission in the database
        QMessageBox.information(self, "Update", "Update Mission button clicked! (Logic not yet implemented)")

    def save_new_mission(self):
        """
        Placeholder function for saving a new mission.
        """
        # Add your logic here to save a new mission to the database
        QMessageBox.information(self, "Save", "Save New Mission button clicked! (Logic not yet implemented)")
