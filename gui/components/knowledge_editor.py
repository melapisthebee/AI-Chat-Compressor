"""
Manual knowledge editing interface for the knowledge core.
"""

import json
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QPushButton, QComboBox, QTextEdit, QMessageBox,
    QDialog, QDialogButtonBox, QSplitter, QGroupBox, QListWidget,
)
from PyQt6.QtCore import Qt, pyqtSignal

from database.connection import get_thread_session
from database.queries import get_project_knowledge, edit_knowledge_entry, delete_knowledge_entry


class KnowledgeEditorWidget(QFrame):
    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._current_project = None
        self._categories = {}
        self._selected_category = None
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        hdr = QHBoxLayout()
        hdr.addWidget(QLabel("Knowledge Editor"))
        hdr.addStretch()
        layout.addLayout(hdr)
        sel = QHBoxLayout()
        self.proj_combo = QComboBox()
        self.proj_combo.setFixedWidth(260)
        self.proj_combo.setEditable(True)
        self.proj_combo.setPlaceholderText("Select project...")
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.setFixedWidth(80)
        sel.addWidget(self.proj_combo)
        sel.addWidget(self.refresh_btn)
        layout.addLayout(sel)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        left = QGroupBox("Categories")
        lv = QVBoxLayout(left)
        self.cat_list = QListWidget()
        self.cat_list.currentTextChanged.connect(self._on_category_selected)
        lv.addWidget(self.cat_list)
        splitter.addWidget(left)
        right = QGroupBox("Category Content")
        rv = QVBoxLayout(right)
        self.editor = QTextEdit()
        self.editor.setPlaceholderText("Select a category to edit...")
        rv.addWidget(self.editor)
        btns = QHBoxLayout()
        self.save_btn = QPushButton("Save")
        self.save_btn.clicked.connect(self.save_current)
        btns.addWidget(self.save_btn)
        self.delete_btn = QPushButton("Delete")
        self.delete_btn.clicked.connect(self.delete_current)
        btns.addWidget(self.delete_btn)
        btns.addStretch()
        rv.addLayout(btns)
        splitter.addWidget(right)
        splitter.setSizes([280, 520])
        layout.addWidget(splitter)
        self.status = QLabel("")
        layout.addWidget(self.status)
        self.refresh_btn.clicked.connect(self._refresh_categories)

    def set_project(self, name: str):
        self._current_project = name
        self.proj_combo.setCurrentText(name)
        self._refresh_categories()

    def _refresh_categories(self):
        name = (self.proj_combo.currentText() or "").strip()
        if not name:
            return
        with get_thread_session() as db:
            from database.models import Project
            proj = db.query(Project).filter(Project.name == name).first()
            if not proj:
                self.status.setText("Project not found")
                return
            data = get_project_knowledge(db, proj.id)
        self._categories = data
        self.cat_list.clear()
        self.cat_list.addItems(sorted(data.keys()))
        self.status.setText(f"{len(data)} categories loaded" if data else "No knowledge entries")

    def _on_category_selected(self, cat: str):
        content = self._categories.get(cat, {})
        self.editor.setPlainText(json.dumps(content, indent=2) if isinstance(content, dict) else str(content))
        self._selected_category = cat

    def save_current(self):
        cat = getattr(self, "_selected_category", None)
        if not cat:
            QMessageBox.warning(self, "Nothing Selected", "Select a category first.")
            return
        name = (self.proj_combo.currentText() or "").strip()
        if not name:
            QMessageBox.warning(self, "No Project", "Select a project first.")
            return
        text = self.editor.toPlainText().strip()
        try:
            new_content = json.loads(text)
        except Exception:
            new_content = text
        with get_thread_session() as db:
            from database.models import Project
            proj = db.query(Project).filter(Project.name == name).first()
            if not proj:
                QMessageBox.critical(self, "Error", "Project not found")
                return
            edit_knowledge_entry(db, proj.id, cat, new_content)
        self.status.setText(f"Saved '{cat}'")
        self.changed.emit()

    def delete_current(self):
        cat = getattr(self, "_selected_category", None)
        if not cat:
            return
        ok = QMessageBox.question(
            self, "Delete Category",
            f"Delete '{cat}'? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if ok != QMessageBox.StandardButton.Yes:
            return
        name = (self.proj_combo.currentText() or "").strip()
        with get_thread_session() as db:
            from database.models import Project
            proj = db.query(Project).filter(Project.name == name).first()
            if proj:
                delete_knowledge_entry(db, proj.id, cat)
        self._refresh_categories()
        self.status.setText(f"Deleted '{cat}'")
        self.changed.emit()
