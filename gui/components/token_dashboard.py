"""
Token Usage Dashboard Component

Displays compression metrics and token statistics per project:
- Compression ratio visualization
- Token usage breakdown
- Processing statistics
- Historical trends
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QProgressBar, QGridLayout, QScrollArea, QPushButton,
    QGroupBox, QTableWidget, QTableWidgetItem, QHeaderView
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont, QPalette, QColor


class TokenDashboardWidget(QFrame):
    """
    Dashboard widget showing token usage statistics and compression metrics.
    """
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.project_stats = {}  # Store stats per project
    
    def setup_ui(self):
        """Initialize the dashboard UI components."""
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)
        
        # Title
        title_label = QLabel("📊 Token Usage Dashboard")
        title_label.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #8ae9fd; margin-bottom: 8px;")
        main_layout.addWidget(title_label)
        
        # Summary Cards Layout
        summary_layout = QGridLayout()
        summary_layout.setSpacing(8)
        
        # Create summary cards
        self.card_raw_tokens = self._create_summary_card("Total Raw Tokens", "0", "#3d3d3d")
        self.card_compressed_tokens = self._create_summary_card("Compressed Tokens", "0", "#3d3d3d")
        self.card_compression_ratio = self._create_summary_card("Compression Ratio", "0%", "#3d3d3d")
        self.card_avg_processing_time = self._create_summary_card("Avg Processing Time", "0s", "#3d3d3d")
        
        summary_layout.addWidget(self.card_raw_tokens, 0, 0)
        summary_layout.addWidget(self.card_compressed_tokens, 0, 1)
        summary_layout.addWidget(self.card_compression_ratio, 1, 0)
        summary_layout.addWidget(self.card_avg_processing_time, 1, 1)
        
        main_layout.addLayout(summary_layout)
        
        # Progress Bar Section
        progress_group = QGroupBox("Token Budget Usage")
        progress_layout = QVBoxLayout(progress_group)
        
        self.budget_progress = QProgressBar()
        self.budget_progress.setRange(0, 100)
        self.budget_progress.setValue(0)
        self.budget_progress.setTextVisible(True)
        self.budget_progress.setStyleSheet("""
            QProgressBar {
                background-color: #1e1e1e;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                text-align: center;
            }
            QProgressBar::chunk {
                background-color: #4caf50;
                border-radius: 3px;
            }
        """)
        progress_layout.addWidget(self.budget_progress)
        
        budget_label = QLabel("0 / 10000 tokens used")
        budget_label.setStyleSheet("color: #888888; font-size: 11px;")
        progress_layout.addWidget(budget_label)
        
        main_layout.addWidget(progress_group)
        
        # Project Statistics Table
        table_group = QGroupBox("Project Statistics")
        table_layout = QVBoxLayout(table_group)
        
        self.stats_table = QTableWidget()
        self.stats_table.setColumnCount(6)
        self.stats_table.setHorizontalHeaderLabels([
            "Project", "Raw Tokens", "Compressed", "Ratio", "Chunks", "Status"
        ])
        self.stats_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.stats_table.setAlternatingRowColors(True)
        self.stats_table.setStyleSheet("""
            QTableWidget {
                background-color: #1e1e1e;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                gridline-color: #3d3d3d;
            }
            QTableWidget::item {
                padding: 8px;
            }
            QHeaderView::section {
                background-color: #2d2d2d;
                color: #ffffff;
                padding: 8px;
                border: none;
                font-weight: bold;
            }
        """)
        table_layout.addWidget(self.stats_table)
        
        main_layout.addWidget(table_group)
        
        # Action Buttons
        button_layout = QHBoxLayout()
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self.refresh_dashboard)
        refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #212121;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #333333;
                border: 1px solid #555555;
            }
        """)
        button_layout.addWidget(refresh_btn)
        
        export_btn = QPushButton("💾 Export Stats")
        export_btn.clicked.connect(self.export_statistics)
        export_btn.setStyleSheet("""
            QPushButton {
                background-color: #212121;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #333333;
                border: 1px solid #555555;
            }
        """)
        button_layout.addWidget(export_btn)
        
        button_layout.addStretch()
        main_layout.addLayout(button_layout)
    
    def _create_summary_card(self, title: str, value: str, bg_color: str) -> QFrame:
        """Create a summary statistic card."""
        card = QFrame()
        card.setFrameShape(QFrame.Shape.StyledPanel)
        card.setFrameShadow(QFrame.Shadow.Raised)
        card.setStyleSheet(f"background-color: {bg_color}; border-radius: 8px; padding: 12px;")
        
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 8, 12, 8)
        
        title_label = QLabel(title)
        title_label.setStyleSheet("color: #aaaaaa; font-size: 11px;")
        title_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(title_label)
        
        value_label = QLabel(value)
        value_label.setStyleSheet("color: #8ae9fd; font-size: 20px; font-weight: bold;")
        value_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(value_label)
        
        return card
    
    def update_dashboard(self, project_name: str, stats: dict):
        """
        Update dashboard with new statistics for a project.
        
        Args:
            project_name: Name of the project
            stats: Dictionary with statistics (raw_tokens, compressed_tokens, ratio, etc.)
        """
        # Store project stats
        self.project_stats[project_name] = stats
        
        # Update summary cards
        total_raw = sum(s.get('raw_tokens', 0) for s in self.project_stats.values())
        total_compressed = sum(s.get('compressed_tokens', 0) for s in self.project_stats.values())
        
        overall_ratio = (total_compressed / total_raw * 100) if total_raw > 0 else 0
        
        self.card_raw_tokens.findChild(QLabel, 1).setText(self._format_number(total_raw))
        self.card_compressed_tokens.findChild(QLabel, 1).setText(self._format_number(total_compressed))
        self.card_compression_ratio.findChild(QLabel, 1).setText(f"{overall_ratio:.1f}%")
        
        # Update progress bar
        max_tokens = 10000  # Default budget
        usage_percent = min((total_raw / max_tokens) * 100, 100)
        self.budget_progress.setValue(int(usage_percent))
        
        # Update table
        self._update_stats_table()
    
    def _update_stats_table(self):
        """Update the statistics table with project data."""
        self.stats_table.setRowCount(len(self.project_stats))
        
        for row, (project_name, stats) in enumerate(self.project_stats.items()):
            self.stats_table.setItem(row, 0, QTableWidgetItem(project_name))
            self.stats_table.setItem(row, 1, QTableWidgetItem(self._format_number(stats.get('raw_tokens', 0))))
            self.stats_table.setItem(row, 2, QTableWidgetItem(self._format_number(stats.get('compressed_tokens', 0))))
            
            ratio = stats.get('ratio', 0)
            ratio_item = QTableWidgetItem(f"{ratio:.1f}%")
            if ratio < 30:
                ratio_item.setForeground(QColor("#4caf50"))  # Green for good compression
            elif ratio < 60:
                ratio_item.setForeground(QColor("#ff9800"))  # Orange for moderate
            else:
                ratio_item.setForeground(QColor("#f44336"))  # Red for poor
            self.stats_table.setItem(row, 3, ratio_item)
            
            self.stats_table.setItem(row, 4, QTableWidgetItem(str(stats.get('chunks', 0))))
            
            # Status
            status = stats.get('status', 'Active')
            status_item = QTableWidgetItem(status)
            if status == 'Active':
                status_item.setForeground(QColor("#4caf50"))
            self.stats_table.setItem(row, 5, status_item)
    
    def _format_number(self, num: int) -> str:
        """Format large numbers with K/M suffixes."""
        if num >= 1000000:
            return f"{num / 1000000:.1f}M"
        elif num >= 1000:
            return f"{num / 1000:.1f}K"
        else:
            return str(num)
    
    def refresh_dashboard(self):
        """Refresh the dashboard display."""
        # This would typically reload data from database
        self._update_stats_table()
    
    def export_statistics(self):
        """Export statistics to a file."""
        # Placeholder for export functionality
        from PyQt6.QtWidgets import QMessageBox
        msg = QMessageBox()
        msg.setWindowTitle("Export Statistics")
        msg.setText("Statistics export functionality coming soon!")
        msg.setIcon(QMessageBox.Icon.Information)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.exec()
    
    def clear_dashboard(self):
        """Clear all dashboard data."""
        self.project_stats.clear()
        self.card_raw_tokens.findChild(QLabel, 1).setText("0")
        self.card_compressed_tokens.findChild(QLabel, 1).setText("0")
        self.card_compression_ratio.findChild(QLabel, 1).setText("0%")
        self.budget_progress.setValue(0)
        self.stats_table.setRowCount(0)


