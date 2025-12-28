#!/usr/bin/env python3
"""
Schedule Master - Oxygen Not Included Style
多轨平铺任务管理工具 - 双模式视图
"""
import sys
import os
from dataclasses import dataclass
from typing import List
from enum import Enum
from datetime import datetime, date
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QHBoxLayout, QLabel, QScrollArea, QPushButton
)
from PyQt6.QtCore import Qt, QRectF, QRect, QTimer, QPropertyAnimation, QEasingCurve, QPoint
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, 
    QLinearGradient, QCursor
)


class ViewMode(Enum):
    """视图模式"""
    SIDEBAR = 1      # 侧边栏模式
    FULLSCREEN = 2   # 全屏模式


@dataclass
class Task:
    """任务数据模型"""
    title: str
    start_hour: float  # 0-24
    end_hour: float    # 0-24
    color: str
    date: date = None  # 任务日期
    track: int = 0     # 自动计算的轨道编号


class MultiTrackLayoutEngine:
    """多轨平铺布局算法"""
    
    @staticmethod
    def is_overlap(task1: Task, task2: Task) -> bool:
        """检测两个任务是否时间重叠"""
        return task1.start_hour < task2.end_hour and task2.start_hour < task1.end_hour
    
    @staticmethod
    def layout_tasks(tasks: List[Task]) -> int:
        """
        分配轨道编号并返回所需最大轨道数
        算法：贪心策略，每个任务分配到最低可用轨道
        """
        if not tasks:
            return 0
        
        sorted_tasks = sorted(tasks, key=lambda t: t.start_hour)
        track_end_times = []
        
        for task in sorted_tasks:
            assigned = False
            for track_idx, end_time in enumerate(track_end_times):
                if task.start_hour >= end_time:
                    task.track = track_idx
                    track_end_times[track_idx] = task.end_hour
                    assigned = True
                    break
            
            if not assigned:
                task.track = len(track_end_times)
                track_end_times.append(task.end_hour)
        
        return len(track_end_times)


