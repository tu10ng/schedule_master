#!/usr/bin/env python3
"""
Schedule Master - Step 2: View Logic Separation
侧边栏(垂直列表) vs 全屏(日期网格)
"""
import sys
import os
from dataclasses import dataclass
from typing import List
from enum import Enum
from datetime import date, timedelta
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QHBoxLayout, QLabel, QPushButton, QScrollArea
)
from PyQt6.QtCore import Qt, QRect, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QCursor


# 网格常量
CELL_WIDTH_HOUR = 40    # 小时模式单元格宽度
CELL_WIDTH_DAY = 120    # 日期模式单元格宽度
CELL_HEIGHT = 80        # 单元格高度
SIDEBAR_TASK_HEIGHT = 60  # 侧边栏任务高度


class ViewMode(Enum):
    """视图模式"""
    SIDEBAR = 1      # 侧边栏模式(垂直列表)
    FULLSCREEN = 2   # 全屏模式(日期网格)


@dataclass
class Task:
    """任务数据模型"""
    title: str
    person: str         # 人员名称
    date: date          # 任务日期
    start_hour: int = 9  # 开始小时
    duration: int = 2    # 持续小时数
    color: str = "#5B859E"


class SidebarTaskCard(QWidget):
    """侧边栏任务卡片 - 垂直排列"""
    
    def __init__(self, task: Task, parent=None):
        super().__init__(parent)
        self.task = task
        self.setFixedHeight(SIDEBAR_TASK_HEIGHT)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 卡片背景
        card_rect = self.rect().adjusted(5, 5, -5, -5)
        painter.fillRect(card_rect, QColor(self.task.color))
        
        # 边框
        painter.setPen(QPen(QColor(self.task.color).darker(130), 2))
        painter.drawRoundedRect(card_rect, 4, 4)
        
        # 任务标题
        painter.setPen(QColor("#FFFFFF"))
        title_font = QFont("Microsoft YaHei", 11, QFont.Weight.Bold)
        painter.setFont(title_font)
        title_rect = card_rect.adjusted(10, 5, -10, -25)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                        self.task.title)
        
        # 时间信息
        time_font = QFont("Consolas", 9)
        painter.setFont(time_font)
        painter.setPen(QColor("#AAAAAA"))
        time_text = f"{self.task.start_hour:02d}:00 - {self.task.start_hour + self.task.duration:02d}:00"
        time_rect = card_rect.adjusted(10, 30, -10, -5)
        painter.drawText(time_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                        time_text)


class SidebarPersonGroup(QWidget):
    """侧边栏人员组 - 垂直任务列表"""
    
    def __init__(self, person_name: str, tasks: List[Task], parent=None):
        super().__init__(parent)
        self.person_name = person_name
        self.tasks = tasks
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(5)
        
        # 人员标题
        name_label = QLabel(f"👤 {person_name}")
        name_label.setStyleSheet("""
            QLabel {
                color: #FFFFFF;
                font-size: 14px;
                font-weight: bold;
                padding: 5px;
                background-color: #2A3039;
                border-radius: 4px;
            }
        """)
        layout.addWidget(name_label)
        
        # 任务卡片列表
        if tasks:
            for task in tasks:
                card = SidebarTaskCard(task)
                layout.addWidget(card)
        else:
            # 无任务提示
            empty_label = QLabel("暂无任务")
            empty_label.setStyleSheet("color: #666; padding: 10px;")
            layout.addWidget(empty_label)


