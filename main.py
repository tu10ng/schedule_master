#!/usr/bin/env python3
import sys
import os
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QHBoxLayout, QLabel, QPushButton, QCheckBox, QTextEdit
)
from PyQt6.QtCore import (
    Qt, QTimer, QPoint, QRect, QSize, QPropertyAnimation, 
    QEasingCurve, pyqtSignal
)
from PyQt6.QtGui import QPalette, QColor, QFont

class TaskWidget(QWidget):
    """单个任务小部件"""
    def __init__(self, task_number: int, parent=None):
        super().__init__(parent)
        self.task_number = task_number
        self.init_ui()
        
    def init_ui(self):
        layout = QHBoxLayout()
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(10)
        
        self.checkbox = QCheckBox()
        self.checkbox.setStyleSheet("""
            QCheckBox::indicator {
                width: 20px;
                height: 20px;
                border-radius: 4px;
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
        
        self.number_label = QLabel(f"任务 {self.task_number}")
        self.number_label.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        self.number_label.setStyleSheet("color: #FFFFFF; min-width: 60px;")
        
        self.content_edit = QTextEdit()
        self.content_edit.setPlaceholderText("在此输入任务内容...")
        self.content_edit.setMaximumHeight(80)
        self.content_edit.setStyleSheet("""
            QTextEdit {
                background-color: rgba(255, 255, 255, 0.15);
                border: 1px solid rgba(74, 144, 226, 0.5);
                border-radius: 6px;
                color: #FFFFFF;
                padding: 5px;
                font-size: 10pt;
            }
            QTextEdit:focus {
                border: 1px solid #4A90E2;
                background-color: rgba(255, 255, 255, 0.2);
            }
        """)
        
        layout.addWidget(self.checkbox)
        layout.addWidget(self.number_label)
        layout.addWidget(self.content_edit, 1)
        
        self.setLayout(layout)
        self.setStyleSheet("""
            TaskWidget {
                background-color: rgba(50, 50, 60, 0.7);
                border-radius: 8px;
                margin: 2px;
            }
        """)

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.is_collapsed = False
        self.docked_side = None
        self.normal_geometry = QRect(0, 0, 350, 500)
        self.snap_threshold = 50
        self.collapsed_width = 4
        self.mouse_press_pos = None
        
        self.collapse_timer = QTimer()
        self.collapse_timer.setSingleShot(True)
        self.collapse_timer.timeout.connect(self.animate_collapse)
        
        self.init_ui()
        self.setup_window_properties()

    def init_ui(self):
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(10, 5, 10, 10)
        
        # Custom Title Bar
        self.title_bar = QWidget()
        self.title_bar_layout = QHBoxLayout(self.title_bar)
        self.title_bar_layout.setContentsMargins(5, 5, 0, 5)
        
        self.title_label = QLabel("📋 Schedule Master")
        self.title_label.setStyleSheet("color: white; font-weight: bold; font-family: 'Microsoft YaHei';")
        self.title_bar_layout.addWidget(self.title_label)
        self.title_bar_layout.addStretch()
        
        # Standard Buttons
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
            self.title_bar_layout.addWidget(btn)
            
        self.min_btn.clicked.connect(self.showMinimized)
        self.max_btn.clicked.connect(self.toggle_maximize)
        self.close_btn.clicked.connect(self.close)
        
        self.main_layout.addWidget(self.title_bar)
        
        # Tasks
        for i in range(1, 4):
            self.main_layout.addWidget(TaskWidget(i))
        self.main_layout.addStretch()

        self.setStyleSheet("""
            QMainWindow { 
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 rgba(40, 44, 52, 0.95), stop:1 rgba(25, 28, 34, 0.95));
                border: 1px solid rgba(74, 144, 226, 0.5);
                border-radius: 8px;
            }
        """)

    def setup_window_properties(self):
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.resize(350, 500)
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.width() - 360, 100)

    def toggle_maximize(self):
        if self.isMaximized():
            self.showNormal()
            self.max_btn.setText("☐")
            self.setStyleSheet(self.styleSheet().replace("border-radius: 0px;", "border-radius: 8px;"))
        else:
            self.showMaximized()
            self.max_btn.setText("❐")
            # Remove rounded corners when maximized
            self.setStyleSheet(self.styleSheet().replace("border-radius: 8px;", "border-radius: 0px;"))

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.mouse_press_pos = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.mouse_press_pos:
            if self.isMaximized():
                # Allow dragging out of maximized state
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
        # Snapping action logic
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
        if self.docked_side and not self.is_collapsed:
            self.collapse_timer.start(200)

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
        
        # Smoothly hide content
        QTimer.singleShot(50, lambda: self.central_widget.hide())
        self.anim.start()

    def animate_expand(self):
        if not self.is_collapsed: return
        self.is_collapsed = False
        self.central_widget.show()
        
        self.expand_anim = QPropertyAnimation(self, b"geometry")
        self.expand_anim.setDuration(300)
        self.expand_anim.setEasingCurve(QEasingCurve.Type.OutBack)
        self.expand_anim.setEndValue(self.normal_geometry)
        self.expand_anim.start()

if __name__ == "__main__":
    import sys
    import os
    if sys.platform == "linux":
        os.environ["QT_QPA_PLATFORM"] = "xcb"
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
