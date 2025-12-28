#!/usr/bin/env python3
"""
Schedule Master - Oxygen Not Included Style
多轨平铺任务管理工具
"""
import sys
import os
from dataclasses import dataclass
from typing import List
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QHBoxLayout, QLabel, QScrollArea
)
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import (
    QPainter, QColor, QPen, QBrush, QFont, 
    QLinearGradient
)


@dataclass
class Task:
    """任务数据模型"""
    title: str
    start_hour: float  # 0-24
    end_hour: float    # 0-24
    color: str
    track: int = 0  # 自动计算的轨道编号


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
        
        # 按开始时间排序
        sorted_tasks = sorted(tasks, key=lambda t: t.start_hour)
        
        # 跟踪每个轨道的最后结束时间
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
    def __init__(self, person_name: str, tasks: List[Task], parent=None):
        super().__init__(parent)
        self.person_name = person_name
        self.tasks = tasks
        self.timeline_width = 960
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
    """主视图"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Schedule Master - ONI Style")
        self.resize(1200, 600)
        self.init_ui()
        self.load_demo_data()
    
    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Header
        header = QWidget()
        header.setFixedHeight(40)
        header.setStyleSheet("background-color: #2A3039;")
        h_layout = QHBoxLayout(header)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(0)
        
        spacer = QWidget()
        spacer.setFixedWidth(120)
        spacer.setStyleSheet("border-right: 2px solid #3A4049;")
        h_layout.addWidget(spacer)
        
        self.timeline_header = TimelineHeader(960)
        h_layout.addWidget(self.timeline_header)
        h_layout.addStretch()
        
        main_layout.addWidget(header)
        
        # Scroll Area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { background-color: #1F2329; border: none; }")
        
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(2)
        
        scroll.setWidget(self.container)
        main_layout.addWidget(scroll)
        
        self.setStyleSheet("QMainWindow { background-color: #1F2329; }")
    
    def load_demo_data(self):
        tasks1 = [
            Task("睡觉 💤", 0, 8, "#5B859E"),
            Task("工作 💼", 6, 14, "#E3A857"),
            Task("运动 🏃", 12, 16, "#7FAE8A"),
        ]
        self.container_layout.addWidget(PersonRow("张三", tasks1))
        
        tasks2 = [
            Task("会议 📊", 9, 11, "#D98E7A"),
            Task("学习 📚", 10, 12, "#9B7FAE"),
            Task("休息 ☕", 14, 15, "#6B9BAE"),
        ]
        self.container_layout.addWidget(PersonRow("李四", tasks2))
        self.container_layout.addStretch()


if __name__ == "__main__":
    if sys.platform == "linux":
        # Ensure xcb is used for stable rendering on Linux
        os.environ["QT_QPA_PLATFORM"] = "xcb"
    
    app = QApplication(sys.argv)
    window = ScheduleView()
    window.show()
    sys.exit(app.exec())