class FullscreenPersonRow(QWidget):
    """全屏人员行 - 日期网格"""
    
    def __init__(self, person_name: str, tasks: List[Task], 
                 start_date: date, days: int = 7, parent=None):
        super().__init__(parent)
        self.person_name = person_name
        self.tasks = tasks
        self.start_date = start_date
        self.days = days
        
        # 构建日期到任务的映射
        self.date_tasks = {}
        for task in tasks:
            if task.date not in self.date_tasks:
                self.date_tasks[task.date] = []
            self.date_tasks[task.date].append(task)
        
        canvas_width = days * CELL_WIDTH_DAY + 120
        self.setFixedSize(canvas_width, CELL_HEIGHT)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 背景
        painter.fillRect(self.rect(), QColor("#1F2329"))
        
        # 绘制名字列
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
        
        # 绘制日期网格
        painter.translate(120, 0)
        self.draw_grid(painter)
        self.draw_tasks_in_grid(painter)
    
    def draw_grid(self, painter: QPainter):
        """绘制日期网格线"""
        grid_pen = QPen(QColor("#3A4049"), 1)
        painter.setPen(grid_pen)
        
        # 垂直线(每天)
        for day in range(self.days + 1):
            x = day * CELL_WIDTH_DAY
            painter.drawLine(x, 0, x, CELL_HEIGHT)
        
        # 水平线
        painter.drawLine(0, 0, self.days * CELL_WIDTH_DAY, 0)
        painter.drawLine(0, CELL_HEIGHT, self.days * CELL_WIDTH_DAY, CELL_HEIGHT)
        
        # 周末高亮
        for day in range(self.days):
            current_date = self.start_date + timedelta(days=day)
            if current_date.weekday() >= 5:  # 周六/周日
                x = day * CELL_WIDTH_DAY
                weekend_rect = QRect(x + 1, 1, CELL_WIDTH_DAY - 2, CELL_HEIGHT - 2)
                painter.fillRect(weekend_rect, QColor(255, 255, 255, 10))
    
    def draw_tasks_in_grid(self, painter: QPainter):
        """在网格中绘制任务"""
        for day in range(self.days):
            current_date = self.start_date + timedelta(days=day)
            
            if current_date in self.date_tasks:
                tasks = self.date_tasks[current_date]
                x = day * CELL_WIDTH_DAY
                
                # 在该日期单元格内垂直堆叠任务
                task_height = min(CELL_HEIGHT // len(tasks) - 4, 25)
                
                for idx, task in enumerate(tasks):
                    y = idx * (task_height + 2) + 5
                    task_rect = QRect(x + 3, y, CELL_WIDTH_DAY - 6, task_height)
                    
                    # 填充
                    painter.fillRect(task_rect, QColor(task.color))
                    
                    # 边框
                    painter.setPen(QPen(QColor(task.color).darker(130), 1))
                    painter.drawRect(task_rect)
                    
                    # 文字
                    painter.setPen(QColor("#FFFFFF"))
                    font = QFont("Consolas", 8, QFont.Weight.Bold)
                    painter.setFont(font)
                    # 简化标题显示
                    title = task.title[:8] + "..." if len(task.title) > 8 else task.title
                    painter.drawText(task_rect, Qt.AlignmentFlag.AlignCenter, title)


class DateHeader(QWidget):
    """日期表头"""
    
    def __init__(self, start_date: date, days: int = 7, parent=None):
        super().__init__(parent)
        self.start_date = start_date
        self.days = days
        self.setFixedHeight(50)
        self.setFixedWidth(days * CELL_WIDTH_DAY + 120)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#2A3039"))
        
        # 名字列占位
        painter.fillRect(0, 0, 120, 50, QColor("#2A3039"))
        
        # 日期标签
        painter.translate(120, 0)
        
        for day in range(self.days):
            current_date = self.start_date + timedelta(days=day)
            x = day * CELL_WIDTH_DAY
            
            # 周末背景
            if current_date.weekday() >= 5:
                painter.fillRect(x, 0, CELL_WIDTH_DAY, 50, QColor(255, 100, 100, 30))
            
            # 日期文字
            painter.setPen(QColor("#FFFFFF"))
            font = QFont("Microsoft YaHei", 10, QFont.Weight.Bold)
            painter.setFont(font)
            
            date_text = f"{current_date.month}/{current_date.day}"
            weekday_text = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][current_date.weekday()]
            
            painter.drawText(QRect(x, 5, CELL_WIDTH_DAY, 20),
                           Qt.AlignmentFlag.AlignCenter, date_text)
            
            painter.setFont(QFont("Microsoft YaHei", 8))
            painter.setPen(QColor("#AAAAAA"))
            painter.drawText(QRect(x, 28, CELL_WIDTH_DAY, 20),
                           Qt.AlignmentFlag.AlignCenter, weekday_text)


