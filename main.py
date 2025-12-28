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
    QHBoxLayout, QLabel, QPushButton, QScrollArea, QLineEdit
)
from PyQt6.QtCore import Qt, QRect, QTimer, QPropertyAnimation, QEasingCurve, QPoint, pyqtProperty, QUrl
from PyQt6.QtMultimedia import QSoundEffect
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QCursor, QFontMetrics


# 网格常量
CELL_WIDTH_FULL = 140   
CELL_WIDTH_SIDE = 240   
CELL_HEIGHT = 90        
NAME_COL_WIDTH = 100    


class ViewMode(Enum):
    SIDEBAR = 1      
    FULLSCREEN = 2   


class TaskStatus(Enum):
    TODO = "需要进行"
    BLOCKED = "阻塞中"
    DONE = "已完成"


@dataclass
class Task:
    title: str
    person: str
    date: date
    start_hour: int = 9
    duration: int = 2
    color: str = "#2E3440"
    status: TaskStatus = TaskStatus.TODO
    id: str = ""

    def __post_init__(self):
        if not self.id:
            import uuid
            self.id = str(uuid.uuid4())[:8]


class InlineEditor(QLineEdit):
    def __init__(self, parent, rect, callback):
        super().__init__(parent)
        self.callback = callback
        self.finalized = False
        self.setGeometry(rect)
        self.setStyleSheet("""
            QLineEdit { 
                background: #2A3039; 
                color: white; 
                border: 2px solid #4A90E2; 
                padding: 2px;
                font-family: 'Consolas';
                font-size: 11px;
            }
        """)
        self.setFocus()
        self.returnPressed.connect(self.finalize)
        
    def finalize(self):
        if self.finalized: return
        self.finalized = True
        if self.text().strip():
            self.callback(self.text().strip())
        self.deleteLater()

    def focusOutEvent(self, event):
        # 失去焦点时自动提交，实现“无感”转化
        self.finalize()
        super().focusOutEvent(event)


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

        # 钉住按钮 (仅在需要时外部控制显示)
        self.pin_btn = QPushButton("📌")
        self.pin_btn.setFixedSize(30, 30)
        self.pin_btn.setCheckable(True)
        self.pin_btn.setStyleSheet("""
            QPushButton { background: transparent; color: white; border: none; font-size: 14px; }
            QPushButton:hover { background: #3A4049; }
            QPushButton:checked { background: #4A90E2; color: #FFFFFF; border-radius: 4px; }
        """)
        self.layout.addWidget(self.pin_btn)
        
        self.toggle_btn = QPushButton("→")
        self.toggle_btn.setFixedSize(30, 30)
        self.toggle_btn.setStyleSheet("""
            QPushButton { background: #3A4049; color: white; border: none; border-radius: 40px; font-weight: bold; font-size: 16px; }
            QPushButton:hover { background: #4A5059; }
        """)
        self.layout.addWidget(self.toggle_btn)
        
        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(30, 30)
        self.close_btn.setStyleSheet("QPushButton { background: transparent; color: white; border: none; } QPushButton:hover { background: #e81123; }")
        self.layout.addWidget(self.close_btn)

    def mousePressEvent(self, event):
        if self.window().current_mode == ViewMode.SIDEBAR:
            return  # 侧边栏模式禁止通过标题栏移动窗口
            
        if event.button() == Qt.MouseButton.LeftButton:
            self.window().drag_pos = event.globalPosition().toPoint() - self.window().pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.window().current_mode == ViewMode.FULLSCREEN:
            if event.buttons() == Qt.MouseButton.LeftButton and hasattr(self.window(), 'drag_pos'):
                self.window().move(event.globalPosition().toPoint() - self.window().drag_pos)
                event.accept()


