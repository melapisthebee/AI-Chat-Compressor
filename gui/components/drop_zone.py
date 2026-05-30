import os
from PyQt6.QtWidgets import QFrame, QVBoxLayout, QLabel
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent

SUPPORTED_EXTENSIONS = ('.txt', '.md', '.pdf', '.json')

class DropZone(QFrame):
    """
    A visual drag-and-drop container that filters for local .json files
    and emits a signal with the absolute file path when a drop occurs.
    """
    file_dropped = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)
        self.setObjectName("DropZone")
        
        # Modern dashed border look using stylesheet syntax
        self.setStyleSheet("""
            #DropZone {
                border: 2px dashed #5c5c5c;
                border-radius: 8px;
                background-color: #1e1e1e;
            }
            #DropZone[hover="true"] {
                border: 2px dashed #3a86ff;
                background-color: #2a2a2a;
            }
        """)
        
        layout = QVBoxLayout(self)
        self.label = QLabel("Drag & Drop LM Studio Chat Export Here\n(.json, .txt, .md, .pdf)", self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("color: #aaaaaa; font-size: 14px; font-weight: bold;")
        layout.addWidget(self.label)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            url = event.mimeData().urls()[0].toLocalFile()
            if url.lower().endswith(SUPPORTED_EXTENSIONS):  # ◄ Updated here
                self.setProperty("hover", "true")
                self.style().unpolish(self)
                self.style().polish(self)
                event.acceptProposedAction()
                return
        event.ignore()

    def dragLeaveEvent(self, event):
        """Resets the style sheet state when the cursor exits the widget boundaries."""
        self.setProperty("hover", "false")
        self.style().unpolish(self)
        self.style().polish(self)
        event.accept()

    def dropEvent(self, event: QDropEvent):
        self.setProperty("hover", "false")
        self.style().unpolish(self)
        self.style().polish(self)
        
        if event.mimeData().hasUrls():
            filepath = event.mimeData().urls()[0].toLocalFile()
            if os.path.exists(filepath) and filepath.lower().endswith(SUPPORTED_EXTENSIONS): # ◄ Updated here
                self.file_dropped.emit(filepath)
                event.acceptProposedAction()
                return
        event.ignore()