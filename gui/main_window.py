import os
import json
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, QTextEdit, QPushButton, QMessageBox, QApplication)
from PyQt6.QtCore import QThread, pyqtSignal

from database.connection import SessionLocal, init_db
from database.queries import get_or_create_project, list_all_projects, get_project_knowledge
from database.models import Project
from engine.parser import parse_lm_studio_file
from engine.compression import CompressionEngine

class CompressionWorker(QThread):
    """
    Worker thread tasked with processing the conversation through the LLM pipeline
    without freezing the GUI interface thread.
    """
    progress_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(dict, str)
    error_signal = pyqtSignal(str)

    def __init__(self, project_name: str, filepath: str):
        super().__init__()
        self.project_name = project_name
        self.filepath = filepath

    def run(self):
        db = SessionLocal()
        try:
            self.progress_signal.emit("Parsing source conversation log export file...")
            messages = parse_lm_studio_file(self.filepath)
            filename = os.path.basename(self.filepath)
            
            self.progress_signal.emit(f"Retrieving or constructing Project: '{self.project_name}'...")
            project = get_or_create_project(db, self.project_name)
            
            self.progress_signal.emit("Running sliding token window synchronization loop through local LLM...")
            engine = CompressionEngine()
            
            # Runs the dynamic context synchronization
            updated_knowledge = engine.process_and_adapt(db, project.id, messages, filename)
            
            self.finished_signal.emit(updated_knowledge, self.project_name)
        except Exception as e:
            self.error_signal.emit(str(e))
        finally:
            db.close()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Adaptive Conversation Sync Engine")
        self.resize(800, 600)
        
        # Initialize SQLite structure on launch
        init_db()
        
        # Core Dark Theme Base Stylesheet
        self.setStyleSheet("""
            QMainWindow { background-color: #121212; }
            QLabel { color: #ffffff; }
            QComboBox { 
                background-color: #1e1e1e; color: #ffffff; 
                border: 1px solid #3d3d3d; border-radius: 4px; padding: 6px; 
            }
            QComboBox QAbstractItemView {
                background-color: #1e1e1e; color: #ffffff;
                selection-background-color: #333333;
            }
            QTextEdit { 
                background-color: #1e1e1e; color: #8ae9fd; font-family: 'Consolas', 'Courier New';
                border: 1px solid #3d3d3d; border-radius: 4px; 
            }
            QPushButton {
                background-color: #212121; color: #ffffff;
                border: 1px solid #3d3d3d; border-radius: 4px; padding: 4px 12px;
            }
            QPushButton:hover {
                background-color: #333333; border: 1px solid #555555;
            }
        """)

        # Main Layout Construction
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        
        # Project Selector Field Row (Upgraded to Editable QComboBox)
        proj_layout = QHBoxLayout()
        proj_label = QLabel("Active Target Project Profile:")
        proj_label.setStyleSheet("font-weight: bold;")
        
        self.project_input = QComboBox()
        self.project_input.setEditable(True)
        self.project_input.setPlaceholderText("Select or type a project name...")
        
        proj_layout.addWidget(proj_label)
        proj_layout.addWidget(self.project_input)
        main_layout.addLayout(proj_layout)
        
        # Drag and Drop zone instance
        from gui.components.drop_zone import DropZone
        self.drop_zone = DropZone()
        self.drop_zone.file_dropped.connect(self.handle_incoming_file)
        main_layout.addWidget(self.drop_zone, stretch=2)
        
        # Output Logging Header Row (Pushes Copy button to the absolute right edge)
        log_header_layout = QHBoxLayout()
        log_label = QLabel("System Output / Current Project State Blueprint:")
        self.copy_btn = QPushButton("Copy Context State", self)
        self.copy_btn.setFixedWidth(140)
        self.copy_btn.clicked.connect(self.copy_state_to_clipboard)
        
        log_header_layout.addWidget(log_label)
        log_header_layout.addStretch()  # Acts as an expanding spring row divider
        log_header_layout.addWidget(self.copy_btn)
        main_layout.addLayout(log_header_layout)
        
        # Console Display Text Frame
        self.console_output = QTextEdit()
        self.console_output.setReadOnly(True)
        main_layout.addWidget(self.console_output, stretch=3)
        
        self.console_output.append("System Ready. Name or select your active project area above and drag in a log file.")

        # Wire up selection changes to pull historic snapshots automatically
        self.project_input.currentTextChanged.connect(self.load_project_history_to_screen)
        
        # Hydrate existing entries on boot
        self.refresh_project_dropdown()

    def refresh_project_dropdown(self):
        """Queries the database to hydrate the combobox profile selectors."""
        db = SessionLocal()
        try:
            projects = list_all_projects(db)
            self.project_input.blockSignals(True)
            self.project_input.clear()
            for p in projects:
                self.project_input.addItem(p.name)
            self.project_input.setCurrentIndex(-1)
            self.project_input.blockSignals(False)
        finally:
            db.close()

    def load_project_history_to_screen(self, project_name: str):
        """Pulls historical context records straight to the terminal if selected."""
        if not project_name.strip():
            return
            
        db = SessionLocal()
        try:
            project = db.query(Project).filter(Project.name == project_name.strip()).first()
            if project:
                knowledge = get_project_knowledge(db, project.id)
                if knowledge:
                    self.console_output.clear()
                    self.console_output.append(f"📂 LOADED EXISTING SNAPSHOT FOR PROJECT: {project_name}\n")
                    self.console_output.append("--- CURRENT ADAPTIVE KNOWLEDGE CORE STATE ---")
                    self.console_output.append(json.dumps(knowledge, indent=2))
                else:
                    self.console_output.clear()
                    self.console_output.append(f"📂 Profile '{project_name}' is active but contains no historical records yet.")
        finally:
            db.close()

    def handle_incoming_file(self, filepath: str):
        """Triggered when the drop zone captures a valid file."""
        project_name = self.project_input.currentText().strip()
        
        if not project_name:
            QMessageBox.warning(self, "Missing Project Marker", "Please provide a target project name before adding raw session data.")
            return
            
        # Lock UI inputs to prevent collision modifications during generation
        self.drop_zone.setAcceptDrops(False)
        self.project_input.setEnabled(False)
        self.copy_btn.setEnabled(False)
        
        # Spawn the processing lifecycle thread
        self.worker = CompressionWorker(project_name, filepath)
        self.worker.progress_signal.connect(self.update_status)
        self.worker.error_signal.connect(self.handle_worker_error)
        self.worker.finished_signal.connect(self.handle_worker_success)
        
        # MEMORY LEAK PREVENTION: Force C++ QThread object cleanup natively upon completion
        self.worker.finished.connect(self.worker.deleteLater)
        
        self.worker.start()

    def update_status(self, text: str):
        self.console_output.append(f"⚙️ {text}")

    def handle_worker_error(self, err_message: str):
        self.console_output.append(f"\n❌ CRITICAL CRASH IN PIPELINE LOOP:\n{err_message}\n")
        self.reset_ui_controls()
        QMessageBox.critical(self, "Pipeline Error Encountered", f"An execution boundary error occurred:\n{err_message}")

    def handle_worker_success(self, final_knowledge: dict, project_name: str):
        self.console_output.clear()
        self.console_output.append(f"✅ SUCCESSFUL UPDATE STRATIFICATION FOR PROJECT: {project_name}\n")
        self.console_output.append("--- UPDATED ADAPTIVE KNOWLEDGE CORE STATE ---")
        
        pretty_json = json.dumps(final_knowledge, indent=2)
        self.console_output.append(pretty_json)
        
        self.refresh_project_dropdown()
        self.project_input.setCurrentText(project_name)
        self.reset_ui_controls()

    def reset_ui_controls(self):
        """Re-enables user context inputs once background task processing ends."""
        self.drop_zone.setAcceptDrops(True)
        self.project_input.setEnabled(True)
        self.copy_btn.setEnabled(True)
    
    def copy_state_to_clipboard(self):
        """Copies the current adaptive knowledge text to the system clipboard."""
        state_text = self.console_output.toPlainText()
        
        if state_text.strip():
            clipboard = QApplication.clipboard()
            clipboard.setText(state_text)
            self.statusBar().showMessage("Context state copied to clipboard!", 3000)
        else:
            QMessageBox.warning(self, "Copy Failed", "The output area is currently empty.")

    def closeEvent(self, event):
        """
        Safely captures application shutdown attempts and forces the background worker 
        through the explicit Quit-Wait lifecycle execution pattern to prevent 
        'Destroyed while thread is still running' underlying C++ exceptions.
        """
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.console_output.append("\n⚠️ System shutting down: Halting background background generation loop...")
            self.worker.quit()
            self.worker.wait()
        event.accept()