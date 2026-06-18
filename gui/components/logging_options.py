import os
import subprocess
import sys
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QComboBox, QPushButton, QMessageBox
from PyQt6.QtGui import QFont
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
LOG_DIR = PROJECT_ROOT / "logs"

class LoggingOptionsWidget(QFrame):
    """Repurposed panel dedicated strictly to session logs, diagnostic levels, and output structures."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()

    def setup_ui(self):
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setStyleSheet("background-color: #1e1e1e; border-radius: 8px; padding: 12px;")
        
        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        
        title_label = QLabel("📋 System Logging & Directory Options")
        title_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #8ae9fd;")
        layout.addWidget(title_label)
        
        # Log Level Selection
        level_layout = QHBoxLayout()
        level_label = QLabel("Diagnostic Verbosity Level:")
        level_label.setStyleSheet("color: #ffffff;")
        self.level_input = QComboBox()
        self.level_input.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.level_input.setCurrentText("INFO")
        self.level_input.setStyleSheet("background-color: #2d2d2d; color: #ffffff; padding: 4px;")
        level_layout.addWidget(level_label)
        level_layout.addWidget(self.level_input)
        layout.addLayout(level_layout)
        
        # Preferences Checks
        self.save_raw_prompts = QCheckBox("Save pristine LLM system/user prompt wrappers to generation logs")
        self.save_raw_prompts.setChecked(True)
        self.save_raw_prompts.setStyleSheet("color: #ffffff;")
        layout.addWidget(self.save_raw_prompts)
        
        self.auto_clear_logs = QCheckBox("Automatically purge empty logging directories on completion anomalies")
        self.auto_clear_logs.setStyleSheet("color: #ffffff;")
        layout.addWidget(self.auto_clear_logs)
        
        # Directory Navigation Shortcuts
        folder_layout = QHBoxLayout()
        open_folder_btn = QPushButton("📂 Open Logs Directory")
        open_folder_btn.setStyleSheet("""
            QPushButton { background-color: #212121; color: #ffffff; border: 1px solid #3d3d3d; padding: 8px; border-radius: 4px; }
            QPushButton:hover { background-color: #333333; }
        """)
        open_folder_btn.clicked.connect(self.open_logs_folder)
        folder_layout.addWidget(open_folder_btn)
        layout.addLayout(folder_layout)
        layout.addStretch()

    def open_logs_folder(self):
        """Cross-platform diagnostic wrapper to jump right to the timestamped outputs."""
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        try:
            if sys.platform == "win32":
                os.startfile(LOG_DIR)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(LOG_DIR)])
            else:
                subprocess.Popen(["xdg-open", str(LOG_DIR)])
        except Exception as e:
            QMessageBox.critical(self, "Navigation Failure", f"Could not view path location:\n{str(e)}")