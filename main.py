#!/usr/bin/env python3
"""
Schedule Master - Step 3: UI Controls & Pinning
改进按钮逻辑与侧边栏置顶功能
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
CELL_WIDTH_FULL = 140   
CELL_WIDTH_SIDE = 240   
CELL_HEIGHT = 90        
NAME_COL_WIDTH = 100    


class ViewMode(Enum):
    SIDEBAR = 1      
    FULLSCREEN = 2   


@dataclass
class Task:
    title: str
    person: str
    date: date
    start_hour: int = 9
    duration: int = 2
    color: str = "#5B859E"


class GridPersonRow(QWidget):
    def __init__(self, person_name: str, tasks: List[Task], 
                 start_date: date, days: int, parent=None):
        super().__init__(parent)
        self.person_name, self.tasks, self.start_date, self.days = person_name, tasks, start_date, days
        self.date_map: Dict[date, List[Task]] = {}
        for t in tasks:
            if t.date not in self.date_map: self.date_map[t.date] = []
            self.date_map[t.date].append(t)
        self.setFixedHeight(CELL_HEIGHT)
    
    def get_cell_width(self):
        return (self.width() - NAME_COL_WIDTH) / self.days

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.fillRect(self.rect(), QColor("#1F2329"))
        
        # 1. 绘制名字单元格
        name_rect = QRect(0, 0, NAME_COL_WIDTH, CELL_HEIGHT)
        painter.fillRect(name_rect, QColor("#2A3039"))
        painter.setPen(QPen(QColor("#3A4049"), 2))
        painter.drawRect(name_rect)
        painter.setPen(QColor("#FFFFFF"))
        painter.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        painter.drawText(name_rect.adjusted(5, 0, -5, 0), Qt.AlignmentFlag.AlignCenter, self.person_name)
        
        # 2. 绘制网格单元格
        cell_width = self.get_cell_width()
        painter.translate(NAME_COL_WIDTH, 0)
        grid_pen = QPen(QColor("#3A4049"), 1)
        
        for i in range(self.days):
            current_date = self.start_date + timedelta(days=i)
            cell_x = int(i * cell_width)
            cell_rect = QRect(cell_x, 0, int(cell_width), CELL_HEIGHT)
            
            painter.setPen(grid_pen)
            painter.drawRect(cell_rect)
            
            if current_date in self.date_map:
                self.draw_tasks_in_cell(painter, cell_rect, self.date_map[current_date])

    def draw_tasks_in_cell(self, painter: QPainter, rect: QRect, tasks: List[Task]):
        count = len(tasks)
        if count == 0: return
        spacing = 4
        available_h = rect.height() - (spacing * 2)
        block_h = min(24, (available_h - (count - 1) * 2) // count)
        for idx, task in enumerate(tasks):
            y = spacing + idx * (block_h + 2)
            task_rect = QRect(rect.x() + 4, y, rect.width() - 8, block_h)
            painter.fillRect(task_rect, QColor(task.color))
            painter.setPen(QPen(QColor(task.color).darker(140), 1))
            painter.drawRect(task_rect)
            painter.setPen(QColor("#FFFFFF"))
            painter.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
            display_text = task.title
            if rect.width() > 180: display_text += f" ({task.start_hour:02d}:00)"
            metrics = painter.fontMetrics()
            elided_text = metrics.elidedText(display_text, Qt.TextElideMode.ElideRight, task_rect.width() - 4)
            painter.drawText(task_rect.adjusted(4, 0, -4, 0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_text)


class ModeHeader(QWidget):
    def __init__(self, start_date: date, days: int, mode: ViewMode, parent=None):
        super().__init__(parent)
        self.start_date, self.days, self.mode = start_date, days, mode
        self.setFixedHeight(40)
    
    def get_cell_width(self):
        return (self.width() - NAME_COL_WIDTH) / self.days

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#2A3039"))
        
        # 名字部分
        painter.setPen(QPen(QColor("#3A4049"), 2))
        painter.drawRect(0, 0, NAME_COL_WIDTH, 40)
        
        # 单元格部分
        cell_width = self.get_cell_width()
        painter.translate(NAME_COL_WIDTH, 0)
        
        for i in range(self.days):
            current_date = self.start_date + timedelta(days=i)
            cell_x = int(i * cell_width)
            header_rect = QRect(cell_x, 0, int(cell_width), 40)
            
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
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Schedule Master")
        
        # 核心变革：统一窗口 Flag，全程不修改 Flag 以避免闪烁和重建
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint | 
            Qt.WindowType.Tool
        )
        
        self.current_mode = ViewMode.FULLSCREEN
        self.is_collapsed = False
        self.is_pinned = False
        self.collapsed_width = 8
        self.collapse_timer = QTimer()
        self.collapse_timer.setSingleShot(True)
        self.collapse_timer.timeout.connect(self.collapse_sidebar)
        
        self.sidebar_geometry = QRect()
        self.fullscreen_geometry = QRect()
        self.all_tasks = []
        
        self.init_ui()
        self.load_demo_data()
        
        # 设置初始几何位置
        screen = QApplication.primaryScreen().availableGeometry()
        w, h = 1100, screen.height() - 100
        self.setGeometry(screen.width() - w, 50, w, h)
        self.show()
        self.rebuild_content()

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
        layout.setSpacing(5)
        
        self.title_label = QLabel("📋 ONI")
        self.title_label.setStyleSheet("color: #FFFFFF; font-weight: bold; font-family: 'Consolas';")
        layout.addWidget(self.title_label)
        layout.addStretch()

        # 钉住按钮 (仅在侧边栏模式显示逻辑)
        self.pin_btn = QPushButton("📌")
        self.pin_btn.setFixedSize(30, 30)
        self.pin_btn.setCheckable(True)
        self.pin_btn.clicked.connect(self.toggle_pin)
        self.pin_btn.setStyleSheet("""
            QPushButton { background: transparent; color: white; border: none; font-size: 14px; }
            QPushButton:hover { background: #3A4049; }
            QPushButton:checked { background: #4A90E2; color: #FFFFFF; border-radius: 4px; }
        """)
        self.pin_btn.hide()
        layout.addWidget(self.pin_btn)
        
        # 切换按钮 - 初始全屏转侧边栏 (→)
        self.toggle_btn = QPushButton("→")
        self.toggle_btn.setFixedSize(30, 30)
        self.toggle_btn.clicked.connect(self.toggle_view_mode)
        self.toggle_btn.setStyleSheet("""
            QPushButton { background: #3A4049; color: white; border: none; border-radius: 40px; font-weight: bold; font-size: 16px; }
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
            Task("哈奇喂养", "李四", t, 8, 1, "#D98E7A"),
            Task("实验室分析", "张三", t + timedelta(days=1), 14, 2, "#7FAE8A"),
        ]

    def rebuild_content(self):
        """流式更新内容，适配父窗体拉伸"""
        today = date.today()
        days = 1 if self.current_mode == ViewMode.SIDEBAR else 7
        
        # 1. 更新表头
        if self.container_layout.count() > 0:
            header = self.container_layout.itemAt(0).widget()
            if isinstance(header, ModeHeader):
                header.mode, header.days = self.current_mode, days
            else:
                self.clear_layout()
                self.container_layout.addWidget(ModeHeader(today, days, self.current_mode))
        else:
            self.container_layout.addWidget(ModeHeader(today, days, self.current_mode))

        # 2. 更新人员行
        persons = sorted(list(set(t.person for t in self.all_tasks)))
        existing_rows = []
        for i in range(1, self.container_layout.count()):
            w = self.container_layout.itemAt(i).widget()
            if isinstance(w, GridPersonRow): existing_rows.append(w)
        
        for i, p in enumerate(persons):
            p_tasks = [t for t in self.all_tasks if t.person == p]
            if i < len(existing_rows):
                row = existing_rows[i]
                row.person_name, row.tasks, row.days = p, p_tasks, days
            else:
                self.container_layout.insertWidget(i + 1, GridPersonRow(p, p_tasks, today, days))
        
        # 3. 清理冗余
        if len(existing_rows) > len(persons):
            for i in range(len(persons), len(existing_rows)): existing_rows[i].deleteLater()

        # 4. 底部弹簧
        if self.container_layout.count() > 0:
            last = self.container_layout.itemAt(self.container_layout.count()-1)
            if not last or not last.spacerItem(): self.container_layout.addStretch()
        
        self.update()

        if self.container_layout.count() > 0 and not isinstance(self.container_layout.itemAt(self.container_layout.count()-1), QWidget):
             self.container_layout.addStretch()

    def clear_layout(self):
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

    def toggle_view_mode(self):
        self.animate_transition(ViewMode.SIDEBAR if self.current_mode == ViewMode.FULLSCREEN else ViewMode.FULLSCREEN)

    def toggle_pin(self):
        self.is_pinned = self.pin_btn.isChecked()
        if self.is_pinned: 
            self.collapse_timer.stop()
        else:
            # 如果取消钉住时鼠标已经在外面，立即触发折叠检查
            if not self.rect().contains(self.mapFromGlobal(QCursor.pos())):
                self.collapse_timer.start(250)

    def animate_transition(self, target_mode: ViewMode):
        screen = QApplication.primaryScreen().availableGeometry()
        if self.is_collapsed: self.expand_sidebar()
        
        # 1. 唯一一次更新 UI 结构（不改变 Flag，不透明化）
        self.current_mode = target_mode
        self.update_ui_state(target_mode)
        
        # 2. 计算目标尺寸 (Y轴和高度始终保持同步)
        w = 1100 if target_mode == ViewMode.FULLSCREEN else 360
        h = screen.height() - 100
        target_geo = QRect(screen.width() - w, 50, w, h)
        if target_mode == ViewMode.SIDEBAR: self.sidebar_geometry = target_geo
        
        # 3. 开始丝滑拉伸动画 (不涉及窗口重绘/Flags改变)
        self.anim = QPropertyAnimation(self, b"geometry")
        self.anim.setDuration(400)
        self.anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.anim.setEndValue(target_geo)
        self.anim.start()

    def update_ui_state(self, mode: ViewMode):
        """仅更新按钮和网格逻辑，不触碰窗口 Flag"""
        if mode == ViewMode.SIDEBAR:
            self.toggle_btn.setText("←")
            self.pin_btn.show()
            self.setMouseTracking(True)
        else:
            self.toggle_btn.setText("→")
            self.pin_btn.hide()
            self.is_pinned = False
            self.pin_btn.setChecked(False)
            self.setMouseTracking(False)
        self.rebuild_content()

    def finalize_mode(self, mode: ViewMode):
        self.update_ui_state(mode)
        self.show()

    def show_fullscreen_mode(self):
        # 初始显示
        pass 

    def enterEvent(self, event):
        if self.current_mode == ViewMode.SIDEBAR and self.is_collapsed: self.expand_sidebar()
        self.collapse_timer.stop()

    def leaveEvent(self, event):
        if self.current_mode == ViewMode.SIDEBAR and not self.is_collapsed and not self.is_pinned:
            if not self.rect().contains(self.mapFromGlobal(QCursor.pos())):
                self.collapse_timer.start(250)

    def collapse_sidebar(self):
        if self.current_mode != ViewMode.SIDEBAR or self.is_collapsed or self.is_pinned: return
        self.is_collapsed = True
        screen = QApplication.primaryScreen().availableGeometry()
        
        self.coll_anim = QPropertyAnimation(self, b"geometry")
        self.coll_anim.setDuration(250)
        self.coll_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        target_rect = QRect(screen.width() - self.collapsed_width, self.y(), self.collapsed_width, self.height())
        self.coll_anim.setEndValue(target_rect)
        
        # 动画开始后稍晚一点隐藏内容，保持平滑感
        QTimer.singleShot(150, lambda: self.main_widget.hide() if self.is_collapsed else None)
        self.coll_anim.start()

    def expand_sidebar(self):
        if not self.is_collapsed: return
        self.is_collapsed = False
        
        self.exp_anim = QPropertyAnimation(self, b"geometry")
        self.exp_anim.setDuration(200)
        self.exp_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.exp_anim.setEndValue(self.sidebar_geometry)
        
        # 展开前显示内容
        self.main_widget.show()
        self.exp_anim.start()

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
