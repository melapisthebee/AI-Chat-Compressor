import os
import json
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, QTextEdit, QPushButton, QMessageBox, QApplication, QFrame)
from PyQt6.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt6.QtGui import QFont

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
        
        # State management for visual indicator
        self.current_state = "IDLE"  # IDLE, RUNNING, SUCCESS, WARNING, CRITICAL, DB_ERROR
        self.blink_timer = QTimer(self)
        self.blink_timer.timeout.connect(self.toggle_blink_indicator)
        self.blink_visible = True
        
        # Settings action flag
        self.settings_opened = False
        
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
        
        # Project Selector Field Row (Upgraded to Editable QComboBox with visual indicators)
        proj_layout = QHBoxLayout()
        
        # Visual Status Indicator Dot
        self.status_indicator = QFrame()
        self.status_indicator.setFixedSize(12, 12)
        self.status_indicator.setStyleSheet("border-radius: 6px; background-color: #4caf50;")
        proj_layout.addWidget(self.status_indicator)
        
        # Settings Button (Placeholder)
        settings_btn = QPushButton("⚙️")
        settings_btn.setFixedSize(24, 24)
        settings_btn.setToolTip("Settings (Coming Soon)")
        settings_btn.clicked.connect(self.open_settings_placeholder)
        proj_layout.addWidget(settings_btn)
        
        # Project Label
        proj_label = QLabel("Active Target Project Profile:")
        proj_label.setStyleSheet("font-weight: bold; margin-left: 8px;")
        proj_layout.addWidget(proj_label)
        
        # Shortened Project Input (20% smaller than default)
        self.project_input = QComboBox()
        self.project_input.setEditable(True)
        self.project_input.setPlaceholderText("Select or type a project name...")
        self.project_input.setMinimumWidth(200)  # Reduced width
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
        
        # Set running indicator (blinking green)
        self.set_status_indicator("RUNNING")
        
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
        """
        Handles pipeline errors with smart notification logic.
        - Non-critical errors: console output + status bar message
        - Critical errors: console output + modal popup + red indicator
        """
        self.console_output.append(f"\n❌ CRITICAL CRASH IN PIPELINE LOOP:\n{err_message}\n")
        
        # Determine error severity and show appropriate UI feedback
        critical_keywords = ["database", "permission denied", "connection failed",
                           "api error", "timeout exceeded", "out of memory"]
        is_critical = any(keyword in err_message.lower() for keyword in critical_keywords)
        
        if is_critical:
            # Critical: Show popup + red blinking indicator
            self.set_status_indicator("CRITICAL")
            QMessageBox.critical(self, "Pipeline Error Encountered", f"Critical error:\n{err_message}")
        else:
            # Non-critical: Status bar message + yellow warning indicator
            self.set_status_indicator("WARNING")
            self.statusBar().showMessage(f"Warning: {err_message[:80]}", 5000)
        
        self.reset_ui_controls()

    def handle_worker_success(self, final_knowledge: dict, project_name: str):
        # Set success indicator
        self.set_status_indicator("SUCCESS")
        
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
        # Return to idle state
        self.set_status_indicator("IDLE")
    
    def copy_state_to_clipboard(self):
        """Copies the current adaptive knowledge text to the system clipboard."""
        state_text = self.console_output.toPlainText()
        
        if state_text.strip():
            clipboard = QApplication.clipboard()
            clipboard.setText(state_text)
            self.statusBar().showMessage("Context state copied to clipboard!", 3000)
        else:
            QMessageBox.warning(self, "Copy Failed", "The output area is currently empty.")
    
    def set_status_indicator(self, state):
        """
        Updates the visual status indicator dot based on application state.
        States: IDLE (solid green), RUNNING (blinking green), SUCCESS (solid green),
                WARNING (solid yellow), CRITICAL (blinking red), DB_ERROR (blinking red)
        """
        self.current_state = state
        
        # Stop any existing timer first
        if self.blink_timer.isActive():
            self.blink_timer.stop()
        
        # Determine color and blinking behavior based on state
        if state == "IDLE":
            self.status_indicator.setStyleSheet("border-radius: 6px; background-color: #4caf50;")  # Solid green
        elif state == "RUNNING":
            self.status_indicator.setStyleSheet("border-radius: 6px; background-color: #4caf50;")  # Green base
            self.blink_timer.start(500)  # Blink every 500ms
        elif state == "SUCCESS":
            self.status_indicator.setStyleSheet("border-radius: 6px; background-color: #4caf50;")  # Solid green
            self.blink_timer.stop()
        elif state == "WARNING":
            self.status_indicator.setStyleSheet("border-radius: 6px; background-color: #ff9800;")  # Orange/Yellow
            self.blink_timer.stop()
        elif state in ("CRITICAL", "DB_ERROR"):
            self.status_indicator.setStyleSheet("border-radius: 6px; background-color: #f44336;")  # Red base
            self.blink_timer.start(500)  # Blink every 500ms

    def toggle_blink_indicator(self):
        """
        Toggles the status indicator visibility for blinking effect.
        Used to signal active processing or critical error states.
        """
        self.blink_visible = not self.blink_visible
        if self.current_state == "RUNNING":
            color = "#4caf50" if self.blink_visible else "#1e3a1e"  # Green to dark green
        elif self.current_state in ("CRITICAL", "DB_ERROR"):
            color = "#f44336" if self.blink_visible else "#8b0000"  # Red to dark red
        else:
            return
        
        self.status_indicator.setStyleSheet(f"border-radius: 6px; background-color: {color};")

    def open_settings_placeholder(self):
        """
        Placeholder settings dialog - functionality to be implemented.
        Currently shows a modal with placeholder content.
        """
        msg = QMessageBox()
        msg.setWindowTitle("Settings (Coming Soon)")
        msg.setIcon(QMessageBox.Information)
        msg.setText("⚙️ Settings Panel\n\nThis feature is under development.\n\nPlanned features:\n• API Configuration\n• Token Budget Settings\n• Compression Model Selection\n• Database Management")
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec()

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
