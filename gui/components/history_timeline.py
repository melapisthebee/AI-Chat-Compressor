"""
Project History Timeline Component

Visualizes knowledge evolution over time with:
- Processing session timeline
- Knowledge growth metrics
- Compression ratio trends
- Interactive event markers
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QPushButton, QGroupBox, QToolTip
)
from PyQt6.QtCore import Qt, pyqtSignal, QRect
from PyQt6.QtGui import QFont, QColor

from database.connection import SessionLocal


class TimelineEvent:
    """Represents a single processing event in the timeline."""
    
    def __init__(self, session_id, timestamp, raw_tokens, compressed_tokens, 
                 ratio, filename, knowledge_categories):
        self.session_id = session_id
        self.timestamp = timestamp
        self.raw_tokens = raw_tokens
        self.compressed_tokens = compressed_tokens
        self.ratio = ratio
        self.filename = filename
        self.knowledge_categories = knowledge_categories


class HistoryTimelineWidget(QFrame):
    """
    Widget displaying project processing history as a timeline.
    """
    
    session_selected_signal = pyqtSignal(dict)  # Emit selected session data
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_project_name = None
        self.timeline_events = []
        self.setup_ui()
    
    def setup_ui(self):
        """Initialize the timeline UI."""
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
        title_label = QLabel("📅 Project History Timeline")
        title_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #8ae9fd;")
        header_layout.addWidget(title_label)
        
        header_layout.addStretch()
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.setFixedWidth(100)
        refresh_btn.clicked.connect(self.load_timeline)
        refresh_btn.setStyleSheet(self._button_style())
        header_layout.addWidget(refresh_btn)
        
        main_layout.addLayout(header_layout)
        
        # Timeline container with scroll area
        self.timeline_scroll = QScrollArea()
        self.timeline_scroll.setWidgetResizable(True)
        self.timeline_scroll.setFrameShape(QFrame.Shape.NoFrame)
        
        self.timeline_content = QWidget()
        self.timeline_layout = QVBoxLayout(self.timeline_content)
        self.timeline_layout.setSpacing(8)
        self.timeline_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        self.timeline_scroll.setWidget(self.timeline_content)
        main_layout.addWidget(self.timeline_scroll, stretch=1)
        
        # Summary stats footer
        summary_layout = QHBoxLayout()
        
        self.session_count_label = QLabel("Sessions: 0")
        self.session_count_label.setStyleSheet("color: #888888; font-size: 11px;")
        summary_layout.addWidget(self.session_count_label)
        
        summary_layout.addStretch()
        
        self.total_knowledge_label = QLabel("Knowledge Categories: 0")
        self.total_knowledge_label.setStyleSheet("color: #888888; font-size: 11px;")
        summary_layout.addWidget(self.total_knowledge_label)
        
        main_layout.addLayout(summary_layout)
    
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
    
    def load_timeline(self, project_name=None):
        """Load processing history for the current project."""
        if project_name:
            self.current_project_name = project_name
        
        if not self.current_project_name:
            self.clear_timeline()
            return
        
        db = SessionLocal()
        try:
            from database.models import Project, Session as ChatSession
            from sqlalchemy import desc
            
            project = db.query(Project).filter(Project.name == self.current_project_name).first()
            
            if not project:
                self.clear_timeline()
                return
            
            # Get all sessions for this project ordered by date
            session_records = db.query(ChatSession)\
                .filter(ChatSession.project_id == project.id)\
                .order_by(desc(ChatSession.imported_at))\
                .all()
            
            self.timeline_events = []
            
            for session in session_records:
                # Count knowledge categories from the snapshot (if stored)
                try:
                    categories_count = getattr(session, 'knowledge_snapshot', None)
                    if categories_count:
                        import json
                        knowledge = json.loads(categories_count) if isinstance(categories_count, str) else categories_count
                        categories_count = len(knowledge) if isinstance(knowledge, dict) else 0
                except Exception:
                    categories_count = 0
                
                raw_tokens = session.raw_token_count or 0
                compressed_tokens = session.compressed_token_count or 0
                ratio = (compressed_tokens / raw_tokens * 100) if raw_tokens > 0 else 0.0
                
                event = TimelineEvent(
                    session_id=session.id,
                    timestamp=session.imported_at,
                    raw_tokens=raw_tokens,
                    compressed_tokens=compressed_tokens,
                    ratio=ratio,
                    filename=session.filename,
                    knowledge_categories=categories_count
                )
                self.timeline_events.append(event)
            
            self.render_timeline()
            self.update_summary_stats()
            
        except Exception as e:
            print(f"Error loading timeline: {e}")
        finally:
            db.close()
    
    def render_timeline(self):
        """Render the timeline events."""
        # Clear existing events
        while self.timeline_layout.count():
            child = self.timeline_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        
        if not self.timeline_events:
            empty_label = QLabel("No processing history yet. Process a conversation to see timeline.")
            empty_label.setStyleSheet("color: #666666; font-style: italic;")
            empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.timeline_layout.addWidget(empty_label)
            return
        
        for event in self.timeline_events:
            event_widget = self._create_event_widget(event)
            self.timeline_layout.addWidget(event_widget)
        
        # Add spacing between events
        spacer = QWidget()
        spacer.setFixedHeight(10)
        self.timeline_layout.addWidget(spacer)
    
    def _create_event_widget(self, event):
        """Create a widget representing a single timeline event."""
        container = QFrame()
        container.setStyleSheet("""
            QFrame {
                background-color: #252525;
                border-radius: 6px;
                padding: 10px;
            }
            QFrame:hover {
                background-color: #2d2d2d;
            }
        """)
        
        layout = QVBoxLayout(container)
        layout.setSpacing(6)
        
        # Header row: timestamp + filename
        header_layout = QHBoxLayout()
        
        time_str = event.timestamp.strftime("%Y-%m-%d %H:%M") if event.timestamp else "Unknown date"
        time_label = QLabel(time_str)
        time_label.setStyleSheet("color: #8ae9fd; font-weight: bold; font-size: 12px;")
        header_layout.addWidget(time_label)
        
        header_layout.addStretch()
        
        filename_label = QLabel(f"📄 {event.filename}")
        filename_label.setStyleSheet("color: #888888; font-size: 11px;")
        header_layout.addWidget(filename_label)
        
        layout.addLayout(header_layout)
        
        # Stats row
        stats_layout = QHBoxLayout()
        
        raw_label = QLabel(f"Raw: {self._format_number(event.raw_tokens)}")
        raw_label.setStyleSheet("color: #cccccc; font-size: 11px;")
        stats_layout.addWidget(raw_label)
        
        stats_layout.addStretch(2)
        
        comp_label = QLabel(f"Compressed: {self._format_number(event.compressed_tokens)}")
        comp_label.setStyleSheet("color: #8ae9fd; font-size: 11px;")
        stats_layout.addWidget(comp_label)
        
        stats_layout.addStretch(2)
        
        ratio_color = self._get_ratio_color(event.ratio)
        ratio_label = QLabel(f"Ratio: {event.ratio:.1f}%")
        ratio_label.setStyleSheet(f"color: {ratio_color}; font-size: 11px; font-weight: bold;")
        stats_layout.addWidget(ratio_label)
        
        layout.addLayout(stats_layout)
        
        # Footer row: categories + action button
        footer_layout = QHBoxLayout()
        
        cat_label = QLabel(f"📊 {event.knowledge_categories} knowledge categories")
        cat_label.setStyleSheet("color: #666666; font-size: 10px;")
        footer_layout.addWidget(cat_label)
        
        footer_layout.addStretch()
        
        view_btn = QPushButton("View")
        view_btn.setFixedWidth(60)
        view_btn.clicked.connect(lambda checked=False, evt=event: self._on_session_selected(evt))
        view_btn.setStyleSheet("""
            QPushButton {
                background-color: #3d3d3d;
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 10px;
            }
            QPushButton:hover {
                background-color: #5c5c5c;
            }
        """)
        footer_layout.addWidget(view_btn)
        
        layout.addLayout(footer_layout)
        
        return container
    
    def _get_ratio_color(self, ratio):
        """Get color based on compression ratio."""
        if ratio < 30:
            return "#4caf50"  # Green - good compression
        elif ratio < 60:
            return "#ff9800"  # Orange - moderate
        else:
            return "#f44336"  # Red - poor compression
    
    def _format_number(self, num):
        """Format large numbers with K/M suffixes."""
        if num >= 1000000:
            return f"{num / 1000000:.1f}M"
        elif num >= 1000:
            return f"{num / 1000:.1f}K"
        return str(num)
    
    def _on_session_selected(self, event):
        """Handle session selection."""
        session_data = {
            'session_id': event.session_id,
            'timestamp': event.timestamp,
            'raw_tokens': event.raw_tokens,
            'compressed_tokens': event.compressed_tokens,
            'ratio': event.ratio,
            'filename': event.filename,
            'knowledge_categories': event.knowledge_categories
        }
        self.session_selected_signal.emit(session_data)
    
    def update_summary_stats(self):
        """Update the summary statistics labels."""
        if not self.timeline_events:
            self.session_count_label.setText("Sessions: 0")
            self.total_knowledge_label.setText("Knowledge Categories: 0")
            return
        
        total_sessions = len(self.timeline_events)
        latest_categories = self.timeline_events[0].knowledge_categories if self.timeline_events else 0
        
        self.session_count_label.setText(f"Sessions: {total_sessions}")
        self.total_knowledge_label.setText(f"Knowledge Categories: {latest_categories}")
    
    def clear_timeline(self):
        """Clear the timeline display."""
        self.timeline_events = []
        self.render_timeline()