class TaskBlock(QWidget):
    """任务块组件 - 带发光效果"""
    
    def __init__(self, task: Task, timeline_width: int, parent=None):
        super().__init__(parent)
        self.task = task
        self.timeline_width = timeline_width
        self.is_hovered = False
        self.setMouseTracking(True)
        self.calculate_geometry()
        
    def calculate_geometry(self):
        """根据任务时间计算几何位置"""
        hour_width = self.timeline_width / 24.0
        x = int(self.task.start_hour * hour_width)
        width = int((self.task.end_hour - self.task.start_hour) * hour_width)
        height = 35 
        self.setGeometry(x, 0, width, height)
    
    def enterEvent(self, event):
        self.is_hovered = True
        self.update()
        
    def leaveEvent(self, event):
        self.is_hovered = False
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        if self.is_hovered:
            for i in range(5):
                alpha = 50 - i * 10
                glow_color = QColor(self.task.color)
                glow_color.setAlpha(alpha)
                pen = QPen(glow_color, 2 + i * 0.5)
                painter.setPen(pen)
                painter.setBrush(Qt.BrushStyle.NoBrush)
                rect = QRectF(i, i, self.width() - 2*i, self.height() - 2*i)
                painter.drawRoundedRect(rect, 6, 6)
        
        main_rect = QRectF(2, 2, self.width() - 4, self.height() - 4)
        gradient = QLinearGradient(0, 0, 0, self.height())
        base_color = QColor(self.task.color)
        gradient.setColorAt(0, base_color.lighter(110))
        gradient.setColorAt(1, base_color)
        
        painter.setBrush(QBrush(gradient))
        painter.setPen(QPen(QColor(self.task.color).darker(120), 2))
        painter.drawRoundedRect(main_rect, 6, 6)
        
        painter.setPen(QColor("#FFFFFF"))
        font = QFont("Consolas", 10, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(main_rect, Qt.AlignmentFlag.AlignCenter, self.task.title)


class TimelineCanvas(QWidget):
    """时间轴画布子类，用于绘制网格"""
    def __init__(self, timeline_width: int, max_tracks: int, track_height: int, track_spacing: int, parent=None):
        super().__init__(parent)
        self.timeline_width = timeline_width
        self.max_tracks = max_tracks
        self.track_height = track_height
        self.track_spacing = track_spacing
        self.setFixedWidth(timeline_width)
        total_height = max(max_tracks * track_height + (max_tracks - 1) * track_spacing, 45)
        self.setFixedHeight(total_height)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#1F2329"))
        
        hour_width = self.timeline_width / 24
        for i in range(25):
            x = int(i * hour_width)
            pen = QPen(QColor("#3A4049" if i % 6 == 0 else "#2A3039"), 1)
            painter.setPen(pen)
            painter.drawLine(x, 0, x, self.height())
        
        for i in range(self.max_tracks + 1):
            y = i * (self.track_height + self.track_spacing)
            painter.setPen(QPen(QColor("#2A3039"), 1, Qt.PenStyle.DashLine))
            painter.drawLine(0, y, self.timeline_width, y)


class PersonRow(QWidget):
    """人员行组件"""
    def __init__(self, person_name: str, tasks: List[Task], timeline_width: int = 960, parent=None):
        super().__init__(parent)
        self.person_name = person_name
        self.tasks = tasks
        self.timeline_width = timeline_width
        self.track_height = 40
        self.track_spacing = 5
        
        self.max_tracks = MultiTrackLayoutEngine.layout_tasks(tasks)
        self.init_ui()
    
    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        name_label = QLabel(self.person_name)
        name_label.setFixedWidth(120)
        name_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        name_label.setStyleSheet("""
            QLabel {
                background-color: #2A3039;
                color: #FFFFFF;
                font-weight: bold;
                font-size: 14px;
                padding-right: 15px;
                border-right: 2px solid #3A4049;
            }
        """)
        layout.addWidget(name_label)
        
        self.timeline_canvas = TimelineCanvas(
            self.timeline_width, self.max_tracks, 
            self.track_height, self.track_spacing, self
        )
        layout.addWidget(self.timeline_canvas)
        layout.addStretch()
        
        for task in self.tasks:
            block = TaskBlock(task, self.timeline_width, self.timeline_canvas)
            y_pos = task.track * (self.track_height + self.track_spacing) + 5
            block.move(block.x(), y_pos)


class TimelineHeader(QWidget):
    """时间轴表头子类"""
    def __init__(self, timeline_width: int, parent=None):
        super().__init__(parent)
        self.timeline_width = timeline_width
        self.setFixedWidth(timeline_width)
        self.setFixedHeight(40)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        hour_width = self.timeline_width / 24
        painter.setFont(QFont("Consolas", 9))
        painter.setPen(QColor("#AAAAAA"))
        
        for i in range(24):
            x = int(i * hour_width)
            painter.drawText(QRectF(x, 0, hour_width, 40), Qt.AlignmentFlag.AlignCenter, f"{i:02d}:00")
            if i > 0:
                painter.setPen(QColor("#3A4049"))
                painter.drawLine(x, 30, x, 40)
                painter.setPen(QColor("#AAAAAA"))


class ScheduleView(QMainWindow):
    """主视图 - 支持双模式"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Schedule Master - ONI Style")
        
        # 视图模式
        self.current_mode = ViewMode.FULLSCREEN
        self.is_collapsed = False  # 侧边栏折叠状态
        self.collapsed_width = 5
        
        # 定时器
        self.collapse_timer = QTimer()
        self.collapse_timer.setSingleShot(True)
        self.collapse_timer.timeout.connect(self.collapse_sidebar)
        
        # 几何状态
        self.sidebar_geometry = QRect()
        self.fullscreen_geometry = QRect()
        
        # 数据
        self.all_tasks = []
        
        self.init_ui()
        self.load_demo_data()
        self.show_fullscreen_mode()  # 默认全屏模式
    
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
        self.title_bar = QWidget()
        self.title_bar.setFixedHeight(35)
        self.title_bar.setStyleSheet("background-color: #2A3039;")
        
        layout = QHBoxLayout(self.title_bar)
        layout.setContentsMargins(10, 0, 5, 0)
        layout.setSpacing(10)
        
        title_label = QLabel("📋 Schedule Master")
        title_label.setStyleSheet("color: #FFFFFF; font-weight: bold; font-size: 13px;")
        layout.addWidget(title_label)
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
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: rgba(91, 163, 245, 0.8);
            }
        """)
        layout.addWidget(self.toggle_btn)
        
        # 关闭按钮
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(30, 30)
        close_btn.clicked.connect(QApplication.quit)
        close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                color: white;
                border: none;
                font-size: 14px;
            }
            QPushButton:hover { background: #e81123; }
        """)
        layout.addWidget(close_btn)
        
        self.main_layout.addWidget(self.title_bar)
    
    def create_content_area(self):
        """创建内容区域"""
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("QScrollArea { background-color: #1F2329; border: none; }")
        
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(2)
        
        self.scroll_area.setWidget(self.container)
        self.main_layout.addWidget(self.scroll_area)
    
    def load_demo_data(self):
        """加载演示数据"""
        today = date.today()
        
        self.all_tasks = [
            ("张三", [
                Task("睡觉 💤", 0, 8, "#5B859E", today),
                Task("工作 💼", 6, 14, "#E3A857", today),
                Task("运动 🏃", 12, 16, "#7FAE8A", today),
            ]),
            ("李四", [
                Task("会议 📊", 9, 11, "#D98E7A", today),
                Task("学习 📚", 10, 12, "#9B7FAE", today),
                Task("休息 ☕", 14, 15, "#6B9BAE", today),
            ])
        ]
    
    def rebuild_content(self, tasks_data):
        """重建内容"""
        # 清空现有内容
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 添加header
        if self.current_mode == ViewMode.FULLSCREEN:
            header = self.create_fullscreen_header()
            self.container_layout.addWidget(header)
        
        # 添加人员行
        timeline_width = 960 if self.current_mode == ViewMode.FULLSCREEN else 280
        for person_name, tasks in tasks_data:
            row = PersonRow(person_name, tasks, timeline_width)
            self.container_layout.addWidget(row)
        
        self.container_layout.addStretch()
    
    def create_fullscreen_header(self):
        """创建全屏模式表头"""
        header = QWidget()
        header.setFixedHeight(40)
        header.setStyleSheet("background-color: #2A3039;")
        layout = QHBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        spacer = QWidget()
        spacer.setFixedWidth(120)
        spacer.setStyleSheet("border-right: 2px solid #3A4049;")
        layout.addWidget(spacer)
        
        timeline_header = TimelineHeader(960)
        layout.addWidget(timeline_header)
        layout.addStretch()
        
        return header
    
    def toggle_view_mode(self):
        """切换视图模式"""
        if self.current_mode == ViewMode.FULLSCREEN:
            self.animate_to_sidebar()
        else:
            self.animate_to_fullscreen()
    
    def animate_to_sidebar(self):
        """动画切换到侧边栏模式"""
        screen = QApplication.primaryScreen().availableGeometry()
        
        # 保存当前几何
        self.fullscreen_geometry = self.geometry()
        
        # 目标几何（右侧边缘）
        target_width = 350
        target_height = screen.height() - 100
        target_x = screen.width() - target_width
        target_y = 50
        
        self.sidebar_geometry = QRect(target_x, target_y, target_width, target_height)
        
        # 动画
        self.animation = QPropertyAnimation(self, b"geometry")
        self.animation.setDuration(400)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.animation.setStartValue(self.geometry())
        self.animation.setEndValue(self.sidebar_geometry)
        self.animation.finished.connect(lambda: self.finalize_sidebar_mode())
        self.animation.start()
        
        self.current_mode = ViewMode.SIDEBAR
    
    def finalize_sidebar_mode(self):
        """完成侧边栏模式切换"""
        # 更新窗口标志
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.show()
        
        # 重建内容（只显示今日任务）
        today_tasks = [(name, tasks) for name, tasks in self.all_tasks]
        self.rebuild_content(today_tasks)
        
        # 更新按钮
        self.toggle_btn.setText("▬")
        self.toggle_btn.setToolTip("切换全屏模式")
        
        # 启用鼠标追踪
        self.setMouseTracking(True)
    
    def animate_to_fullscreen(self):
        """动画切换到全屏模式"""
        if self.is_collapsed:
            self.expand_sidebar()
        
        screen = QApplication.primaryScreen().availableGeometry()
        
        # 目标几何（居中）
        target_width = 1200
        target_height = 700
        target_x = (screen.width() - target_width) // 2
        target_y = (screen.height() - target_height) // 2
        
        self.fullscreen_geometry = QRect(target_x, target_y, target_width, target_height)
        
        # 动画
        self.animation = QPropertyAnimation(self, b"geometry")
        self.animation.setDuration(400)
        self.animation.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.animation.setStartValue(self.geometry())
        self.animation.setEndValue(self.fullscreen_geometry)
        self.animation.finished.connect(lambda: self.finalize_fullscreen_mode())
        self.animation.start()
        
        self.current_mode = ViewMode.FULLSCREEN
    
    def finalize_fullscreen_mode(self):
        """完成全屏模式切换"""
        # 更新窗口标志（移除置顶）
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.show()
        
        # 重建内容
        self.rebuild_content(self.all_tasks)
        
        # 更新按钮
        self.toggle_btn.setText("⛶")
        self.toggle_btn.setToolTip("切换侧边栏模式")
        
        self.setMouseTracking(False)
    
    def show_sidebar_mode(self):
        """显示侧边栏模式（无动画）"""
        screen = QApplication.primaryScreen().availableGeometry()
        target_width = 350
        target_height = screen.height() - 100
        self.setGeometry(screen.width() - target_width, 50, target_width, target_height)
        self.current_mode = ViewMode.SIDEBAR
        self.finalize_sidebar_mode()
    
    def show_fullscreen_mode(self):
        """显示全屏模式（无动画）"""
        screen = QApplication.primaryScreen().availableGeometry()
        target_width = 1200
        target_height = 700
        self.setGeometry((screen.width() - target_width) // 2, 
                        (screen.height() - target_height) // 2,
                        target_width, target_height)
        self.current_mode = ViewMode.FULLSCREEN
        self.finalize_fullscreen_mode()
    
    # 侧边栏折叠功能
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
        """鼠标按下 - 拖动窗口"""
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.pos()
    
    def mouseMoveEvent(self, event):
        """鼠标移动 - 拖动窗口"""
        if event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, 'drag_pos'):
            self.move(event.globalPosition().toPoint() - self.drag_pos)


if __name__ == "__main__":
    if sys.platform == "linux":
        os.environ["QT_QPA_PLATFORM"] = "xcb"
    
    app = QApplication(sys.argv)
    window = ScheduleView()
    window.show()
    sys.exit(app.exec())
