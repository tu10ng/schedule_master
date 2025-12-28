from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt
from models import ViewMode

class CustomTitleBar(QWidget):
    """专用标题栏，控制窗口移动和基础 UI"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(35)
        self.setStyleSheet("background-color: #2A3039;")
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(10, 0, 5, 0)
        self.layout.setSpacing(5)
        
        self.title_label = QLabel("📋 ONI")
        self.title_label.setStyleSheet("color: #FFFFFF; font-weight: bold; font-family: 'Consolas';")
        self.layout.addWidget(self.title_label)
        self.layout.addStretch()
        
        self.setCursor(Qt.CursorShape.SizeAllCursor)

        # 钉住按钮 (仅在需要时外部控制显示)
        self.pin_btn = QPushButton("📌")
        self.pin_btn.setFixedSize(30, 30)
        self.pin_btn.setCheckable(True)
        self.pin_btn.setStyleSheet("""
            QPushButton { background: transparent; color: white; border: none; font-size: 14px; }
            QPushButton:hover { background: #3A4049; }
            QPushButton:checked { background: #4A90E2; color: #FFFFFF; border-radius: 4px; }
        """)
        self.pin_btn.setCursor(Qt.CursorShape.ArrowCursor)
        self.layout.addWidget(self.pin_btn)
        
        self.toggle_btn = QPushButton("→")
        self.toggle_btn.setFixedSize(30, 30)
        self.toggle_btn.setStyleSheet("""
            QPushButton { background: #3A4049; color: white; border: none; border-radius: 40px; font-weight: bold; font-size: 16px; }
            QPushButton:hover { background: #4A5059; }
        """)
        self.toggle_btn.setCursor(Qt.CursorShape.ArrowCursor)
        self.layout.addWidget(self.toggle_btn)
        
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.setStyleSheet("QPushButton { background: transparent; color: white; border: none; } QPushButton:hover { background: #e81123; }")
        self.close_btn.setCursor(Qt.CursorShape.ArrowCursor)
        self.layout.addWidget(self.close_btn)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.window().drag_pos = event.globalPosition().toPoint() - self.window().pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and hasattr(self.window(), 'drag_pos'):
            target_pos = event.globalPosition().toPoint() - self.window().drag_pos
            
            if self.window().current_mode == ViewMode.SIDEBAR:
                # 侧边栏模式：限制 X 轴，仅允许 Y 轴移动
                current_x = self.window().x()
                self.window().move(current_x, target_pos.y())
            else:
                # 全屏模式：自由移动
                self.window().move(target_pos)
            event.accept()
