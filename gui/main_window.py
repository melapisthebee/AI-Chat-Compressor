import os
import json
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QLabel, QTextEdit, QPushButton, QMessageBox, QApplication, QFrame, QListWidget, QStackedWidget, QScrollArea, QProgressBar)
from PyQt6.QtCore import QThread, pyqtSignal, QTimer, Qt
from PyQt6.QtGui import QFont

from database.connection import SessionLocal, init_db
from database.queries import get_or_create_project, list_all_projects, get_project_knowledge
from database.models import Project
from engine.compression import CompressionEngine
from gui.components.token_dashboard import TokenDashboardWidget
from gui.components.conversation_preview import ConversationPreviewWidget
from gui.components.history_timeline import HistoryTimelineWidget

# Import parser function
from engine.parser import parse_lm_studio_file


class CompressionWorker(QThread):
    """
    Worker thread tasked with processing the conversation through the LLM pipeline
    without freezing the GUI interface thread.
    """
    progress_signal = pyqtSignal(str, str)  # phase, message
    stats_signal = pyqtSignal(str, dict)  # project_name, dashboard_data per chunk
    finished_signal = pyqtSignal(dict, str, dict)  # knowledge, project_name, dashboard_data
    error_signal = pyqtSignal(str)

    def __init__(self, project_name: str, filepath: str):
        super().__init__()
        self.project_name = project_name
        self.filepath = filepath

    def run(self):
        db = SessionLocal()
        try:
            self.progress_signal.emit("PARSING", "Parsing source conversation log export file...")
            messages = parse_lm_studio_file(self.filepath)
            print(f"Parsed {len(messages)} messages from file")
            filename = os.path.basename(self.filepath)
            
            self.progress_signal.emit("INITIALIZING", f"Retrieving or constructing Project: '{self.project_name}'...")
            project = get_or_create_project(db, self.project_name)
            print(f"Project '{project.name}' (ID: {project.id}) ready")
            
            self.progress_signal.emit("COMPRESSION", "Running sliding token window synchronization loop through local LLM...")
            
            def _live_stats(raw_tokens, compressed_tokens, ratio, chunks_processed):
                stats_data = {
                    'raw_tokens': raw_tokens,
                    'compressed_tokens': compressed_tokens,
                    'ratio': ratio,
                    'chunks': chunks_processed,
                    'status': 'Processing'
                }
                # Emit signal to update dashboard in real-time
                self.stats_signal.emit(self.project_name, stats_data)
            
            engine = CompressionEngine(stats_callback=_live_stats)
            
            # Runs the dynamic context synchronization with streaming support
            print("\nStarting compression engine process_and_adapt()...")
            self.progress_signal.emit("COMPRESSION", "Processing chunks through LLM extraction pass...")
            result = engine.process_and_adapt(db, project.id, messages, filename)
            
            # Handle both old and new return formats
            if isinstance(result, dict):
                updated_knowledge = result.get('knowledge', result)
                dashboard_data = result.get('dashboard_data', {})
                processing_stats = result.get('processing_stats', {})
                print(f"\nProcess completed: {len(updated_knowledge)} knowledge categories")
                if dashboard_data:
                    print(f"   Dashboard data: {dashboard_data}")
            else:
                updated_knowledge = result
                dashboard_data = {}
                processing_stats = {}
            
            self.progress_signal.emit("AUDIT", "Finalizing and committing knowledge updates...")
                
            self.finished_signal.emit(updated_knowledge, self.project_name, dashboard_data)
        except Exception as e:
            import traceback
            error_detail = f"{str(e)}\n{traceback.format_exc()}"
            print(f"Worker thread failed: {error_detail}")
            self.progress_signal.emit("ERROR", str(e))
            self.error_signal.emit(str(e))
        finally:
            db.close()


