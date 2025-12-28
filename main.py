#!/usr/bin/env python3
import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QHBoxLayout, QLabel, QPushButton, QCheckBox, QLineEdit,
    QScrollArea, QSizePolicy
)
from PyQt6.QtCore import (
    Qt, QTimer, QPoint, QRect, QSize, QPropertyAnimation, 
    QEasingCurve, pyqtSignal
)
from PyQt6.QtGui import QPalette, QColor, QFont, QCursor

from models.task_manager import TaskManager
from models.task import Task
from storage.task_storage import TaskStorage


class TaskWidget(QWidget):
    """单个任务小部件 - Excel式编辑"""
    
    deleted = pyqtSignal(str)  # task_id
    
    def __init__(self, task: Task, task_manager: TaskManager, parent=None):
        super().__init__(parent)
        self.task = task
        self.task_manager = task_manager
        self.save_timer = QTimer()
        self.save_timer.setSingleShot(True)
        self.save_timer.timeout.connect(self._save_content)
        self.init_ui()
        
    def init_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)
        
        # Checkbox
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(self.task.completed)
        self.checkbox.stateChanged.connect(self._on_completion_changed)
        self.checkbox.setStyleSheet("""
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border-radius: 3px;
                border: 2px solid #4A90E2;
                background-color: rgba(255, 255, 255, 0.1);
            }
            QCheckBox::indicator:checked {
                background-color: #4A90E2;
                border-color: #4A90E2;
            }
            QCheckBox::indicator:hover {
                border-color: #5BA3F5;
            }
        """)
        
        # 单行文本编辑 - Excel风格
        self.content_edit = QLineEdit()
        self.content_edit.setText(self.task.content)
        self.content_edit.setPlaceholderText("输入任务内容...")
        self.content_edit.textChanged.connect(self._on_text_changed)
        self.content_edit.setStyleSheet("""
            QLineEdit {
                background-color: rgba(255, 255, 255, 0.12);
                border: 1px solid rgba(74, 144, 226, 0.3);
                border-radius: 4px;
                color: #FFFFFF;
                padding: 6px 10px;
                font-size: 10pt;
            }
            QLineEdit:focus {
                border: 1px solid #4A90E2;
                background-color: rgba(255, 255, 255, 0.18);
            }
        """)
        
        # Delete button (hidden by default, shows on hover)
        self.delete_btn = QPushButton("✕")
        self.delete_btn.setFixedSize(24, 24)
        self.delete_btn.clicked.connect(self._on_delete_clicked)
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background: rgba(232, 17, 35, 0.7);
                color: white;
                border: none;
                border-radius: 12px;
                font-size: 12px;
                font-weight: bold;
            }
            QPushButton:hover {
                background: rgba(232, 17, 35, 0.9);
            }
        """)
        self.delete_btn.hide()
        
        layout.addWidget(self.checkbox)
        layout.addWidget(self.content_edit, 1)
        layout.addWidget(self.delete_btn)
        
        self.setLayout(layout)
        self.setStyleSheet("""
            TaskWidget {
                background-color: rgba(45, 48, 55, 0.6);
                border-radius: 6px;
                margin: 2px 0px;
            }
            TaskWidget:hover {
                background-color: rgba(55, 58, 65, 0.7);
            }
        """)
    
    def enterEvent(self, event):
        """Show delete button on hover"""
        self.delete_btn.show()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Hide delete button"""
        self.delete_btn.hide()
        super().leaveEvent(event)
    
    def _on_text_changed(self):
        """Debounced save on text change"""
        self.save_timer.start(500)  # 500ms后保存
    
    def _save_content(self):
        """Save content to task manager"""
        new_content = self.content_edit.text()
        if new_content != self.task.content:
            self.task_manager.update_task(self.task.id, content=new_content)
    
    def _on_completion_changed(self, state):
        """Update completion status"""
        completed = (state == Qt.CheckState.Checked.value)
        self.task_manager.update_task(self.task.id, completed=completed)
    
    def _on_delete_clicked(self):
        """Delete this task"""
        self.deleted.emit(self.task.id)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Window state
        self.is_collapsed = False
        self.docked_side = None
        self.normal_geometry = QRect(0, 0, 400, 550)
        self.snap_threshold = 50
        self.collapsed_width = 5
        self.mouse_press_pos = None
        
        # Task management
        self.task_manager = TaskManager()
        self.task_storage = TaskStorage()
        self.task_widgets = {}  # task_id -> TaskWidget
        
        # Auto-save timer
        self.auto_save_timer = QTimer()
        self.auto_save_timer.setSingleShot(True)
        self.auto_save_timer.timeout.connect(self._save_tasks)
        
        # Collapse timer
        self.collapse_timer = QTimer()
        self.collapse_timer.setSingleShot(True)
        self.collapse_timer.timeout.connect(self.animate_collapse)
        
        # Connect task manager signals
        self.task_manager.task_added.connect(self._on_task_added)
        self.task_manager.task_updated.connect(self._on_task_updated)
        self.task_manager.task_deleted.connect(self._on_task_deleted)
        
        self.init_ui()
        self.setup_window_properties()
        self.load_tasks()

    def init_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(10, 5, 10, 10)
        self.main_layout.setSpacing(8)
        
        # Title Bar
        self.title_bar = self.create_title_bar()
        self.main_layout.addWidget(self.title_bar)
        
        # Scrollable Task List
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background: rgba(255, 255, 255, 0.05);
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: rgba(74, 144, 226, 0.5);
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: rgba(74, 144, 226, 0.7);
            }
        """)
        
        # Task container
        self.task_container = QWidget()
        self.task_layout = QVBoxLayout(self.task_container)
        self.task_layout.setContentsMargins(0, 0, 0, 0)
        self.task_layout.setSpacing(4)
        self.task_layout.addStretch()
        
        self.scroll_area.setWidget(self.task_container)
        self.main_layout.addWidget(self.scroll_area, 1)
        
        # Add Task Button
        self.add_task_btn = QPushButton("+ 新增任务")
        self.add_task_btn.clicked.connect(self._add_new_task)
        self.add_task_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(74, 144, 226, 0.5);
                color: white;
                border: 1px dashed rgba(74, 144, 226, 0.8);
                border-radius: 6px;
                padding: 8px;
                font-weight: bold;
                font-size: 10pt;
            }
            QPushButton:hover {
                background-color: rgba(74, 144, 226, 0.7);
                border: 1px solid #4A90E2;
            }
            QPushButton:pressed {
                background-color: rgba(58, 115, 181, 0.8);
            }
        """)
        self.main_layout.addWidget(self.add_task_btn)

        self.setStyleSheet("""
            QMainWindow { 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, 
                    stop:0 rgba(40, 44, 52, 0.95), 
                    stop:1 rgba(25, 28, 34, 0.95));
                border: 1px solid rgba(74, 144, 226, 0.5);
                border-radius: 8px;
            }
        """)

    def create_title_bar(self):
        """创建标题栏"""
        title_bar = QWidget()
        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(5, 5, 0, 5)
        
        title_label = QLabel("📋 Schedule Master")
        title_label.setStyleSheet("color: white; font-weight: bold; font-family: 'Microsoft YaHei';")
        layout.addWidget(title_label)
        layout.addStretch()
        
        # Standard window buttons
        btn_style = """
            QPushButton { 
                background: transparent; 
                color: white; 
                border: none; 
                font-family: 'Segoe UI Symbol', 'Microsoft YaHei';
                font-size: 12px; 
                width: 32px; 
                height: 32px; 
            }
            QPushButton:hover { background: rgba(255, 255, 255, 0.15); }
            QPushButton#closeBtn:hover { background: #e81123; }
        """
        
        self.min_btn = QPushButton("—")
        self.max_btn = QPushButton("☐")
        self.close_btn = QPushButton("✕")
        self.close_btn.setObjectName("closeBtn")
        
        for btn in [self.min_btn, self.max_btn, self.close_btn]:
            btn.setStyleSheet(btn_style)
            layout.addWidget(btn)
            
        self.min_btn.clicked.connect(self.showMinimized)
        self.max_btn.clicked.connect(self.toggle_maximize)
        self.close_btn.clicked.connect(QApplication.quit)
        
        return title_bar

    def setup_window_properties(self):
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(400, 550)
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.width() - 410, 100)

    def load_tasks(self):
        """Load tasks from storage"""
        tasks = self.task_storage.load_tasks()
        if tasks:
            for task in tasks:
                self.task_manager.tasks.append(task)
                self._create_task_widget(task)
        else:
            # Create initial task if none exist
            self._add_new_task()

    def _add_new_task(self):
        """Add a new task"""
        task = self.task_manager.add_task("")
        # Focus on the new task
        if task.id in self.task_widgets:
            self.task_widgets[task.id].content_edit.setFocus()

    def _create_task_widget(self, task: Task):
        """Create UI widget for task"""
        task_widget = TaskWidget(task, self.task_manager)
        task_widget.deleted.connect(lambda tid: self.task_manager.delete_task(tid))
        
        # Insert before stretch
        self.task_layout.insertWidget(self.task_layout.count() - 1, task_widget)
        self.task_widgets[task.id] = task_widget

    def _on_task_added(self, task: Task):
        """Handle new task added"""
        self._create_task_widget(task)
        self._trigger_auto_save()

    def _on_task_updated(self, task: Task):
        """Handle task updated"""
        self._trigger_auto_save()

    def _on_task_deleted(self, task_id: str):
        """Handle task deleted"""
        if task_id in self.task_widgets:
            widget = self.task_widgets[task_id]
            self.task_layout.removeWidget(widget)
            widget.deleteLater()
            del self.task_widgets[task_id]
            self._trigger_auto_save()

    def _trigger_auto_save(self):
        """Trigger auto-save with debounce"""
        self.auto_save_timer.start(1000)  # 1秒后保存

    def _save_tasks(self):
        """Save all tasks to storage"""
        self.task_storage.save_tasks(self.task_manager.get_all_tasks())

    # Window management methods (unchanged)
    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
            self.max_btn.setText("☐")
            self.setStyleSheet(self.styleSheet().replace("border-radius: 0px;", "border-radius: 8px;"))
        else:
            self.showMaximized()
            self.max_btn.setText("❐")
            self.setStyleSheet(self.styleSheet().replace("border-radius: 8px;", "border-radius: 0px;"))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.mouse_press_pos = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.mouse_press_pos:
            if self.isMaximized():
                hit_x = event.globalPosition().toPoint().x()
                self.toggle_maximize()
                self.move(hit_x - self.width() // 2, 0)
                self.mouse_press_pos = event.globalPosition().toPoint() - self.pos()
            
            new_pos = event.globalPosition().toPoint() - self.mouse_press_pos
            self.move(new_pos)
            self.check_snap(new_pos)

    def mouseReleaseEvent(self, event):
        self.mouse_press_pos = None

    def check_snap(self, pos):
        screen = QApplication.primaryScreen().availableGeometry()
        if pos.x() < self.snap_threshold:
            self.move(0, pos.y())
            self.docked_side = "left"
        elif pos.x() + self.width() > screen.width() - self.snap_threshold:
            self.move(screen.width() - self.width(), pos.y())
            self.docked_side = "right"
        else:
            self.docked_side = None
            self.collapse_timer.stop()

    def enterEvent(self, event):
        if self.is_collapsed:
            self.animate_expand()
        self.collapse_timer.stop()

    def leaveEvent(self, event):
        if not self.rect().contains(self.mapFromGlobal(QCursor.pos())):
            if self.docked_side and not self.is_collapsed:
                self.collapse_timer.start(150)

    def animate_collapse(self):
        if self.is_collapsed or self.isMaximized(): return
        self.is_collapsed = True
        self.normal_geometry = self.geometry()
        
        screen = QApplication.primaryScreen().availableGeometry()
        target_x = 0 if self.docked_side == "left" else screen.width() - self.collapsed_width
        
        self.anim = QPropertyAnimation(self, b"geometry")
        self.anim.setDuration(250)
        self.anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.anim.setEndValue(QRect(target_x, self.y(), self.collapsed_width, self.height()))
        
        QTimer.singleShot(50, lambda: self.central_widget.hide())
        self.anim.start()

    def animate_expand(self):
        if not self.is_collapsed: return
        self.is_collapsed = False
        self.central_widget.show()
        
        self.expand_anim = QPropertyAnimation(self, b"geometry")
        self.expand_anim.setDuration(150)
        self.expand_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.expand_anim.setEndValue(self.normal_geometry)
        self.expand_anim.start()


if __name__ == "__main__":
    import sys
    import os
    if sys.platform == "linux":
        os.environ["QT_QPA_PLATFORM"] = "xcb"
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
