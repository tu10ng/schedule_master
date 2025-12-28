#!/usr/bin/env python3
"""
Schedule Master - Excel Grid System with Dual-Mode View
基于单元格索引的坐标系统 + 双视图模式
"""
import sys
import os
from dataclasses import dataclass
from typing import List
from enum import Enum
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QHBoxLayout, QLabel, QPushButton, QScrollArea
)
from PyQt6.QtCore import Qt, QRect, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QCursor


# 网格常量
CELL_WIDTH = 60   # 每个单元格宽度(像素)
CELL_HEIGHT = 50  # 每个单元格高度(像素)


class ViewMode(Enum):
    """视图模式"""
    SIDEBAR = 1      # 侧边栏模式
    FULLSCREEN = 2   # 全屏模式


@dataclass
class Task:
    """任务数据模型 - 基于单元格索引"""
    title: str
    row_index: int      # 行索引(人员)
    col_index: int      # 列索引(开始时间)
    duration: int = 1   # 持续时间(单元格数)
    color: str = "#5B859E"
    
    def get_pixel_rect(self, row_offset_y: int = 0) -> QRect:
        """计算任务的像素矩形(完全填充格子)"""
        x = self.col_index * CELL_WIDTH
        y = row_offset_y  # 使用传入的行偏移
        width = self.duration * CELL_WIDTH
        height = CELL_HEIGHT
        return QRect(x, y, width, height)


