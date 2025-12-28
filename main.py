#!/usr/bin/env python3
"""
Schedule Master - Step 2 (Refined): Unified Grid Style
侧边栏(单列网格) vs 全屏(多列网格)
"""
import sys
import os
from dataclasses import dataclass
from typing import List, Dict
from enum import Enum
from datetime import date, timedelta
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QHBoxLayout, QLabel, QPushButton, QScrollArea
)
from PyQt6.QtCore import Qt, QRect, QTimer, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QCursor


# 网格常量
CELL_WIDTH_FULL = 140   # 全屏模式日期单元格宽度
CELL_WIDTH_SIDE = 240   # 侧边栏模式单元格宽度
CELL_HEIGHT = 90        # 单元格高度 (增加高度以容纳堆叠任务)
NAME_COL_WIDTH = 100    # 名字列宽度


class ViewMode(Enum):
    """视图模式"""
    SIDEBAR = 1      # 侧边栏模式(单列网格)
    FULLSCREEN = 2   # 全屏模式(日期网格)


@dataclass
class Task:
    """任务数据模型"""
    title: str
    person: str
    date: date
    start_hour: int = 9
    duration: int = 2
    color: str = "#5B859E"


class GridPersonRow(QWidget):
    """统一网格人员行 - 支持单列或多列"""
    
    def __init__(self, person_name: str, tasks: List[Task], 
                 start_date: date, days: int, cell_width: int, parent=None):
        super().__init__(parent)
        self.person_name = person_name
        self.tasks = tasks
        self.start_date = start_date
        self.days = days
        self.cell_width = cell_width
        
        # 按日期对任务分组
        self.date_map: Dict[date, List[Task]] = {}
        for t in tasks:
            if t.date not in self.date_map:
                self.date_map[t.date] = []
            self.date_map[t.date].append(t)
            
        self.setFixedSize(NAME_COL_WIDTH + days * cell_width, CELL_HEIGHT)
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 背景
        painter.fillRect(self.rect(), QColor("#1F2329"))
        
        # 1. 绘制名字单元格
        name_rect = QRect(0, 0, NAME_COL_WIDTH, CELL_HEIGHT)
        painter.fillRect(name_rect, QColor("#2A3039"))
        
        # 名字边框
        painter.setPen(QPen(QColor("#3A4049"), 2))
        painter.drawRect(name_rect)
        
        painter.setPen(QColor("#FFFFFF"))
        painter.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        painter.drawText(name_rect.adjusted(5, 0, -5, 0), 
                        Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter, 
                        self.person_name)
        
        # 2. 绘制网格单元格
        painter.translate(NAME_COL_WIDTH, 0)
        
        grid_pen = QPen(QColor("#3A4049"), 1)
        
        for i in range(self.days):
            current_date = self.start_date + timedelta(days=i)
            cell_x = i * self.cell_width
            cell_rect = QRect(cell_x, 0, self.cell_width, CELL_HEIGHT)
            
            # 单元格边框 (Excel式)
            painter.setPen(grid_pen)
            painter.drawRect(cell_rect)
            
            # 绘制该单元格内的任务
            if current_date in self.date_map:
                day_tasks = self.date_map[current_date]
                self.draw_tasks_in_cell(painter, cell_rect, day_tasks)

    def draw_tasks_in_cell(self, painter: QPainter, rect: QRect, tasks: List[Task]):
        """在单元格内垂直排列任务"""
        count = len(tasks)
        if count == 0: return
        
        # 计算每个任务块的高度，考虑间距
        spacing = 4
        available_h = rect.height() - (spacing * 2)
        block_h = min(24, (available_h - (count - 1) * 2) // count)
        
        for idx, task in enumerate(tasks):
            y = spacing + idx * (block_h + 2)
            task_rect = QRect(rect.x() + 4, y, rect.width() - 8, block_h)
            
            # 填充矩形 (ONI风格)
            painter.fillRect(task_rect, QColor(task.color))
            
            # 极细边框
            painter.setPen(QPen(QColor(task.color).darker(140), 1))
            painter.drawRect(task_rect)
            
            # 文字 (Consolas 等宽字)
            painter.setPen(QColor("#FFFFFF"))
            painter.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
            
            # 如果宽度够，显示时间
            display_text = task.title
            if rect.width() > 180:
                display_text += f" ({task.start_hour:02d}:00)"
                
            metrics = painter.fontMetrics()
            elided_text = metrics.elidedText(display_text, Qt.TextElideMode.ElideRight, task_rect.width() - 4)
            painter.drawText(task_rect.adjusted(4, 0, -4, 0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_text)


class ModeHeader(QWidget):
    """网格表头"""
    def __init__(self, start_date: date, days: int, cell_width: int, mode: ViewMode, parent=None):
        super().__init__(parent)
        self.start_date = start_date
        self.days = days
        self.cell_width = cell_width
        self.mode = mode
        self.setFixedHeight(40)
        self.setFixedWidth(NAME_COL_WIDTH + days * cell_width)
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#2A3039"))
        
        # 名字列占位
        painter.setPen(QPen(QColor("#3A4049"), 2))
        painter.drawRect(0, 0, NAME_COL_WIDTH, 40)
        
        painter.translate(NAME_COL_WIDTH, 0)
        
        for i in range(self.days):
            current_date = self.start_date + timedelta(days=i)
            x = i * self.cell_width
            header_rect = QRect(x, 0, self.cell_width, 40)
            
            painter.setPen(QPen(QColor("#3A4049"), 1))
            painter.drawRect(header_rect)
            
            painter.setPen(QColor("#AAAAAA"))
            painter.setFont(QFont("Microsoft YaHei", 9, QFont.Weight.Bold))
            
            if self.mode == ViewMode.SIDEBAR:
                title = "今日任务 (TODAY)"
            else:
                title = current_date.strftime("%m/%d ") + ["周一","周二","周三","周四","周五","周六","周日"][current_date.weekday()]
                
            painter.drawText(header_rect, Qt.AlignmentFlag.AlignCenter, title)


class ScheduleView(QMainWindow):
    """主视图"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Schedule Master - Unified Grid")
        
        self.current_mode = ViewMode.FULLSCREEN
        self.is_collapsed = False
        self.collapsed_width = 8
        
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
        self.setStyleSheet("QMainWindow { background-color: #1F2329; border: 1px solid #3A4049; }")

    def create_title_bar(self):
        self.title_bar = QWidget()
        self.title_bar.setFixedHeight(35)
        self.title_bar.setStyleSheet("background-color: #2A3039;")
        layout = QHBoxLayout(self.title_bar)
        layout.setContentsMargins(10, 0, 5, 0)
        
        self.title_label = QLabel("📋 ONI Schedule")
        self.title_label.setStyleSheet("color: #FFFFFF; font-weight: bold; font-family: 'Consolas';")
        layout.addWidget(self.title_label)
        layout.addStretch()
        
        self.toggle_btn = QPushButton("⛶")
        self.toggle_btn.setFixedSize(30, 30)
        self.toggle_btn.clicked.connect(self.toggle_view_mode)
        self.toggle_btn.setStyleSheet("""
            QPushButton { background: #3A4049; color: white; border: none; border-radius: 4px; }
            QPushButton:hover { background: #4A5059; }
        """)
        layout.addWidget(self.toggle_btn)
        
        close_btn = QPushButton("✕")
        close_btn.setFixedSize(30, 30)
        close_btn.clicked.connect(QApplication.quit)
        close_btn.setStyleSheet("QPushButton { background: transparent; color: white; border: none; } QPushButton:hover { background: #e81123; }")
        layout.addWidget(close_btn)
        self.main_layout.addWidget(self.title_bar)

    def create_content_area(self):
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setStyleSheet("QScrollArea { background: #1F2329; border: none; }")
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 0, 0)
        self.container_layout.setSpacing(1)
        self.scroll.setWidget(self.container)
        self.main_layout.addWidget(self.scroll)

    def load_demo_data(self):
        t = date.today()
        self.all_tasks = [
            Task("周期巡检", "张三", t, 9, 1, "#5B859E"),
            Task("供氧维护", "张三", t, 10, 2, "#E3A857"),
            Task("实验室分析", "张三", t + timedelta(days=1), 14, 2, "#7FAE8A"),
            Task("哈奇喂养", "李四", t, 8, 1, "#D98E7A"),
            Task("电力采集", "李四", t, 11, 4, "#9B7FAE"),
            Task("火箭准备", "李四", t + timedelta(days=2), 10, 5, "#6B9BAE"),
        ]

    def rebuild_content(self):
        while self.container_layout.count():
            w = self.container_layout.takeAt(0).widget()
            if w: w.deleteLater()
            
        today = date.today()
        if self.current_mode == ViewMode.SIDEBAR:
            days, width = 1, CELL_WIDTH_SIDE
            start_date = today
        else:
            days, width = 7, CELL_WIDTH_FULL
            start_date = today
            
        # Header
        self.container_layout.addWidget(ModeHeader(start_date, days, width, self.current_mode))
        
        # Rows
        persons = sorted(list(set(t.person for t in self.all_tasks)))
        for p in persons:
            p_tasks = [t for t in self.all_tasks if t.person == p]
            self.container_layout.addWidget(GridPersonRow(p, p_tasks, start_date, days, width))
            
        self.container_layout.addStretch()

    def toggle_view_mode(self):
        if self.current_mode == ViewMode.FULLSCREEN:
            self.animate_transition(ViewMode.SIDEBAR)
        else:
            self.animate_transition(ViewMode.FULLSCREEN)

    def animate_transition(self, target_mode: ViewMode):
        screen = QApplication.primaryScreen().availableGeometry()
        self.fullscreen_geometry = self.geometry() if self.current_mode == ViewMode.FULLSCREEN else self.fullscreen_geometry
        
        if target_mode == ViewMode.SIDEBAR:
            w, h = 360, screen.height() - 100
            target_geo = QRect(screen.width() - w, 50, w, h)
            self.sidebar_geometry = target_geo
        else:
            if self.is_collapsed: self.expand_sidebar()
            w, h = 1100, 600
            target_geo = QRect((screen.width() - w)//2, (screen.height() - h)//2, w, h)
            
        self.anim = QPropertyAnimation(self, b"geometry")
        self.anim.setDuration(400)
        self.anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.anim.setEndValue(target_geo)
        self.anim.finished.connect(lambda m=target_mode: self.finalize_mode(m))
        self.anim.start()
        self.current_mode = target_mode

    def finalize_mode(self, mode: ViewMode):
        flags = Qt.WindowType.FramelessWindowHint
        if mode == ViewMode.SIDEBAR:
            flags |= Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool
            self.toggle_btn.setText("▬")
            self.setMouseTracking(True)
        else:
            self.toggle_btn.setText("⛶")
            self.setMouseTracking(False)
            
        self.setWindowFlags(flags)
        self.show()
        self.rebuild_content()

    def show_fullscreen_mode(self):
        screen = QApplication.primaryScreen().availableGeometry()
        w, h = 1100, 600
        self.setGeometry((screen.width() - w)//2, (screen.height() - h)//2, w, h)
        self.finalize_mode(ViewMode.FULLSCREEN)

    def enterEvent(self, event):
        if self.current_mode == ViewMode.SIDEBAR and self.is_collapsed: self.expand_sidebar()
        self.collapse_timer.stop()

    def leaveEvent(self, event):
        if self.current_mode == ViewMode.SIDEBAR and not self.is_collapsed:
            if not self.rect().contains(self.mapFromGlobal(QCursor.pos())):
                self.collapse_timer.start(250)

    def collapse_sidebar(self):
        if self.current_mode != ViewMode.SIDEBAR or self.is_collapsed: return
        self.is_collapsed = True
        screen = QApplication.primaryScreen().availableGeometry()
        anim = QPropertyAnimation(self, b"geometry")
        anim.setDuration(250)
        anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        anim.setEndValue(QRect(screen.width() - self.collapsed_width, self.y(), self.collapsed_width, self.height()))
        QTimer.singleShot(100, lambda: self.main_widget.hide())
        anim.start()
        self.trans_anim = anim

    def expand_sidebar(self):
        if not self.is_collapsed: return
        self.is_collapsed = False
        self.main_widget.show()
        anim = QPropertyAnimation(self, b"geometry")
        anim.setDuration(200)
        anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        anim.setEndValue(self.sidebar_geometry)
        anim.start()
        self.trans_anim = anim

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_pos = event.globalPosition().toPoint() - self.pos()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and hasattr(self, 'drag_pos'):
            self.move(event.globalPosition().toPoint() - self.drag_pos)


if __name__ == "__main__":
    if sys.platform == "linux": os.environ["QT_QPA_PLATFORM"] = "xcb"
    app = QApplication(sys.argv)
    window = ScheduleView()
    window.show()
    sys.exit(app.exec())
