from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QStackedWidget
from PyQt6.QtCore import Qt, pyqtSignal

from gui.components.token_dashboard import TokenBudgetSettingsWidget
from gui.components.logging_options import LoggingOptionsWidget

class SettingsDialog(QDialog):
    """
    A secondary modal window that houses system configurations, 
    keeping the main workspace clear for active operations.
    """
    # Signal to forward settings changes back to the main window's dashboard
    settings_changed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("System Configuration")
        self.resize(800, 550)
        
        # Apply the matching industrial dark theme
        self.setStyleSheet("""
            QDialog { background-color: #121212; }
            QListWidget {
                background-color: #161616;
                border: 1px solid #2a2a2a;
                border-radius: 2px;
                outline: none;
            }
            QListWidget::item {
                color: #888888;
                padding: 12px 20px;
                border-bottom: 1px solid #1a1a1a;
                border-right: 2px solid transparent;
            }
            QListWidget::item:selected {
                background-color: #1e1e1e;
                color: #ffffff;
                border-right: 2px solid #8ae9fd;
            }
            QListWidget::item:hover:!selected {
                background-color: #1a1a1a;
                color: #cccccc;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Left Sidebar Navigation
        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(180)

        # Right Content Area
        self.workspace = QStackedWidget()

        # Link selection
        self.sidebar.currentRowChanged.connect(self.workspace.setCurrentIndex)

        layout.addWidget(self.sidebar)
        layout.addWidget(self.workspace, stretch=1)

        # [1] Token Budget Settings
        self.token_settings = TokenBudgetSettingsWidget()
        # Pass the signal straight through to the parent
        self.token_settings.settings_changed.connect(self.settings_changed.emit) 
        self.workspace.addWidget(self.token_settings)
        self.sidebar.addItem("[*] Token Budget")

        # [2] Logging Configuration
        self.logging_options = LoggingOptionsWidget()
        self.workspace.addWidget(self.logging_options)
        self.sidebar.addItem("[#] Logging")

        # Focus the first tab
        self.sidebar.setCurrentRow(0)