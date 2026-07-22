import json
from pathlib import Path
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QComboBox, QPushButton, QMessageBox
from PyQt6.QtGui import QFont
from PyQt6.QtCore import pyqtSignal

from config.settings import settings

API_SETTINGS_FILE = Path(__file__).resolve().parent.parent.parent / "storage" / "api_settings.json"


class ApiSettingsWidget(QFrame):
    """Widget for configuring LM Studio API connection and timeout settings."""

    settings_changed = pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setStyleSheet("background-color: #1e1e1e; border-radius: 8px; padding: 12px;")

        layout = QVBoxLayout(self)
        layout.setSpacing(14)

        title_label = QLabel("⚡ API Connection & Timeout Settings")
        title_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #8ae9fd;")
        layout.addWidget(title_label)

        # Description
        desc_label = QLabel("Configure how the system connects to LM Studio and handles request timeouts.")
        desc_label.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(desc_label)

        # Timeout per HTTP request
        timeout_layout = QHBoxLayout()
        timeout_label = QLabel("Request Timeout (seconds):")
        timeout_label.setStyleSheet("color: #ffffff;")
        self.timeout_input = QSpinBox()
        self.timeout_input.setRange(30, 600)
        self.timeout_input.setValue(settings.REQUEST_TIMEOUT)
        self.timeout_input.setStyleSheet(self._input_style())
        timeout_layout.addWidget(timeout_label)
        timeout_layout.addWidget(self.timeout_input)
        timeout_layout.addStretch()
        layout.addLayout(timeout_layout)

        # Max retries
        retry_layout = QHBoxLayout()
        retry_label = QLabel("Max Retries:")
        retry_label.setStyleSheet("color: #ffffff;")
        self.retry_input = QSpinBox()
        self.retry_input.setRange(0, 10)
        self.retry_input.setValue(settings.MAX_RETRIES)
        self.retry_input.setStyleSheet(self._input_style())
        retry_layout.addWidget(retry_label)
        retry_layout.addWidget(self.retry_input)
        retry_layout.addStretch()
        layout.addLayout(retry_layout)

        # Retry base delay
        delay_layout = QHBoxLayout()
        delay_label = QLabel("Retry Base Delay (seconds):")
        delay_label.setStyleSheet("color: #ffffff;")
        self.delay_input = QSpinBox()
        self.delay_input.setRange(1, 60)
        self.delay_input.setValue(settings.RETRY_BASE_DELAY)
        self.delay_input.setStyleSheet(self._input_style())
        delay_layout.addWidget(delay_label)
        delay_layout.addWidget(self.delay_input)
        delay_layout.addStretch()
        layout.addLayout(delay_layout)

        # Model selection
        model_layout = QHBoxLayout()
        model_label = QLabel("Default Compression Model:")
        model_label.setStyleSheet("color: #ffffff;")
        self.model_input = QComboBox()
        self.model_input.setEditable(True)
        self.model_input.setPlaceholderText("Enter LM Studio model name")
        self.model_input.setCurrentText(settings.DEFAULT_COMPRESSION_MODEL)
        self.model_input.setStyleSheet(self._input_style())
        model_layout.addWidget(model_label)
        model_layout.addWidget(self.model_input)
        model_layout.addStretch()
        layout.addLayout(model_layout)

        # Validation message
        self.validation_label = QLabel("")
        self.validation_label.setStyleSheet("color: #f44336; font-size: 11px;")
        layout.addWidget(self.validation_label)

        # Action Buttons
        button_layout = QHBoxLayout()

        apply_btn = QPushButton("Apply Settings")
        apply_btn.clicked.connect(self._apply_settings)
        apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #4caf50;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
        """)
        button_layout.addWidget(apply_btn)

        reset_btn = QPushButton("Reset to Defaults")
        reset_btn.clicked.connect(self._reset_defaults)
        reset_btn.setStyleSheet("""
            QPushButton {
                background-color: #212121;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #333333;
            }
        """)
        button_layout.addWidget(reset_btn)
        layout.addLayout(button_layout)

    def _input_style(self) -> str:
        return """
            QSpinBox, QComboBox {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 6px;
            }
            QComboBox::drop-down {
                border-left: 1px solid #3d3d3d;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #3d3d3d;
                border-radius: 2px;
                width: 16px;
            }
        """

    def _apply_settings(self):
        current_settings = {
            'request_timeout': self.timeout_input.value(),
            'max_retries': self.retry_input.value(),
            'retry_base_delay': self.delay_input.value(),
            'default_model': self.model_input.currentText(),
        }

        # Validate
        errors = []
        if current_settings['request_timeout'] < 30:
            errors.append("Timeout must be at least 30 seconds")
        if current_settings['max_retries'] < 0:
            errors.append("Max retries must be >= 0")
        if current_settings['retry_base_delay'] < 1:
            errors.append("Retry delay must be at least 1 second")

        if errors:
            self.validation_label.setText(f"❌ {'; '.join(errors)}")
            self.validation_label.setStyleSheet("color: #f44336; font-size: 11px;")
            return

        self.validation_label.setText("✓ Settings applied successfully!")
        self.validation_label.setStyleSheet("color: #4caf50; font-size: 11px;")

        self.settings_changed.emit(current_settings)
        
        # Persist to file
        try:
            API_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(API_SETTINGS_FILE, 'w') as f:
                json.dump(current_settings, f, indent=2)
        except Exception:
            pass

    def _reset_defaults(self):
        self.timeout_input.setValue(settings.REQUEST_TIMEOUT)
        self.retry_input.setValue(settings.MAX_RETRIES)
        self.delay_input.setValue(settings.RETRY_BASE_DELAY)
        self.model_input.setCurrentText(settings.DEFAULT_COMPRESSION_MODEL)

        self.validation_label.setText("✓ Settings reset to defaults")
        self.validation_label.setStyleSheet("color: #4caf50; font-size: 11px;")