class CompressionWorkerWithMessages(QThread):
    """
    Worker thread that accepts pre-parsed messages for processing.
    Used when user selects specific messages from preview panel.
    """
    progress_signal = pyqtSignal(str, str)  # phase, message
    stats_signal = pyqtSignal(str, dict)  # project_name, dashboard_data per chunk
    finished_signal = pyqtSignal(dict, str, dict)  # knowledge, project_name, dashboard_data
    error_signal = pyqtSignal(str)

    def __init__(self, project_name: str, messages: list):
        super().__init__()
        self.project_name = project_name
        self.messages = messages

    def run(self):
        db = SessionLocal()
        try:
            self.progress_signal.emit("INITIALIZING", f"Retrieving or constructing Project: '{self.project_name}'...")
            project = get_or_create_project(db, self.project_name)
            print(f"Project '{project.name}' (ID: {project.id}) ready")
            
            self.progress_signal.emit("COMPRESSION", "Running sliding token window synchronization loop through local LLM...")
            
            def _live_stats(raw_tokens, compressed_tokens, ratio, chunks_processed):
                stats_data = {
                    'raw_tokens': raw_tokens,
                    'compressed_tokens': compressed_tokens,
                    'ratio': ratio,
                    'chunks': chunks_processed,
                    'status': 'Processing'
                }
                self.stats_signal.emit(self.project_name, stats_data)
            
            engine = CompressionEngine(stats_callback=_live_stats)
            
            # Use a dummy filename since we're processing pre-parsed messages
            filename = "selected_messages"
            
            print("\nStarting compression engine process_and_adapt()...")
            self.progress_signal.emit("COMPRESSION", f"Processing {len(self.messages)} selected messages through LLM extraction pass...")
            result = engine.process_and_adapt(db, project.id, self.messages, filename)
            
            if isinstance(result, dict):
                updated_knowledge = result.get('knowledge', result)
                dashboard_data = result.get('dashboard_data', {})
                print(f"\nProcess completed: {len(updated_knowledge)} knowledge categories")
            else:
                updated_knowledge = result
                dashboard_data = {}
            
            self.progress_signal.emit("AUDIT", "Finalizing and committing knowledge updates...")
                
            self.finished_signal.emit(updated_knowledge, self.project_name, dashboard_data)
        except Exception as e:
            import traceback
            error_detail = f"{str(e)}\n{traceback.format_exc()}"
            print(f"Worker thread failed: {error_detail}")
            self.progress_signal.emit("ERROR", str(e))
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
        self.current_state = "IDLE"
        self.blink_timer = QTimer(self)
        self.blink_timer.timeout.connect(self.toggle_blink_indicator)
        self.blink_visible = True
        
        # Store current project stats for dashboard
        self.current_project_stats = {}
        
        # Progress tracking
        self.current_phase = "IDLE"
        
        # Core Industrial Dark Theme Stylesheet
        self.setStyleSheet("""
            QMainWindow { background-color: #121212; }
            QLabel { color: #cccccc; }
            
            QComboBox { 
                background-color: #1e1e1e; color: #ffffff; 
                border: 1px solid #3d3d3d; border-radius: 2px; padding: 4px 8px; 
            }
            QComboBox::drop-down { border-left: 1px solid #3d3d3d; }
            QComboBox QAbstractItemView {
                background-color: #1e1e1e; color: #ffffff;
                selection-background-color: #333333;
                border: 1px solid #3d3d3d;
            }
            
            QTextEdit { 
                background-color: #1a1a1a; color: #8ae9fd; 
                font-family: 'Consolas', 'Courier New', monospace; font-size: 13px;
                border: 1px solid #2a2a2a; border-radius: 2px; 
            }
            
            QPushButton {
                background-color: #222222; color: #e0e0e0;
                border: 1px solid #3d3d3d; border-radius: 2px; padding: 4px 12px;
            }
            QPushButton:hover { background-color: #333333; border: 1px solid #5c5c5c; color: #ffffff; }
            QPushButton:pressed { background-color: #1a1a1a; }
            
            /* Vertical Sidebar Styling */
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

        # Main Layout Construction
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # --- TOP HEADER ROW ---
        proj_layout = QHBoxLayout()
        
        # Visual Status Indicator Dot with Phase Label
        self.status_indicator = QFrame()
        self.status_indicator.setFixedSize(12, 12)
        self.status_indicator.setStyleSheet("border-radius: 6px; background-color: #4caf50;")
        proj_layout.addWidget(self.status_indicator)
        
        # Phase Status Label
        self.phase_label = QLabel("IDLE")
        self.phase_label.setStyleSheet("font-weight: bold; margin-left: 8px; color: #8ae9fd; letter-spacing: 1px; font-size: 12px;")
        proj_layout.addWidget(self.phase_label)
        
        # Project Label
        proj_label = QLabel("// TARGET PROFILE")
        proj_label.setStyleSheet("font-weight: bold; margin-left: 16px; color: #888888; letter-spacing: 1px;")
        proj_layout.addWidget(proj_label)
        
        # Shortened Project Input (Locked Width)
        self.project_input = QComboBox()
        self.project_input.setEditable(True)
        self.project_input.setPlaceholderText("Select or initialize...")
        self.project_input.setFixedWidth(240) 
        proj_layout.addWidget(self.project_input)
        
        # Quick Settings Gear Icon
        self.quick_settings_btn = QPushButton("⚙️")
        self.quick_settings_btn.setFixedSize(28, 28)
        self.quick_settings_btn.setToolTip("Open Token Settings")
        self.quick_settings_btn.clicked.connect(self.open_settings_dialog)
        proj_layout.addWidget(self.quick_settings_btn)
        
        # Test Connection Button
        test_conn_btn = QPushButton("🔌 Test Connection")
        test_conn_btn.setFixedWidth(130)
        test_conn_btn.setToolTip("Test LM Studio API connectivity")
        test_conn_btn.clicked.connect(self.test_lm_studio_connection)
        test_conn_btn.setStyleSheet("""
            QPushButton {
                background-color: #212121;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 4px 8px;
            }
            QPushButton:hover {
                background-color: #333333;
            }
        """)
        proj_layout.addWidget(test_conn_btn)
        
        proj_layout.addStretch()
        main_layout.addLayout(proj_layout)
        
        # Progress Bar Section
        progress_layout = QHBoxLayout()
        progress_label = QLabel("PROGRESS >>")
        progress_label.setStyleSheet("color: #8ae9fd; font-weight: bold; margin-right: 8px;")
        progress_layout.addWidget(progress_label)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #1e1e1e;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                text-align: center;
                color: #ffffff;
                height: 20px;
            }
            QProgressBar::chunk {
                background-color: #4caf50;
                border-radius: 3px;
            }
        """)
        progress_layout.addWidget(self.progress_bar, stretch=1)
        
        main_layout.addLayout(progress_layout)
        
        # --- VERTICAL SIDEBAR WORKSPACE ---
        body_layout = QHBoxLayout()
        
        # Left Menu
        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(160)
        
        # Right Content Area
        self.workspace = QStackedWidget()
        
        # Link the sidebar clicks to the workspace pages
        self.sidebar.currentRowChanged.connect(self.workspace.setCurrentIndex)
        
        body_layout.addWidget(self.sidebar)
        body_layout.addWidget(self.workspace, stretch=1)
        main_layout.addLayout(body_layout, stretch=1)

       # ---------------------------------------------------------
        # REGISTER WORKSPACE PANELS (Order dictates Sidebar layout)
        # ---------------------------------------------------------

        # [1] Console Output (Set as primary active tab)
        console_scroll = QScrollArea()
        console_scroll.setWidgetResizable(True)
        console_scroll.setFrameShape(QFrame.Shape.NoFrame)
        console_scroll_content = QWidget()
        console_layout = QVBoxLayout(console_scroll_content)
        console_layout.setContentsMargins(0, 0, 0, 0)

        from gui.components.drop_zone import DropZone
        self.drop_zone = DropZone()
        self.drop_zone.file_dropped.connect(self.handle_incoming_file)
        console_layout.addWidget(self.drop_zone)
        
        log_header_layout = QHBoxLayout()
        log_label = QLabel("System Output / Current Project State Blueprint:")
        self.copy_btn = QPushButton("Copy Context State", self)
        self.copy_btn.setFixedWidth(140)
        self.copy_btn.clicked.connect(self.copy_state_to_clipboard)
        log_header_layout.addWidget(log_label)
        log_header_layout.addStretch()
        log_header_layout.addWidget(self.copy_btn)
        console_layout.addLayout(log_header_layout)
        
        self.console_output = QTextEdit()
        self.console_output.setReadOnly(True)
        console_layout.addWidget(self.console_output, stretch=1)
        console_scroll.setWidget(console_scroll_content)
        
        self.workspace.addWidget(console_scroll)
        self.sidebar.addItem("[>] Console")

        # [2] Token Dashboard
        self.token_dashboard = TokenDashboardWidget()
        self.workspace.addWidget(self.token_dashboard)
        self.sidebar.addItem("[+] Dashboard")

        # [3] Conversation Preview Panel
        self.conversation_preview = ConversationPreviewWidget()
        self.conversation_preview.process_selected_signal.connect(self.handle_conversation_selection)
        self.workspace.addWidget(self.conversation_preview)
        self.sidebar.addItem("[?] Preview")

        # [4] Project History Timeline
        self.history_timeline = HistoryTimelineWidget()
        self.workspace.addWidget(self.history_timeline)
        self.sidebar.addItem("[>] History")

        # Load startup settings
        from engine.streaming_processor import token_budget_manager, initialize_settings_from_file
        initialize_settings_from_file()
        current_settings = token_budget_manager.get_current_settings()
        self.token_dashboard.update_settings(current_settings)

        # Force UI to start on the Console tab
        self.sidebar.setCurrentRow(0)
        
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
        """Pulls historical context records and loads timeline for the selected project."""
        clean_name = project_name.strip()
        
        # Guard: blank or non-matching names clear the console entirely
        if not clean_name:
            self.console_output.clear()
            return
            
        db = SessionLocal()
        try:
            project = db.query(Project).filter(Project.name == clean_name).first()
            if project:
                knowledge = get_project_knowledge(db, project.id)
                if knowledge:
                    self.console_output.clear()
                    self.console_output.append(f"LOADED EXISTING SNAPSHOT FOR PROJECT: {project_name}\n")
                    self.console_output.append("--- CURRENT ADAPTIVE KNOWLEDGE CORE STATE ---")
                    self.console_output.append(json.dumps(knowledge, indent=2))
                else:
                    self.console_output.clear()
                    self.console_output.append(f"Profile '{project_name}' is active but contains no historical records yet.")
                
                # Load the history timeline for this project
                self.history_timeline.load_timeline(clean_name)
            else:
                # Name doesn't match any database entry - clear the view
                self.console_output.clear()
        finally:
            db.close()

    def test_lm_studio_connection(self):
        """Test LM Studio API connectivity."""
        self.console_output.append(">> Testing LM Studio connection...")
        
        try:
            from engine.compression import CompressionEngine
            engine = CompressionEngine()
            
            # Try to list models (health check)
            response = engine.client.models.list()
            models = list(response)
            
            if models:
                self.console_output.append(f"✓ SUCCESS: LM Studio is healthy. Available models: {len(models)}")
                QMessageBox.information(self, "Connection Test", f"LM Studio is connected and ready.\n\nAvailable models: {len(models)}")
            else:
                self.console_output.append("⚠ WARNING: LM Studio is running but returned no models")
                QMessageBox.warning(self, "Connection Test", "LM Studio is running but no models are loaded.\n\nPlease load a model in LM Studio and try again.")
                
        except Exception as e:
            error_msg = str(e)
            self.console_output.append(f"✗ FAILED: {error_msg}")
            QMessageBox.critical(self, "Connection Test Failed", f"Unable to connect to LM Studio:\n\n{error_msg}\n\nPlease ensure:\n• LM Studio is running\n• Server is enabled (Settings > Server)\n• Correct port (default: 1234)")

    def handle_conversation_selection(self, selected_messages):
        """Process only the selected messages from preview panel."""
        project_name = self.project_input.currentText().strip()
        
        if not project_name:
            QMessageBox.warning(self, "Missing Project Marker", "Please provide a target project name before processing.")
            return
        
        # Lock UI inputs
        self.drop_zone.setAcceptDrops(False)
        self.project_input.setEnabled(False)
        self.copy_btn.setEnabled(False)
        
        # Lock preview panel — visible but non-interactive
        self.conversation_preview.set_locked(True)
        
        # Set running indicator
        self.set_status_indicator("RUNNING")
        self.progress_bar.setValue(10)
        
        # Spawn the processing lifecycle thread with pre-parsed messages
        self.worker = CompressionWorkerWithMessages(project_name, selected_messages)
        self.worker.progress_signal.connect(self.update_status_with_phase)
        self.worker.stats_signal.connect(self._handle_live_stats_update)
        self.worker.error_signal.connect(self.handle_worker_error)
        self.worker.finished_signal.connect(self.handle_worker_success)
        
        self.worker.start()

    def handle_incoming_file(self, filepath: str):
        """Triggered when the drop zone captures a valid file."""
        project_name = self.project_input.currentText().strip()
        
        if not project_name:
            QMessageBox.warning(self, "Missing Project Marker", "Please provide a target project name before adding raw session data.")
            return
            
        # Parse messages first to show in preview
        try:
            self.console_output.append(">> Parsing conversation file...")
            messages = parse_lm_studio_file(filepath)
            self.conversation_preview.load_messages(messages)
            self.console_output.append(f">> Loaded {len(messages)} messages. Review and select messages to process.")
            
            # Store parsed messages for processing when user clicks "Process Selected"
            self.parsed_messages = messages
            self.pending_filepath = filepath
            
        except Exception as e:
            QMessageBox.critical(self, "Parse Error", f"Failed to parse conversation file:\n{str(e)}")
            self.reset_ui_controls()
            return

    def _handle_live_stats_update(self, project_name: str, stats_data: dict):
        """Handle live statistics updates during chunk processing."""
        # Update dashboard immediately with live stats
        self.token_dashboard.update_dashboard(project_name, stats_data)
        
        # Also update console with progress info
        if 'chunks' in stats_data and 'status' in stats_data:
            self.console_output.append(f"\nLive Stats: {stats_data['chunks']} chunks processed, Status: {stats_data['status']}")

    def update_status_with_phase(self, phase: str, message: str):
        """Update status with phase information and progress bar."""
        # Update console output
        self.console_output.append(f">> [{phase}] {message}")
        
        # Update progress bar based on phase
        phase_progress = {
            "PARSING": 10,
            "INITIALIZING": 25,
            "COMPRESSION": 30,  # Will be updated during processing
            "AUDIT": 85,
            "COMPLETE": 100,
            "ERROR": 0
        }
        
        progress_value = phase_progress.get(phase, self.progress_bar.value())
        if phase == "COMPRESSION":
            # During compression, we'll update incrementally via stats_signal
            pass
        else:
            self.progress_bar.setValue(progress_value)
        
        # Update status indicator based on phase
        state_map = {
            "PARSING": "RUNNING",
            "INITIALIZING": "RUNNING", 
            "COMPRESSION": "RUNNING",
            "AUDIT": "RUNNING",
            "COMPLETE": "SUCCESS",
            "ERROR": "CRITICAL"
        }
        
        if phase in state_map:
            self.set_status_indicator(state_map[phase])
        
        # Update phase label
        self.phase_label.setText(phase)

    def update_status(self, text: str):
        """Legacy method for backward compatibility."""
        self.console_output.append(f">> {text}")

    def handle_worker_error(self, err_message: str):
        """Handles pipeline errors with user-friendly notification logic."""
        self.console_output.append(f"\nProcessing Interrupted:\n{err_message}\n")
        
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
                self.console_output.append("\nRetrying operation...")
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
        """Converts technical error messages into user-friendly guidance."""
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
        self.console_output.append(f"SUCCESSFUL UPDATE STRATIFICATION FOR PROJECT: {project_name}\n")
        self.console_output.append("--- UPDATED ADAPTIVE KNOWLEDGE CORE STATE ---")
        
        pretty_json = json.dumps(final_knowledge, indent=2)
        self.console_output.append(pretty_json)
        
        # Always update dashboard with final statistics, even if dashboard_data is empty
        current_stats = {
            'raw_tokens': dashboard_data.get('total_raw_tokens', 0),
            'compressed_tokens': dashboard_data.get('total_compressed_tokens', 0),
            'ratio': dashboard_data.get('compression_ratio_decimal', 0) * 100,
            'chunks': dashboard_data.get('chunks_processed', 0),
            'status': 'Complete'
        } if dashboard_data else {
            'raw_tokens': 0,
            'compressed_tokens': 0,
            'ratio': 0,
            'chunks': 0,
            'status': 'Complete'
        }
        
        # Update dashboard with final stats
        self.token_dashboard.update_dashboard(project_name, current_stats)
        # Store stats for this project
        self.current_project_stats[project_name] = current_stats
        
        # Refresh timeline view
        self.history_timeline.load_timeline(project_name)
        
        self.refresh_project_dropdown()
        self.project_input.setCurrentText(project_name)
        self.reset_ui_controls()

    def reset_ui_controls(self):
        """Re-enables user context inputs once background task processing ends."""
        self.drop_zone.setAcceptDrops(True)
        self.project_input.setEnabled(True)
        self.copy_btn.setEnabled(True)
        # Unlock preview panel
        self.conversation_preview.set_locked(False)
        # Return to idle state
        self.progress_bar.setValue(0)
        self.phase_label.setText("IDLE")
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
        """Updates the visual status indicator dot based on application state."""
        # Guard: If a worker thread is running, block external state assignments unless it's an explicit failure/success signal
        if self.current_state == "RUNNING" and state not in ("SUCCESS", "CRITICAL", "DB_ERROR", "WARNING", "RUNNING"):
            print(f"⚠️ State change request '{state}' rejected. Thread pipeline locked to RUNNING context.")
            return

        self.current_state = state
        
        if self.blink_timer.isActive():
            self.blink_timer.stop()
        
        if state == "IDLE":
            self.status_indicator.setStyleSheet("border-radius: 6px; background-color: #4caf50;")
        elif state == "RUNNING":
            self.status_indicator.setStyleSheet("border-radius: 6px; background-color: #4caf50;")
            self.blink_timer.start(500)
        elif state == "SUCCESS":
            self.status_indicator.setStyleSheet("border-radius: 6px; background-color: #4caf50;")
        elif state == "WARNING":
            self.status_indicator.setStyleSheet("border-radius: 6px; background-color: #ff9800;")
        elif state in ("CRITICAL", "DB_ERROR"):
            self.status_indicator.setStyleSheet("border-radius: 6px; background-color: #f44336;")
            self.blink_timer.start(125)

    def toggle_blink_indicator(self):
        """Toggles the status indicator visibility for blinking effect."""
        self.blink_visible = not self.blink_visible
        if self.current_state == "RUNNING":
            color = "#4caf50" if self.blink_visible else "#1e3a1e"  # Green to dark green
        elif self.current_state in ("CRITICAL", "DB_ERROR"):
            color = "#f44336" if self.blink_visible else "#8b0000"  # Red to dark red
        else:
            return
        
        self.status_indicator.setStyleSheet(f"border-radius: 6px; background-color: {color};")

    def open_settings_dialog(self):
        """Opens the dedicated settings dialog window."""
        from gui.components.settings_dialog import SettingsDialog
        
        dialog = SettingsDialog(self)
        
        # Connect the dialog's settings change signal back to the dashboard
        dialog.settings_changed.connect(self.token_dashboard.update_settings)
        
        # Connect API settings changes to update the engine's client
        dialog.api_settings.settings_changed.connect(self._on_api_settings_changed)
        
        # Execute the dialog (this blocks the main window until closed)
        dialog.exec()
    
    def _on_api_settings_changed(self, data):
        """Apply API settings changes to the running configuration."""
        from config.settings import settings
        
        if 'request_timeout' in data:
            settings.REQUEST_TIMEOUT = data['request_timeout']
            self.console_output.append(f">> API timeout updated to {data['request_timeout']}s")
        if 'max_retries' in data:
            settings.MAX_RETRIES = data['max_retries']
        if 'retry_base_delay' in data:
            settings.RETRY_BASE_DELAY = data['retry_base_delay']
        if 'default_model' in data:
            settings.DEFAULT_COMPRESSION_MODEL = data['default_model']

    def closeEvent(self, event):
        """Safely captures application shutdown attempts and forces the background worker through the explicit Quit-Wait lifecycle execution pattern."""
        if hasattr(self, 'worker') and self.worker is not None:
            try:
                if self.worker.isRunning():
                    self.console_output.append("\nSystem shutting down: Halting background generation loop...")
                    self.worker.quit()
                    self.worker.wait(timeout=5000)  # Wait up to 5 seconds
            except RuntimeError:
                # Worker thread already deleted, ignore
                print("⚠️ Worker thread already cleaned up during shutdown")
            except Exception as e:
                print(f"⚠️ Error during worker shutdown: {e}")
        event.accept()