class TokenBudgetSettingsWidget(QFrame):
    """
    Widget for configuring token budget settings via UI.
    """
    
    settings_changed = None  # Signal to emit when settings change
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """Initialize the settings UI."""
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setFrameShadow(QFrame.Shadow.Raised)
        self.setStyleSheet("background-color: #1e1e1e; border-radius: 8px; padding: 12px;")
        
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        
        # Title
        title_label = QLabel("⚙️ Token Budget Settings")
        title_label.setFont(QFont("Segoe UI", 12, QFont.Weight.Bold))
        title_label.setStyleSheet("color: #8ae9fd;")
        layout.addWidget(title_label)
        
        # Max Target Tokens
        max_layout = QHBoxLayout()
        max_label = QLabel("Max Target Tokens:")
        max_label.setStyleSheet("color: #ffffff;")
        self.max_tokens_input = QSpinBox()
        self.max_tokens_input.setRange(1000, 100000)
        self.max_tokens_input.setValue(10000)
        self.max_tokens_input.setStyleSheet(self._input_style())
        max_layout.addWidget(max_label)
        max_layout.addWidget(self.max_tokens_input)
        layout.addLayout(max_layout)
        
        # Chunk Size
        chunk_layout = QHBoxLayout()
        chunk_label = QLabel("Chunk Size (tokens):")
        chunk_label.setStyleSheet("color: #ffffff;")
        self.chunk_size_input = QSpinBox()
        self.chunk_size_input.setRange(1000, 16000)
        self.chunk_size_input.setValue(8000)
        self.chunk_size_input.setStyleSheet(self._input_style())
        chunk_layout.addWidget(chunk_label)
        chunk_layout.addWidget(self.chunk_size_input)
        layout.addLayout(chunk_layout)
        
        # Overlap Size
        overlap_layout = QHBoxLayout()
        overlap_label = QLabel("Overlap (tokens):")
        overlap_label.setStyleSheet("color: #ffffff;")
        self.overlap_input = QSpinBox()
        self.overlap_input.setRange(200, 8000)
        self.overlap_input.setValue(2000)
        self.overlap_input.setStyleSheet(self._input_style())
        overlap_layout.addWidget(overlap_label)
        overlap_layout.addWidget(self.overlap_input)
        layout.addLayout(overlap_layout)
        
        # Preserve Recent Tokens
        preserve_layout = QHBoxLayout()
        preserve_label = QLabel("Preserve Recent Tokens:")
        preserve_label.setStyleSheet("color: #ffffff;")
        self.preserve_input = QSpinBox()
        self.preserve_input.setRange(500, 20000)
        self.preserve_input.setValue(5000)
        self.preserve_input.setStyleSheet(self._input_style())
        preserve_layout.addWidget(preserve_label)
        preserve_layout.addWidget(self.preserve_input)
        layout.addLayout(preserve_layout)
        
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
        
        # Validation message
        self.validation_label = QLabel("")
        self.validation_label.setStyleSheet("color: #f44336; font-size: 11px;")
        layout.addWidget(self.validation_label)
    
    def _input_style(self) -> str:
        """Return consistent input field styling."""
        return """
            QSpinBox {
                background-color: #2d2d2d;
                color: #ffffff;
                border: 1px solid #3d3d3d;
                border-radius: 4px;
                padding: 6px;
            }
            QSpinBox::up-button, QSpinBox::down-button {
                background-color: #3d3d3d;
                border-radius: 2px;
                width: 16px;
            }
        """
    
    def _apply_settings(self):
        """Apply current settings and validate."""
        settings = {
            'max_target_tokens': self.max_tokens_input.value(),
            'chunk_size_tokens': self.chunk_size_input.value(),
            'overlap_tokens': self.overlap_input.value(),
            'preserve_recent_tokens': self.preserve_input.value()
        }
        
        # Validate
        from engine.streaming_processor import token_budget_manager
        is_valid, error_msg = token_budget_manager.validate_settings(settings)
        
        if is_valid:
            self.validation_label.setText("✓ Settings applied successfully!")
            self.validation_label.setStyleSheet("color: #4caf50;")
            
            # Update streaming processor with new settings
            from engine.streaming_processor import streaming_processor
            streaming_processor.max_target_tokens = settings['max_target_tokens']
            streaming_processor.chunk_size_tokens = settings['chunk_size_tokens']
            streaming_processor.overlap_tokens = settings['overlap_tokens']
            streaming_processor.preserve_recent_tokens = settings['preserve_recent_tokens']
            
            # Emit signal if connected
            if self.settings_changed:
                self.settings_changed(settings)
        else:
            self.validation_label.setText(f"❌ {error_msg}")
            self.validation_label.setStyleSheet("color: #f44336;")
    
    def _reset_defaults(self):
        """Reset all settings to defaults."""
        from engine.streaming_processor import token_budget_manager
        defaults = token_budget_manager.reset_to_defaults()
        
        self.max_tokens_input.setValue(defaults['max_target_tokens'])
        self.chunk_size_input.setValue(defaults['chunk_size_tokens'])
        self.overlap_input.setValue(defaults['overlap_tokens'])
        self.preserve_input.setValue(defaults['preserve_recent_tokens'])
        
        self.validation_label.setText("✓ Settings reset to defaults")
        self.validation_label.setStyleSheet("color: #4caf50;")
    
    def get_current_settings(self) -> dict:
        """Get current settings as dictionary."""
        return {
            'max_target_tokens': self.max_tokens_input.value(),
            'chunk_size_tokens': self.chunk_size_input.value(),
            'overlap_tokens': self.overlap_input.value(),
            'preserve_recent_tokens': self.preserve_input.value()
        }


# Import required widgets
from PyQt6.QtWidgets import QSpinBox
