"""
Conversation Preview Panel Component

Displays parsed conversation messages before processing, allowing users to:
- Review conversation content
- Select specific messages for processing
- See message metadata (role, timestamp, token count)
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QListWidget, QListWidgetItem, QPushButton, QScrollArea,
    QCheckBox, QGroupBox, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QColor, QMouseEvent

from engine.tokenizer import tracker


class ConversationPreviewWidget(QFrame):
    """
    Widget displaying parsed conversation messages with preview capabilities.
    """
    
    process_selected_signal = pyqtSignal(list)  # Emit list of selected message indices
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.messages = []  # List of parsed message dicts
        self.selected_indices = set()
        self._locked = False
        self.setup_ui()
    
    def setup_ui(self):
        """Initialize the preview panel UI."""
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setStyleSheet("""
            QFrame {
                background-color: #1e1e1e;
                border-radius: 8px;
            }
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        
        # Header
        header_layout = QHBoxLayout()
        title_label = QLabel("📋 Conversation Preview Panel")
        title_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #8ae9fd;")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        select_all_btn = QPushButton("Select All")
        select_all_btn.setFixedWidth(100)
        select_all_btn.clicked.connect(self.select_all_messages)
        select_all_btn.setStyleSheet(self._button_style())
        select_all_btn.setObjectName("btn_select_all")
        header_layout.addWidget(select_all_btn)
        
        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.setFixedWidth(120)
        deselect_all_btn.clicked.connect(self.deselect_all_messages)
        deselect_all_btn.setStyleSheet(self._button_style())
        deselect_all_btn.setObjectName("btn_deselect_all")
        header_layout.addWidget(deselect_all_btn)
        
        main_layout.addLayout(header_layout)
        
        # Message list with scroll area
        self.message_list = QListWidget()
        self.message_list.setAlternatingRowColors(True)
        self.message_list.setStyleSheet("""
            QListWidget {
                background-color: #1a1a1a;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                color: #cccccc;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #2a2a2a;
            }
            QListWidget::item:selected {
                background-color: #2d4a2d;
                color: #8ae9fd;
            }
        """)
        self.message_list.itemClicked.connect(self.on_item_clicked)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setWidget(self.message_list)
        
        main_layout.addWidget(scroll_area, stretch=1)
        
        # Footer with stats and action button
        footer_layout = QHBoxLayout()
        
        self.stats_label = QLabel("0 messages | 0 tokens")
        self.stats_label.setStyleSheet("color: #888888; font-size: 11px;")
        footer_layout.addWidget(self.stats_label)
        
        footer_layout.addStretch()
        
        process_btn = QPushButton("▶ Process Selected")
        process_btn.setFixedWidth(140)
        process_btn.clicked.connect(self.emit_selected_messages)
        process_btn.setStyleSheet("""
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
        process_btn.setObjectName("btn_process")
        footer_layout.addWidget(process_btn)
        
        main_layout.addLayout(footer_layout)
        
        # Lock overlay widget (opaque dark grey, sits on top)
        self._overlay = QFrame(self)
        self._overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self._overlay.setStyleSheet("""
            QFrame {
                background-color: rgba(30, 30, 30, 220);
                border-radius: 8px;
            }
        """)
        self._overlay.setVisible(False)
        self._overlay.mousePressEvent = self._overlay_mouse_event
        
        # Lock label on overlay
        self._lock_label = QLabel("🔒 LOCKED — PROCESSING IN PROGRESS")
        self._lock_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        self._lock_label.setStyleSheet("color: #ff9800;")
        self._lock_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        overlay_layout = QVBoxLayout(self._overlay)
        overlay_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        overlay_layout.addWidget(self._lock_label)
        
        self._overlay.raise_()
        self._overlay.resize(self.size())
        
    def resizeEvent(self, event):
        """Keep overlay sized with the widget."""
        super().resizeEvent(event)
        self._overlay.resize(self.size())
    
    def _overlay_mouse_event(self, e: QMouseEvent):
        """Swallow all clicks on the overlay."""
        e.ignore()
    
    def set_locked(self, locked: bool):
        """Lock or unlock the preview panel."""
        self._locked = locked
        self._overlay.setVisible(locked)
        
        # Disable selection interaction on the list
        self.message_list.setEnabled(not locked)
        
        # Disable selection buttons
        btn = self.findChild(QPushButton, "btn_select_all")
        if btn:
            btn.setEnabled(not locked)
        
        btn = self.findChild(QPushButton, "btn_deselect_all")
        if btn:
            btn.setEnabled(not locked)
        
        # Grey out the process button
        btn = self.findChild(QPushButton, "btn_process")
        if btn:
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #555555;
                    color: #888888;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 16px;
                    font-weight: bold;
                }
            """)
            btn.setEnabled(False)
        else:
            # fallback: by object name
            for child in self.findChildren(QPushButton):
                if "Process" in child.text():
                    child.setStyleSheet("""
                        QPushButton {
                            background-color: #555555;
                            color: #888888;
                            border: none;
                            border-radius: 4px;
                            padding: 8px 16px;
                            font-weight: bold;
                        }
                    """)
                    child.setEnabled(False)
                    break
    
    def _button_style(self):
        return """
            QPushButton {
                background-color: #212121;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #333333;
            }
        """
    
    def load_messages(self, messages):
        """Load parsed messages into the preview panel."""
        self.messages = messages
        self.message_list.clear()
        self.selected_indices.clear()
        
        for idx, msg in enumerate(messages):
            role = msg.get('role', 'unknown')
            content_preview = msg.get('content', '')[:100]
            if len(msg.get('content', '')) > 100:
                content_preview += "..."
            
            token_count = tracker.count_tokens(msg.get('content', ''))
            
            # Create list item with formatted text
            item_text = f"[{role.upper()}] ({token_count} tokens): {content_preview}"
            item = QListWidgetItem(item_text)
            item.setData(Qt.ItemDataRole.UserRole, idx)
            item.setForeground(QColor("#8ae9fd" if role == "assistant" else "#cccccc"))
            
            self.message_list.addItem(item)
        
        self.update_stats()
    
    def on_item_clicked(self, item):
        """Toggle selection state when item is clicked."""
        idx = item.data(Qt.ItemDataRole.UserRole)
        
        if idx in self.selected_indices:
            self.selected_indices.remove(idx)
            item.setForeground(QColor("#cccccc"))
        else:
            self.selected_indices.add(idx)
            item.setForeground(QColor("#8ae9fd"))
        
        self.update_stats()
    
    def select_all_messages(self):
        """Select all messages in the list."""
        for row in range(self.message_list.count()):
            item = self.message_list.item(row)
            idx = item.data(Qt.ItemDataRole.UserRole)
            if idx not in self.selected_indices:
                self.selected_indices.add(idx)
                item.setForeground(QColor("#8ae9fd"))
        
        self.update_stats()
    
    def deselect_all_messages(self):
        """Deselect all messages."""
        self.selected_indices.clear()
        
        for row in range(self.message_list.count()):
            item = self.message_list.item(row)
            item.setForeground(QColor("#cccccc"))
        
        self.update_stats()
    
    def update_stats(self):
        """Update the stats label with current selection info."""
        total_messages = len(self.messages)
        selected_count = len(self.selected_indices)
        
        total_tokens = sum(
            tracker.count_tokens(msg.get('content', ''))
            for msg in self.messages
        )
        
        selected_tokens = sum(
            tracker.count_tokens(self.messages[idx].get('content', ''))
            for idx in self.selected_indices
        )
        
        if selected_count == total_messages:
            self.stats_label.setText(f"{selected_count}/{total_messages} messages | {selected_tokens:,} tokens (ALL)")
        else:
            self.stats_label.setText(f"{selected_count}/{total_messages} messages | {selected_tokens:,} / {total_tokens:,} tokens")
    
    def emit_selected_messages(self):
        """Emit the selected messages for processing."""
        if not self.selected_indices:
            QMessageBox.warning(
                self,
                "No Selection",
                "Please select at least one message to process."
            )
            return
        
        selected_messages = [self.messages[idx] for idx in sorted(self.selected_indices)]
        self.process_selected_signal.emit(selected_messages)