class ScheduleView(QMainWindow):
    """主视图"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Schedule Master - View Separation")
        
        self.current_mode = ViewMode.FULLSCREEN
        self.is_collapsed = False
        self.collapsed_width = 5
        
        self.collapse_timer = QTimer()
        self.collapse_timer.setSingleShot(True)
        self.collapse_timer.timeout.connect(self.collapse_sidebar)
        
        self.sidebar_geometry = QRect()
        self.fullscreen_geometry = QRect()
        
        self.all_tasks = []
        
        self.init_ui()
        self.load_demo_data()
        self.show_fullscreen_mode()
    
    def init_ui(self):
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.main_layout = QVBoxLayout(self.main_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        self.create_title_bar()
        self.create_content_area()
        
        self.setStyleSheet("QMainWindow { background-color: #1F2329; }")
    
    def create_title_bar(self):
        title_bar = QWidget()
        title_bar.setFixedHeight(35)
        title_bar.setStyleSheet("background-color: #2A3039;")
        
        layout = QHBoxLayout(title_bar)
        layout.setContentsMargins(10, 0, 5, 0)
        
        title = QLabel("📋 Schedule Master - View Separation")
        title.setStyleSheet("color: white; font-weight: bold;")
        layout.addWidget(title)
        layout.addStretch()
        
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
        today = date.today()
        
        self.all_tasks = [
            Task("晨会", "张三", today, 9, 1, "#5B859E"),
            Task("项目开发", "张三", today, 10, 4, "#E3A857"),
            Task("团队讨论", "张三", today + timedelta(days=1), 14, 2, "#7FAE8A"),
            
            Task("代码审查", "李四", today, 9, 2, "#D98E7A"),
            Task("文档编写", "李四", today, 14, 3, "#9B7FAE"),
            Task("客户会议", "李四", today + timedelta(days=2), 10, 2, "#6B9BAE"),
        ]
    
    def rebuild_content(self):
        """重建内容"""
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        if self.current_mode == ViewMode.SIDEBAR:
            self.build_sidebar_view()
        else:
            self.build_fullscreen_view()
    
    def build_sidebar_view(self):
        """构建侧边栏视图 - 垂直任务列表"""
        # 按人员分组今日任务
        today = date.today()
        person_tasks = {}
        
        for task in self.all_tasks:
            if task.date == today:
                if task.person not in person_tasks:
                    person_tasks[task.person] = []
                person_tasks[task.person].append(task)
        
        # 创建每个人的任务组
        for person in ["张三", "李四"]:  # 固定顺序
            tasks = person_tasks.get(person, [])
            group = SidebarPersonGroup(person, tasks)
            self.container_layout.addWidget(group)
        
        self.container_layout.addStretch()
    
    def build_fullscreen_view(self):
        """构建全屏视图 - 日期网格"""
        today = date.today()
        start_date = today
        days = 7
        
        # 添加日期表头
        header = DateHeader(start_date, days)
        self.container_layout.addWidget(header)
        
        # 按人员分组任务
        person_tasks = {}
        for task in self.all_tasks:
            if task.person not in person_tasks:
                person_tasks[task.person] = []
            person_tasks[task.person].append(task)
        
        # 创建每个人的行
        for person in ["张三", "李四"]:
            tasks = person_tasks.get(person, [])
            row = FullscreenPersonRow(person, tasks, start_date, days)
            self.container_layout.addWidget(row)
        
        self.container_layout.addStretch()
    
    def toggle_view_mode(self):
        if self.current_mode == ViewMode.FULLSCREEN:
            self.animate_to_sidebar()
        else:
            self.animate_to_fullscreen()
    
    def animate_to_sidebar(self):
        screen = QApplication.primaryScreen().availableGeometry()
        self.fullscreen_geometry = self.geometry()
        
        target_width = 380
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
        if self.is_collapsed:
            self.expand_sidebar()
        
        screen = QApplication.primaryScreen().availableGeometry()
        target_width = 1080
        target_height = 600
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
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.show()
        self.rebuild_content()
        self.toggle_btn.setText("⛶")
        self.setMouseTracking(False)
    
    def show_fullscreen_mode(self):
        screen = QApplication.primaryScreen().availableGeometry()
        target_width = 1080
        target_height = 600
        self.setGeometry((screen.width() - target_width) // 2,
                        (screen.height() - target_height) // 2,
                        target_width, target_height)
        self.current_mode = ViewMode.FULLSCREEN
        self.rebuild_content()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint)
        self.show()
    
    def enterEvent(self, event):
        if self.current_mode == ViewMode.SIDEBAR and self.is_collapsed:
            self.expand_sidebar()
        self.collapse_timer.stop()
    
    def leaveEvent(self, event):
        if self.current_mode == ViewMode.SIDEBAR and not self.is_collapsed:
            if not self.rect().contains(self.mapFromGlobal(QCursor.pos())):
                self.collapse_timer.start(200)
    
    def collapse_sidebar(self):
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
