from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QStackedWidget
from PyQt6.QtCore import Qt, pyqtSignal

from gui.components.token_dashboard import TokenBudgetSettingsWidget
from gui.components.logging_options import LoggingOptionsWidget
from gui.components.api_settings import ApiSettingsWidget

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

        # [3] API Settings
        self.api_settings = ApiSettingsWidget()
        self.api_settings.settings_changed.connect(self.settings_changed.emit)
        self.workspace.addWidget(self.api_settings)
        self.sidebar.addItem("[!] API Settings")

        # Load persisted API settings if available
        self._load_persisted_api_settings()

        # Focus the first tab
        self.sidebar.setCurrentRow(0)

    def _load_persisted_api_settings(self):
        """Load persisted API settings from file on dialog open."""
        import json
        from gui.components.api_settings import API_SETTINGS_FILE
        try:
            if API_SETTINGS_FILE.exists():
                with open(API_SETTINGS_FILE, 'r') as f:
                    saved = json.load(f)
                if 'request_timeout' in saved:
                    self.api_settings.timeout_input.setValue(saved['request_timeout'])
                if 'max_retries' in saved:
                    self.api_settings.retry_input.setValue(saved['max_retries'])
                if 'retry_base_delay' in saved:
                    self.api_settings.delay_input.setValue(saved['retry_base_delay'])
                if 'default_model' in saved:
                    self.api_settings.model_input.setCurrentText(saved['default_model'])
        except Exception as e:
            print(f"⚠️ Error loading persisted API settings: {e}")