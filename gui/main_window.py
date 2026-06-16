import os
import json
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, QTextEdit, QPushButton, QMessageBox, QApplication, QFrame, QTabWidget, QScrollArea)
from PyQt6.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt6.QtGui import QFont

from database.connection import SessionLocal, init_db
from database.queries import get_or_create_project, list_all_projects, get_project_knowledge
from database.models import Project
from engine.compression import CompressionEngine
from gui.components.token_dashboard import TokenDashboardWidget, TokenBudgetSettingsWidget

# Import parser function
from engine.parser import parse_lm_studio_file


class CompressionWorker(QThread):
    """
    Worker thread tasked with processing the conversation through the LLM pipeline
    without freezing the GUI interface thread.
    """
    progress_signal = pyqtSignal(str)
    finished_signal = pyqtSignal(dict, str, dict)  # knowledge, project_name, dashboard_data
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
            print(f"✓ Parsed {len(messages)} messages from file")
            filename = os.path.basename(self.filepath)
            
            self.progress_signal.emit(f"Retrieving or constructing Project: '{self.project_name}'...")
            project = get_or_create_project(db, self.project_name)
            print(f"✓ Project '{project.name}' (ID: {project.id}) ready")
            
            self.progress_signal.emit("Running sliding token window synchronization loop through local LLM...")
            engine = CompressionEngine()
            
            # Runs the dynamic context synchronization with streaming support
            print("\n🚀 Starting compression engine process_and_adapt()...")
            result = engine.process_and_adapt(db, project.id, messages, filename)
            
            # Handle both old and new return formats
            if isinstance(result, dict):
                updated_knowledge = result.get('knowledge', result)
                dashboard_data = result.get('dashboard_data', {})
                processing_stats = result.get('processing_stats', {})
                print(f"\n✅ Process completed: {len(updated_knowledge)} knowledge categories")
                if dashboard_data:
                    print(f"   Dashboard data: {dashboard_data}")
            else:
                updated_knowledge = result
                dashboard_data = {}
                processing_stats = {}
                
            self.finished_signal.emit(updated_knowledge, self.project_name, dashboard_data)
        except Exception as e:
            import traceback
            error_detail = f"{str(e)}\n{traceback.format_exc()}"
            print(f"❌ Worker thread failed: {error_detail}")
            self.error_signal.emit(str(e))
        finally:
            db.close()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Adaptive Conversation Sync Engine")
        self.resize(1200, 800)
        
        # Initialize SQLite structure on launch
        init_db()
        
        # State management for visual indicator
        self.current_state = "IDLE"  # IDLE, RUNNING, SUCCESS, WARNING, CRITICAL, DB_ERROR
        self.blink_timer = QTimer(self)
        self.blink_timer.timeout.connect(self.toggle_blink_indicator)
        self.blink_visible = True
        
        # Store current project stats for dashboard
        self.current_project_stats = {}
        
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
        
        # Settings Button
        settings_btn = QPushButton("⚙️ Settings")
        settings_btn.setFixedWidth(80)
        settings_btn.setToolTip("Configure Token Budget Settings")
        settings_btn.clicked.connect(self.open_settings_dialog)
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
        
        # Tab Widget for Dashboard and Console
        self.tab_widget = QTabWidget()
        
        # Tab 1: Console Output
        console_scroll = QScrollArea()
        console_scroll.setWidgetResizable(True)
        console_scroll.setFrameShape(QFrame.Shape.NoFrame)
        console_scroll_content = QWidget()
        console_layout = QVBoxLayout(console_scroll_content)
        
        # Drag and Drop zone instance
        from gui.components.drop_zone import DropZone
        self.drop_zone = DropZone()
        self.drop_zone.file_dropped.connect(self.handle_incoming_file)
        console_layout.addWidget(self.drop_zone)
        
        # Output Logging Header Row
        log_header_layout = QHBoxLayout()
        log_label = QLabel("System Output / Current Project State Blueprint:")
        self.copy_btn = QPushButton("Copy Context State", self)
        self.copy_btn.setFixedWidth(140)
        self.copy_btn.clicked.connect(self.copy_state_to_clipboard)
        
        log_header_layout.addWidget(log_label)
        log_header_layout.addStretch()
        log_header_layout.addWidget(self.copy_btn)
        console_layout.addLayout(log_header_layout)
        
        # Console Display Text Frame
        self.console_output = QTextEdit()
        self.console_output.setReadOnly(True)
        console_layout.addWidget(self.console_output, stretch=1)
        
        console_scroll.setWidget(console_scroll_content)
        self.tab_widget.addTab(console_scroll, "📋 Console Output")
        
        # Tab 2: Token Dashboard
        self.token_dashboard = TokenDashboardWidget()
        self.tab_widget.addTab(self.token_dashboard, "📊 Token Dashboard")
        
        # Tab 3: Settings
        self.settings_widget = TokenBudgetSettingsWidget()
        self.tab_widget.addTab(self.settings_widget, "⚙️ Token Settings")
        
        main_layout.addWidget(self.tab_widget, stretch=1)
        
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
            
        # Store filepath for potential retry
        self.pending_filepath = filepath
        
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
        Handles pipeline errors with user-friendly notification logic.
        - Non-critical errors: console output + status bar message
        - Critical errors: console output + helpful modal popup with retry option
        """
        self.console_output.append(f"\n⚠️ Processing Interrupted:\n{err_message}\n")
        
        # Determine error severity and show appropriate UI feedback
        critical_keywords = ["database", "permission denied", "connection failed",
                           "api error", "timeout exceeded", "out of memory"]
        is_critical = any(keyword in err_message.lower() for keyword in critical_keywords)
        
        if is_critical:
            # Critical: Show helpful popup with retry option + red blinking indicator
            self.set_status_indicator("CRITICAL")
            
            # Create a user-friendly error message
            friendly_message = self._get_friendly_error_message(err_message)
            
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle("⚠️ Processing Interrupted")
            msg_box.setIcon(QMessageBox.Icon.Warning)
            msg_box.setText(friendly_message)
            
            # Add Retry and Close buttons
            retry_button = msg_box.addButton("Retry", QMessageBox.ButtonRole.AcceptRole)
            close_button = msg_box.addButton("Close", QMessageBox.ButtonRole.RejectRole)
            msg_box.exec()
            
            # Check which button was clicked
            if msg_box.clickedButton() == retry_button:
                # User wants to retry - reset UI and restart
                self.console_output.append("\n🔄 Retrying operation...")
                self.reset_ui_controls()
                # Re-trigger the file processing if possible
                if hasattr(self, 'pending_filepath'):
                    self.handle_incoming_file(self.pending_filepath)
            else:
                # User chose to close - just reset UI
                self.reset_ui_controls()
        else:
            # Non-critical: Status bar message + yellow warning indicator
            self.set_status_indicator("WARNING")
            self.statusBar().showMessage(f"Warning: {err_message[:80]}", 5000)
            self.reset_ui_controls()
    
    def _get_friendly_error_message(self, err_message: str) -> str:
        """
        Converts technical error messages into user-friendly guidance.
        
        Args:
            err_message: The raw error message from the pipeline
            
        Returns:
            A user-friendly error description with actionable guidance
        """
        err_lower = err_message.lower()
        
        if "connection failed" in err_lower or "lm studio" in err_lower:
            return ("Unable to connect to LM Studio.\n\n"
                    "Please check:\n"
                    "• LM Studio is running\n"
                    "• The correct model is loaded\n"
                    "• Server address matches settings (default: localhost:1234)\n\n"
                    "After fixing, click 'Retry' to continue.")
        elif "timeout" in err_lower:
            return ("The request took too long to complete.\n\n"
                    "This can happen if:\n"
                    "• The conversation is very long\n"
                    "• LM Studio is processing slowly\n"
                    "• Network issues occurred\n\n"
                    "Please try again, or consider using a smaller file.")
        elif "database" in err_lower:
            return ("Database access error.\n\n"
                    "Please check:\n"
                    "• The database file is not corrupted\n"
                    "• You have write permissions to the storage folder\n\n"
                    "If the problem persists, try restarting the application.")
        elif "permission denied" in err_lower:
            return ("Access denied.\n\n"
                    "Please check:\n"
                    "• The file is not open in another program\n"
                    "• You have permissions to access the file\n\n"
                    "Try selecting a different file or restarting the app.")
        else:
            # Generic friendly message
            return ("An unexpected error occurred during processing.\n\n"
                    f"Error details: {err_message[:200]}\n\n"
                    "Please try again. If the problem persists, "
                    "consider restarting the application or "
                    "contacting support.")

    def handle_worker_success(self, final_knowledge: dict, project_name: str, dashboard_data: dict):
        # Set success indicator
        self.set_status_indicator("SUCCESS")
        
        self.console_output.clear()
        self.console_output.append(f"✅ SUCCESSFUL UPDATE STRATIFICATION FOR PROJECT: {project_name}\n")
        self.console_output.append("--- UPDATED ADAPTIVE KNOWLEDGE CORE STATE ---")
        
        pretty_json = json.dumps(final_knowledge, indent=2)
        self.console_output.append(pretty_json)
        
        # Update dashboard with new statistics
        if dashboard_data:
            self.token_dashboard.update_dashboard(project_name, dashboard_data)
            # Store stats for this project
            self.current_project_stats[project_name] = dashboard_data
        
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
            self.blink_timer.start(125)  # Blink every 125ms

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

    def open_settings_dialog(self):
        """
        Open the token budget settings panel.
        Switches to the settings tab in the main window.
        """
        # Switch to settings tab
        for i in range(self.tab_widget.count()):
            if self.tab_widget.tabText(i) == "⚙️ Token Settings":
                self.tab_widget.setCurrentIndex(i)
                break
        
        # Show a message that settings are available
        self.console_output.append("\n💡 Token Budget Settings panel is now active.\n")
        self.console_output.append("Adjust chunk sizes, overlap, and token budgets as needed.\n")

    def closeEvent(self, event):
        """
        Safely captures application shutdown attempts and forces the background worker 
        through the explicit Quit-Wait lifecycle execution pattern to prevent 
        'Destroyed while thread is still running' underlying C++ exceptions.
        """
        if hasattr(self, 'worker') and self.worker is not None:
            try:
                if self.worker.isRunning():
                    self.console_output.append("\n⚠️ System shutting down: Halting background generation loop...")
                    self.worker.quit()
                    self.worker.wait(timeout=5000)  # Wait up to 5 seconds
            except RuntimeError:
                # Worker thread already deleted, ignore
                print("⚠️ Worker thread already cleaned up during shutdown")
            except Exception as e:
                print(f"⚠️ Error during worker shutdown: {e}")
        event.accept()