class PersonRow(QWidget):
    """人员行 - 包含名字和网格"""
    
    def __init__(self, person_name: str, tasks: List[Task], cols: int = 24, parent=None):
        super().__init__(parent)
        self.person_name = person_name
        self.tasks = tasks
        self.cols = cols
        
        # 设置固定大小
        canvas_width = cols * CELL_WIDTH + 120  # 加上名字列
        canvas_height = CELL_HEIGHT
        self.setFixedSize(canvas_width, canvas_height)
    
    def paintEvent(self, event):
        """绘制人员行"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 1. 绘制背景
        painter.fillRect(self.rect(), QColor("#1F2329"))
        
        # 2. 绘制名字列
        name_rect = QRect(0, 0, 120, CELL_HEIGHT)
        painter.fillRect(name_rect, QColor("#2A3039"))
        painter.setPen(QColor("#FFFFFF"))
        font = QFont("Microsoft YaHei", 11, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(name_rect.adjusted(0, 0, -15, 0),
                        Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                        self.person_name)
        
        # 分割线
        painter.setPen(QPen(QColor("#3A4049"), 2))
        painter.drawLine(120, 0, 120, CELL_HEIGHT)
        
        # 3. 绘制网格线
        painter.translate(120, 0)
        self.draw_grid(painter)
        
        # 4. 绘制任务块
        self.draw_tasks(painter)
    
    def draw_grid(self, painter: QPainter):
        """绘制Excel式分割线"""
        grid_pen = QPen(QColor("#3A4049"), 1)
        painter.setPen(grid_pen)
        
        # 垂直线
        for col in range(self.cols + 1):
            x = col * CELL_WIDTH
            painter.drawLine(x, 0, x, CELL_HEIGHT)
        
        # 水平线
        painter.drawLine(0, 0, self.cols * CELL_WIDTH, 0)
        painter.drawLine(0, CELL_HEIGHT, self.cols * CELL_WIDTH, CELL_HEIGHT)
        
        # 加粗主要网格线(每6列)
        major_pen = QPen(QColor("#4A5059"), 2)
        painter.setPen(major_pen)
        for col in range(0, self.cols + 1, 6):
            x = col * CELL_WIDTH
            painter.drawLine(x, 0, x, CELL_HEIGHT)
    
    def draw_tasks(self, painter: QPainter):
        """绘制任务块"""
        for task in self.tasks:
            rect = task.get_pixel_rect(0)
            task_rect = rect.adjusted(1, 1, -1, -1)
            
            # 填充
            painter.fillRect(task_rect, QColor(task.color))
            
            # 边框
            border_pen = QPen(QColor(task.color).darker(130), 2)
            painter.setPen(border_pen)
            painter.drawRect(task_rect)
            
            # 文字
            painter.setPen(QColor("#FFFFFF"))
            font = QFont("Consolas", 9, QFont.Weight.Bold)
            painter.setFont(font)
            painter.drawText(task_rect, Qt.AlignmentFlag.AlignCenter, task.title)


class TimelineHeader(QWidget):
    """时间轴表头"""
    
    def __init__(self, cols: int = 24, parent=None):
        super().__init__(parent)
        self.cols = cols
        self.setFixedHeight(40)
        self.setFixedWidth(cols * CELL_WIDTH + 120)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#2A3039"))
        
        # 名字列占位
        painter.fillRect(0, 0, 120, 40, QColor("#2A3039"))
        
        # 时间标签
        painter.translate(120, 0)
        painter.setFont(QFont("Consolas", 9))
        painter.setPen(QColor("#AAAAAA"))
        
        for i in range(self.cols):
            x = i * CELL_WIDTH
            painter.drawText(QRect(x, 0, CELL_WIDTH, 40),
                           Qt.AlignmentFlag.AlignCenter, f"{i:02d}:00")


class ScheduleView(QMainWindow):
    """主视图 - 支持双模式"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Schedule Master - Grid + Dual Mode")
        
        # 视图模式
        self.current_mode = ViewMode.FULLSCREEN
        self.is_collapsed = False
        self.collapsed_width = 5
        
        # 定时器
        self.collapse_timer = QTimer()
        self.collapse_timer.setSingleShot(True)
        self.collapse_timer.timeout.connect(self.collapse_sidebar)
        
        # 几何状态
        self.sidebar_geometry = QRect()
        self.fullscreen_geometry = QRect()
        
        # 数据
        self.all_data = []
        
        self.init_ui()
        self.load_demo_data()
        self.show_fullscreen_mode()
    
    def init_ui(self):
        """初始化UI"""
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.main_layout = QVBoxLayout(self.main_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        self.create_title_bar()
        self.create_content_area()
        
        self.setStyleSheet("QMainWindow { background-color: #1F2329; }")
    
    def create_title_bar(self):
        """创建标题栏"""
        title_bar = QWidget()
        title_bar.setFixedHeight(35)
        title_bar.setStyleSheet("background-color: #2A3039;")
        
        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(10, 0, 5, 0)
        
        title = QLabel("📋 Schedule Master - Grid System")
        title.setStyleSheet("color: white; font-weight: bold;")
        layout.addWidget(title)
        layout.addStretch()
        
        # 切换按钮
        self.toggle_btn = QPushButton("⛶")
        self.toggle_btn.setFixedSize(30, 30)
        self.toggle_btn.setToolTip("切换侧边栏模式")
        self.toggle_btn.clicked.connect(self.toggle_view_mode)
        self.toggle_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(74, 144, 226, 0.6);
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 14px;
            }
            QPushButton:hover { background-color: rgba(91, 163, 245, 0.8); }
        """)
        layout.addWidget(self.toggle_btn)
        
        # 关闭按钮
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(30, 30)
        close_btn.clicked.connect(QApplication.quit)
        close_btn.setStyleSheet("""
            QPushButton { background: transparent; color: white; border: none; }
            QPushButton:hover { background: #e81123; }
        """)
        layout.addWidget(close_btn)
        
        self.main_layout.addWidget(title_bar)
    
    def create_content_area(self):
        """创建内容区域"""
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { background: #1F2329; border: none; }")
        
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(2)
        
        self.scroll.setWidget(self.container)
        self.main_layout.addWidget(self.scroll)
    
    def load_demo_data(self):
        """加载演示数据"""
        self.all_data = [
            ("张三", [
                Task("睡觉💤", row_index=0, col_index=0, duration=8, color="#5B859E"),
                Task("工作💼", row_index=0, col_index=9, duration=5, color="#E3A857"),
            ]),
            ("李四", [
                Task("会议📊", row_index=0, col_index=9, duration=2, color="#D98E7A"),
                Task("学习📚", row_index=0, col_index=14, duration=3, color="#9B7FAE"),
            ])
        ]
    
    def rebuild_content(self):
        """重建内容"""
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 列数根据模式调整
        cols = 24 if self.current_mode == ViewMode.FULLSCREEN else 12
        
        # 添加表头
        if self.current_mode == ViewMode.FULLSCREEN:
            header = TimelineHeader(cols)
            self.container_layout.addWidget(header)
        
        # 添加人员行
        for person_name, tasks in self.all_data:
            row = PersonRow(person_name, tasks, cols)
            self.container_layout.addWidget(row)
        
        self.container_layout.addStretch()
    
    def toggle_view_mode(self):
        """切换视图模式"""
        if self.current_mode == ViewMode.FULLSCREEN:
            self.animate_to_sidebar()
        else:
            self.animate_to_fullscreen()
    
    def animate_to_sidebar(self):
        """切换到侧边栏"""
        screen = QApplication.primaryScreen().availableGeometry()
        
        self.fullscreen_geometry = self.geometry()
        target_width = 400
        target_height = screen.height() - 100
        self.sidebar_geometry = QRect(screen.width() - target_width, 50, 
                                     target_width, target_height)
        
        self.animation = QPropertyAnimation(self, b"geometry")
        self.animation.setDuration(400)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.animation.setStartValue(self.geometry())
        self.animation.setEndValue(self.sidebar_geometry)
        self.animation.finished.connect(self.finalize_sidebar_mode)
        self.animation.start()
        
        self.current_mode = ViewMode.SIDEBAR
    
    def finalize_sidebar_mode(self):
        """完成侧边栏切换"""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.show()
        self.rebuild_content()
        self.toggle_btn.setText("▬")
        self.setMouseTracking(True)
    
    def animate_to_fullscreen(self):
        """切换到全屏"""
        if self.is_collapsed:
            self.expand_sidebar()
        
        screen = QApplication.primaryScreen().availableGeometry()
        target_width = 1600
        target_height = 700
        self.fullscreen_geometry = QRect((screen.width() - target_width) // 2,
                                        (screen.height() - target_height) // 2,
                                        target_width, target_height)
        
        self.animation = QPropertyAnimation(self, b"geometry")
        self.animation.setDuration(400)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.animation.setStartValue(self.geometry())
        self.animation.setEndValue(self.fullscreen_geometry)
        self.animation.finished.connect(self.finalize_fullscreen_mode)
        self.animation.start()
        
        self.current_mode = ViewMode.FULLSCREEN
    
    def finalize_fullscreen_mode(self):
        """完成全屏切换"""
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.show()
        self.rebuild_content()
        self.toggle_btn.setText("⛶")
        self.setMouseTracking(False)
    
    def show_fullscreen_mode(self):
        """显示全屏模式(无动画)"""
        screen = QApplication.primaryScreen().availableGeometry()
        target_width = 1600
        target_height = 700
        self.setGeometry((screen.width() - target_width) // 2,
                        (screen.height() - target_height) // 2,
                        target_width, target_height)
        self.current_mode = ViewMode.FULLSCREEN
        self.rebuild_content()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.show()
    
    def enterEvent(self, event):
        """鼠标进入"""
        if self.current_mode == ViewMode.SIDEBAR and self.is_collapsed:
            self.expand_sidebar()
        self.collapse_timer.stop()
    
    def leaveEvent(self, event):
        """鼠标离开"""
        if self.current_mode == ViewMode.SIDEBAR and not self.is_collapsed:
            if not self.rect().contains(self.mapFromGlobal(QCursor.pos())):
                self.collapse_timer.start(200)
    
    def collapse_sidebar(self):
        """折叠侧边栏"""
        if self.current_mode != ViewMode.SIDEBAR or self.is_collapsed:
            return
        
        self.is_collapsed = True
        screen = QApplication.primaryScreen().availableGeometry()
        
        anim = QPropertyAnimation(self, b"geometry")
        anim.setDuration(200)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        target = QRect(screen.width() - self.collapsed_width, self.y(),
                      self.collapsed_width, self.height())
        anim.setEndValue(target)
        
        QTimer.singleShot(50, lambda: self.main_widget.hide())
        anim.start()
        self.collapse_anim = anim
    
    def expand_sidebar(self):
        """展开侧边栏"""
        if not self.is_collapsed:
            return
        
        self.is_collapsed = False
        self.main_widget.show()
        
        anim = QPropertyAnimation(self, b"geometry")
        anim.setDuration(150)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.setEndValue(self.sidebar_geometry)
        anim.start()
        self.expand_anim = anim
    
    def mousePressEvent(self, event):
        """拖动窗口"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.pos()
    
    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, 'drag_pos'):
            self.move(event.globalPosition().toPoint() - self.drag_pos)


if __name__ == "__main__":
    if sys.platform == "linux":
        os.environ["QT_QPA_PLATFORM"] = "xcb"
    
    app = QApplication(sys.argv)
    window = ScheduleView()
    window.show()
    sys.exit(app.exec())