class GridPersonRow(QWidget):
    def __init__(self, person_name: str, tasks: List[Task], 
                 start_date: date, days: int, col_widths: List[int], parent=None):
        super().__init__(parent)
        self.person_name, self.tasks, self.start_date, self.days = person_name, tasks, start_date, days
        self.days, self.col_widths = days, col_widths
        self.col_offsets = self.calculate_offsets()
        self._strikethrough_progress = {} # task_id -> progress (0.0 to 1.0)
        self._current_anim_task_id = None # 用于动画属性追踪
        self.update_date_map()
        self.setFixedHeight(CELL_HEIGHT)
        # 固定最小宽度为总列宽之和 + 人名列宽
        self.setMinimumWidth(sum(col_widths) + NAME_COL_WIDTH)
        
        # 初始化音效
        self.click_sound = QSoundEffect()

    def calculate_offsets(self):
        offsets = [0] * len(self.col_widths)
        curr = 0
        for i in range(len(self.col_widths)):
            offsets[i] = curr
            curr += self.col_widths[i]
        return offsets

    def update_date_map(self):
        self.date_map = {}
        for t in self.tasks:
            if t.date not in self.date_map: self.date_map[t.date] = []
            self.date_map[t.date].append(t)

    def get_strikethrough(self, task_id):
        return self._strikethrough_progress.get(task_id, 0.0)
        
    def _set_strikes(self, val):
        if self._current_anim_task_id:
            self._strikethrough_progress[self._current_anim_task_id] = val
        self.update()

    def _get_strikes(self):
        if self._current_anim_task_id:
            return self._strikethrough_progress.get(self._current_anim_task_id, 0.0)
        return 0.0

    strikes = pyqtProperty(float, _get_strikes, _set_strikes)

    def update_tasks(self, tasks, col_widths=None):
        """核心修复：更新任务列表时必须重构日期映射"""
        if col_widths is not None:
            self.col_widths = col_widths
            self.col_offsets = self.calculate_offsets()
            self.setMinimumWidth(sum(col_widths) + NAME_COL_WIDTH)
        self.tasks = tasks
        self.update_date_map()
        self.update()
    
    def get_col_rect(self, i):
        return QRect(self.col_offsets[i] + NAME_COL_WIDTH, 0, self.col_widths[i], CELL_HEIGHT)

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
        grid_pen = QPen(QColor("#3A4049"), 1)
        
        for i in range(self.days):
            current_date = self.start_date + timedelta(days=i)
            cell_x = self.col_offsets[i] + NAME_COL_WIDTH
            cell_width = self.col_widths[i]
            cell_rect = QRect(cell_x, 0, cell_width, CELL_HEIGHT)
            
            painter.setPen(grid_pen)
            painter.drawRect(cell_rect)
            
            if current_date in self.date_map:
                self.draw_tasks_in_cell(painter, cell_rect, self.date_map[current_date])

    def mouseDoubleClickEvent(self, event):
        # 双击事件现已禁用，统一使用单击逻辑
        pass

    def mousePressEvent(self, event):
        # 寻找点击的单元格
        x = event.position().x()
        if x < NAME_COL_WIDTH: return
        
        # 识别具体的列
        col = -1
        rel_x = x - NAME_COL_WIDTH
        for i, (off, w) in enumerate(zip(self.col_offsets, self.col_widths)):
            if off <= rel_x < off + w:
                col = i
                break
        if col == -1: return
        
        target_date = self.start_date + timedelta(days=col)
        cell_width = self.col_widths[col]
        
        # 1. 检测是否点击在已有任务上
        if target_date in self.date_map:
            rect = QRect(self.col_offsets[col] + NAME_COL_WIDTH, 0, cell_width, CELL_HEIGHT)
            tasks = self.date_map[target_date]
            spacing = 4
            available_h = rect.height() - (spacing * 2)
            block_h = min(24, (available_h - (len(tasks) - 1) * 2) // len(tasks))
            
            for idx, task in enumerate(tasks):
                y = spacing + idx * (block_h + 2)
                task_rect = QRect(rect.x() + 4, y, rect.width() - 8, block_h)
                
                if task_rect.contains(event.position().toPoint()):
                    # 右侧状态开关区域检测 (总宽度约 80px)
                    sw_w = 80
                    sw_rect = QRect(task_rect.right() - sw_w, y, sw_w, block_h)
                    if sw_rect.contains(event.position().toPoint()):
                        # 计算点击了哪一小块
                        local_x = event.position().x() - sw_rect.x()
                        seg_w = sw_w / 3
                        if local_x < seg_w:
                            task.status = TaskStatus.TODO
                        elif local_x < seg_w * 2:
                            task.status = TaskStatus.BLOCKED
                        else:
                            task.status = TaskStatus.DONE
                            self.animate_strikethrough(task)
                        
                        if self.click_sound.isLoaded(): self.click_sound.play()
                        self.update()
                        return
                    
                    # 否则开始拖拽该任务 (如果有移动)
                    main_window = self.window()
                    if hasattr(main_window, "start_task_drag"):
                        offset = event.position().toPoint() - QPoint(rect.x() + 4, y)
                        main_window.start_task_drag(task, self, offset)
                        return
        
        # 2. 如果点击的是空白区域，直接触发创建
        # 计算输入框位置 (在点击处垂直居中一个 24px 高的输入框)
        click_y = event.position().y()
        rect_editor = QRect(self.col_offsets[col] + NAME_COL_WIDTH + 4, int(click_y - 12), cell_width - 8, 24)
        
        def create_task(title):
            new_task = Task(title=title, person=self.person_name, date=target_date)
            main_window = self.window()
            if hasattr(main_window, "add_task"):
                main_window.add_task(new_task)

        self.editor = InlineEditor(self, rect_editor, create_task)
        self.editor.show()
        
        super().mousePressEvent(event)

    def cycle_task_status(self, task):
        # TODO -> BLOCKED -> DONE -> TODO
        if task.status == TaskStatus.TODO:
            task.status = TaskStatus.BLOCKED
        elif task.status == TaskStatus.BLOCKED:
            task.status = TaskStatus.DONE
            self.animate_strikethrough(task)
        else:
            task.status = TaskStatus.TODO
            self._strikethrough_progress[task.id] = 0.0
            
        # 播放音效 (如果有)
        if self.click_sound.isLoaded():
            self.click_sound.play()
            
        self.update()

    def animate_strikethrough(self, task):
        self._current_anim_task_id = task.id
        self._anim = QPropertyAnimation(self, b"strikes")
        self._anim.setDuration(400)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._anim.start()

    def draw_tasks_in_cell(self, painter: QPainter, rect: QRect, tasks: List[Task]):
        count = len(tasks)
        if count == 0: return
        spacing = 4
        available_h = rect.height() - (spacing * 2)
        block_h = min(24, (available_h - (count - 1) * 2) // count)
        
        for idx, task in enumerate(tasks):
            y = spacing + idx * (block_h + 2)
            task_rect = QRect(rect.x() + 4, y, rect.width() - 8, block_h)
            
            # 1. 背景 (默认为白色)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.fillRect(task_rect, QColor(task.color))
            
            # 2. 绘制右侧状态开关 (待办 | 阻塞 | 完成) - 使用小字体
            sw_w = 80
            sw_rect = QRect(task_rect.right() - sw_w, y, sw_w, block_h)
            painter.setFont(QFont("Microsoft YaHei", 7, QFont.Weight.Bold))
            
            segments = [
                (TaskStatus.TODO, "待办", "#5B859E"),
                (TaskStatus.BLOCKED, "阻塞", "#E3A857"),
                (TaskStatus.DONE, "完成", "#7FAE8A")
            ]
            
            seg_w = sw_w // 3
            for i, (status, label, color) in enumerate(segments):
                seg_rect = QRect(sw_rect.x() + i * seg_w, sw_rect.y(), seg_w, block_h)
                if task.status == status:
                    # 激活态：有色背景 + 白色文字
                    painter.fillRect(seg_rect, QColor(color))
                    painter.setPen(QColor("#FFFFFF"))
                else:
                    # 未激活：深灰色背景 + 灰度文字
                    painter.fillRect(seg_rect, QColor("#3A4049"))
                    painter.setPen(QColor("#888888"))
                
                painter.drawText(seg_rect, Qt.AlignmentFlag.AlignCenter, label)
                # 分隔线
                if i < 2:
                    painter.setPen(QPen(QColor("#1F2329"), 1))
                    painter.drawLine(seg_rect.right(), seg_rect.top(), seg_rect.right(), seg_rect.bottom())

            # 3. 边框
            painter.setPen(QPen(QColor("#3A4049"), 2)) # 加深边框感
            painter.drawRect(task_rect)
            
            # 4. 任务标题文字
            painter.setPen(QColor("#FFFFFF")) # 恢复白色文字 (背景变深了)
            painter.setFont(QFont("Microsoft YaHei", 12, QFont.Weight.Bold)) # 正确字体：16px 约等于 12pt
            text_rect = task_rect.adjusted(12, 0, -sw_w - 5, 0)
            metrics = painter.fontMetrics()
            elided_text = metrics.elidedText(task.title, Qt.TextElideMode.ElideRight, text_rect.width())
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_text)
            
            # 5. 划线动画 (如果是已完成)
            progress = self.get_strikethrough(task.id)
            if task.status == TaskStatus.DONE and progress > 0:
                painter.setPen(QPen(QColor("#FF4444"), 2))
                text_width = metrics.horizontalAdvance(elided_text)
                line_y = text_rect.center().y()
                painter.drawLine(text_rect.x(), line_y, int(text_rect.x() + text_width * progress), line_y)


class ModeHeader(QWidget):
    def __init__(self, start_date: date, days: int, col_widths: List[int], mode: ViewMode, parent=None):
        super().__init__(parent)
        self.start_date, self.days, self.mode = start_date, days, mode
        self.col_widths = col_widths
        self.setFixedHeight(40)
        self.setMinimumWidth(sum(col_widths) + NAME_COL_WIDTH)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#2A3039"))
        
        # 名字部分
        painter.setPen(QPen(QColor("#3A4049"), 1))
        painter.drawRect(0, 0, NAME_COL_WIDTH, 40)
        
        # 分享列计算
        offsets = []
        curr = 0
        for w in self.col_widths:
            offsets.append(curr)
            curr += w
        
        for i in range(self.days):
            current_date = self.start_date + timedelta(days=i)
            cell_x = offsets[i] + NAME_COL_WIDTH
            cell_width = self.col_widths[i]
            header_rect = QRect(cell_x, 0, cell_width, 40)
            
            painter.setPen(QPen(QColor("#3A4049"), 1))
            painter.drawRect(header_rect)
            painter.setPen(QColor("#888888"))
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
        
        self.current_mode = ViewMode.SIDEBAR
        self.is_collapsed = False
        self.is_pinned = False
        self.collapsed_width = 8
        self.collapse_timer = QTimer()
        self.collapse_timer.setSingleShot(True)
        self.collapse_timer.timeout.connect(self.collapse_sidebar)
        
        self.sidebar_geometry = QRect()
        self.fullscreen_geometry = QRect()
        self.all_tasks = []
        
        # 拖拽全局状态
        self.dragging_task = None
        self.drag_ghost_pos = QPoint()
        self.drag_origin_row = None
        self.drag_target_info = None # (person_name, date, index)
        
        self.init_ui()
        self.load_demo_data()
        
        # 记录初始高度
        self.init_height = self.height()
        
        # 设置初始几何位置
        screen = QApplication.primaryScreen().availableGeometry()
        h = screen.height() - 100
        
        # 预先设置好两个模式的几何参数
        self.fullscreen_geometry = QRect(screen.width() - 1100, 50, 1100, h)
        self.sidebar_geometry = QRect(screen.width() - 360, 50, 360, h)
        
        # 以侧边栏启动
        self.setGeometry(self.sidebar_geometry)
        self.update_ui_state(ViewMode.SIDEBAR)
        self.show()
        self.rebuild_content()

    def init_ui(self):
        self.main_widget = QWidget()
        self.setCentralWidget(self.main_widget)
        self.main_layout = QVBoxLayout(self.main_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        
        # 使用自定义标题栏
        self.custom_title_bar = CustomTitleBar(self)
        self.main_layout.addWidget(self.custom_title_bar)
        
        # 提取按钮引用以便原本逻辑工作
        self.pin_btn = self.custom_title_bar.pin_btn
        self.toggle_btn = self.custom_title_bar.toggle_btn
        self.close_btn = self.custom_title_bar.close_btn
        
        self.pin_btn.clicked.connect(self.toggle_pin)
        self.toggle_btn.clicked.connect(self.toggle_view_mode)
        self.close_btn.clicked.connect(QApplication.quit)
        
        self.create_content_area()
        self.setStyleSheet("QMainWindow { background-color: #1F2329; border: 1px solid #3A4049; }")

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
        self.all_persons = ["张三", "李四", "王五", "周七"] # 固定人员列表
        t = date.today()
        self.all_tasks = [
            Task("周期巡检", "张三", t, 9, 1),
            Task("供氧维护", "张三", t, 10, 2),
            Task("哈奇喂养", "李四", t, 8, 1),
            Task("实验室分析", "张三", t + timedelta(days=1), 14, 2),
        ]

    def rebuild_content(self):
        """流式更新内容，适配父窗体拉伸"""
        today = date.today()
        days = 1 if self.current_mode == ViewMode.SIDEBAR else 7
        
        # 0. 计算动态列宽
        self.col_widths = []
        metrics = QFontMetrics(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        for i in range(days):
            target_date = today + timedelta(days=i)
            tasks_on_day = [t for t in self.all_tasks if t.date == target_date]
            if not tasks_on_day:
                w = 80 # 不论是在全屏还是侧边栏，没有任务时都保持紧凑
            else:
                max_txt_w = 0
                for t in tasks_on_day:
                    max_txt_w = max(max_txt_w, metrics.horizontalAdvance(t.title))
                w = max_txt_w + 80 + 30 # 标题 + 状态开关(80) + 边距
                min_w = 120 if self.current_mode == ViewMode.FULLSCREEN else 180
                w = max(min_w, w)
            self.col_widths.append(w)
        
        # 1. 更新表头
        total_grid_w = sum(self.col_widths) + NAME_COL_WIDTH
        if self.container_layout.count() > 0:
            header = self.container_layout.itemAt(0).widget()
            if isinstance(header, ModeHeader):
                header.days, header.col_widths, header.mode = days, self.col_widths, self.current_mode
                header.setFixedWidth(total_grid_w)
                header.update()
            else:
                self.clear_layout()
                self.container_layout.addWidget(ModeHeader(today, days, self.col_widths, self.current_mode))
        else:
            self.container_layout.addWidget(ModeHeader(today, days, self.col_widths, self.current_mode))

        # 设置容器固定宽度，消除布局自动拉伸带来的对齐误差
        self.container.setFixedWidth(total_grid_w)

        # 2. 更新人员行
        persons = self.all_persons
        existing_rows = []
        for i in range(1, self.container_layout.count()):
            w = self.container_layout.itemAt(i).widget()
            if isinstance(w, GridPersonRow): existing_rows.append(w)
        
        for i, p in enumerate(persons):
            p_tasks = [t for t in self.all_tasks if t.person == p]
            if i < len(existing_rows):
                row = existing_rows[i]
                row.person_name = p
                row.update_tasks(p_tasks, self.col_widths)
                row.days = days
            else:
                self.container_layout.insertWidget(i + 1, GridPersonRow(p, p_tasks, today, days, self.col_widths))
        
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

        # 5. 如果是侧边栏模式，同步窗口几何尺寸
        if self.current_mode == ViewMode.SIDEBAR:
            screen = QApplication.primaryScreen().availableGeometry()
            # 彻底消除多余空白：窗口宽度 = 内容宽度 + 2px(边框预留)
            target_w = max(200, min(800, total_grid_w + 2))
            h = screen.height() - 100
            self.sidebar_geometry = QRect(screen.width() - target_w, 50, target_w, h)
            
            # 如果当前不是在动画中且没有折叠，则直接更新尺寸
            if not self.is_collapsed and (not hasattr(self, "anim") or self.anim.state() == QPropertyAnimation.State.Stopped):
                self.setGeometry(self.sidebar_geometry)

    def clear_layout(self):
        while self.container_layout.count():
            item = self.container_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

    def add_task(self, task: Task):
        self.all_tasks.append(task)
        self.rebuild_content()

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
        if target_mode == ViewMode.FULLSCREEN:
            w = 1100
        else:
            # 侧边栏模式从 rebuild_content 已经算好的几何位置获取宽度
            w = self.sidebar_geometry.width()
            if w < 100: w = 360 # 保底宽度
            
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
        """更新按钮和可见性"""
        if mode == ViewMode.SIDEBAR:
            # 侧边栏隐藏拖拽标题文字，仅保留按钮
            self.custom_title_bar.title_label.hide()
            self.pin_btn.show()
            self.toggle_btn.setText("←")
            self.setMouseTracking(True)
            self.setWindowOpacity(0.85) # 侧边栏模式半透明
        else:
            self.custom_title_bar.show()
            self.custom_title_bar.title_label.show()
            self.pin_btn.hide()
            self.toggle_btn.setText("→")
            self.is_pinned = False
            self.pin_btn.setChecked(False)
            self.setMouseTracking(False)
            self.setWindowOpacity(1.0) # 全屏恢复不透明
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

    # --- 拖拽系统实现 ---
    
    def mousePressEvent(self, event):
        # 注意：此处的主窗口 mousePress 不再负责移动，由 CustomTitleBar 接管
        # 从而避免干扰 GridPersonRow 的点击/拖拽检测
        pass

    def start_task_drag(self, task, row_widget, offset):
        self.dragging_task = task
        self.drag_origin_row = row_widget
        self.drag_offset = offset
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        self.grabMouse() # 关键：夺取鼠标控制权，确保 move 事件传给 ScheduleView
        self.update()

    def mouseMoveEvent(self, event):
        if self.dragging_task:
            self.drag_ghost_pos = event.position().toPoint() - self.drag_offset
            self.update_drag_preview(event.position().toPoint())
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.dragging_task:
            self.releaseMouse() # 释放鼠标控制权
            self.finalize_task_drag()
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().mouseReleaseEvent(event)

    def update_drag_preview(self, global_point):
        # 寻找目标行和日期
        local_pos = self.scroll.widget().mapFromGlobal(self.mapToGlobal(global_point))
        target_row = None
        for i in range(1, self.container_layout.count()):
            w = self.container_layout.itemAt(i).widget()
            if isinstance(w, GridPersonRow):
                if w.geometry().contains(local_pos):
                    target_row = w
                    break
        
        if target_row:
            x_in_row = local_pos.x() - target_row.x() - NAME_COL_WIDTH
            if x_in_row >= 0:
                # 识别具体的列 (适配动态宽)
                col = -1
                for i, (off, w) in enumerate(zip(target_row.col_offsets, target_row.col_widths)):
                    if off <= x_in_row < off + w:
                        col = i
                        break
                
                if col != -1:
                    target_date = target_row.start_date + timedelta(days=col)
                    self.drag_target_info = (target_row.person_name, target_date)
                else:
                    self.drag_target_info = None
            else:
                self.drag_target_info = None
        else:
            self.drag_target_info = None

    def finalize_task_drag(self):
        if self.drag_target_info:
            target_p, target_d = self.drag_target_info
            
            # 2. 拖动后自动回到 TODO 状态，并强制重置该任务的所有划线进度
            self.dragging_task.person = target_p
            self.dragging_task.date = target_d
            self.dragging_task.status = TaskStatus.TODO
            
            # 遍边所有行，清除该任务的本地动画进度缓存
            for i in range(1, self.container_layout.count()):
                w = self.container_layout.itemAt(i).widget()
                if isinstance(w, GridPersonRow):
                    if self.dragging_task.id in w._strikethrough_progress:
                        w._strikethrough_progress[self.dragging_task.id] = 0.0
            
            self.rebuild_content()
        
        self.dragging_task = None
        self.drag_target_info = None
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.dragging_task:
            painter = QPainter(self)
            painter.setOpacity(0.7)
            # 绘制幽灵块 (根据全屏/侧边栏调整宽度)
            w = CELL_WIDTH_SIDE - 20 if self.current_mode == ViewMode.SIDEBAR else CELL_WIDTH_FULL - 20
            rect = QRect(self.drag_ghost_pos.x(), self.drag_ghost_pos.y(), int(w), 24)
            painter.fillRect(rect, QColor(self.dragging_task.color))
            painter.setPen(QPen(Qt.GlobalColor.white, 1))
            painter.drawRect(rect)
            painter.drawText(rect.adjusted(5,0,0,0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.dragging_task.title)


if __name__ == "__main__":
    if sys.platform == "linux": os.environ["QT_QPA_PLATFORM"] = "xcb"
    app = QApplication(sys.argv)
    window = ScheduleView()
    window.show()
    sys.exit(app.exec())
