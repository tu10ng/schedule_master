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
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QCursor


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
    color: str = "#5B859E"
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
                 start_date: date, days: int, parent=None):
        super().__init__(parent)
        self.person_name, self.tasks, self.start_date, self.days = person_name, tasks, start_date, days
        self.date_map: Dict[date, List[Task]] = {}
        self._strikethrough_progress = {} # task_id -> progress (0.0 to 1.0)
        self.update_date_map()
        self.setFixedHeight(CELL_HEIGHT)
        
        # 初始化音效
        self.click_sound = QSoundEffect()
        # 尝试寻找系统或默认音效，由于没有外部文件，预留位置
        # self.click_sound.setSource(QUrl.fromLocalFile("click.wav")) 
    
    def update_date_map(self):
        self.date_map = {}
        for t in self.tasks:
            if t.date not in self.date_map: self.date_map[t.date] = []
            self.date_map[t.date].append(t)

    def get_strikethrough(self, task_id):
        return self._strikethrough_progress.get(task_id, 0.0)
        
    def set_strikethrough(self, task_id, val):
        self._strikethrough_progress[task_id] = val
        self.update()

    def update_tasks(self, tasks):
        """核心修复：更新任务列表时必须重构日期映射"""
        self.tasks = tasks
        self.update_date_map()
        self.update()
    
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

    def mouseDoubleClickEvent(self, event):
        # 双击事件现已禁用，统一使用单击逻辑
        pass

    def mousePressEvent(self, event):
        # 寻找点击的单元格
        x = event.position().x() - NAME_COL_WIDTH
        if x < 0: return
        
        cell_width = self.get_cell_width()
        col = int(x // cell_width)
        target_date = self.start_date + timedelta(days=col)
        
        # 1. 检测是否点击在已有任务上
        if target_date in self.date_map:
            rect = QRect(int(col * cell_width) + NAME_COL_WIDTH, 0, int(cell_width), CELL_HEIGHT)
            tasks = self.date_map[target_date]
            spacing = 4
            available_h = rect.height() - (spacing * 2)
            block_h = min(24, (available_h - (len(tasks) - 1) * 2) // len(tasks))
            
            for idx, task in enumerate(tasks):
                y = spacing + idx * (block_h + 2)
                task_rect = QRect(rect.x() + 4, y, rect.width() - 8, block_h)
                
                if task_rect.contains(event.position().toPoint()):
                    # 状态点击区域 (左侧 20px)
                    status_rect = QRect(rect.x() + 4, y, 20, block_h)
                    if status_rect.contains(event.position().toPoint()):
                        self.cycle_task_status(task)
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
        rect_editor = QRect(int(col * cell_width) + NAME_COL_WIDTH + 4, int(click_y - 12), int(cell_width) - 8, 24)
        
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
        anim = QPropertyAnimation(self, b"strikes") # 虚拟属性
        anim.setDuration(400)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        
        # 使用自定义更新逻辑，因为 PyqtProperty 对动态 id 不太友好
        def update_anim(val):
            self.set_strikethrough(task.id, val)
            
        anim.valueChanged.connect(update_anim)
        anim.start()
        # 保持引用防止 GC
        if not hasattr(self, '_anims'): self._anims = []
        self._anims.append(anim)

    def draw_tasks_in_cell(self, painter: QPainter, rect: QRect, tasks: List[Task]):
        count = len(tasks)
        if count == 0: return
        spacing = 4
        available_h = rect.height() - (spacing * 2)
        block_h = min(24, (available_h - (count - 1) * 2) // count)
        for idx, task in enumerate(tasks):
            y = spacing + idx * (block_h + 2)
            task_rect = QRect(rect.x() + 4, y, rect.width() - 8, block_h)
            
            # 背景
            painter.fillRect(task_rect, QColor(task.color))
            
            # 状态标识
            status_color = "#FFFFFF"
            status_char = "○"
            if task.status == TaskStatus.BLOCKED:
                status_char = "⚠"
                status_color = "#FFD700"
            elif task.status == TaskStatus.DONE:
                status_char = "●"
                status_color = "#00FF00"
                
            painter.setPen(QPen(QColor(status_color), 2))
            painter.drawText(task_rect.adjusted(2, 0, 0, 0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, status_char)
            
            # 边框
            painter.setPen(QPen(QColor(task.color).darker(140), 1))
            painter.drawRect(task_rect)
            
            # 文字
            painter.setPen(QColor("#FFFFFF"))
            painter.setFont(QFont("Consolas", 8, QFont.Weight.Bold))
            display_text = task.title
            if rect.width() > 180: display_text += f" ({task.start_hour:02d}:00)"
            
            text_rect = task_rect.adjusted(20, 0, -4, 0)
            metrics = painter.fontMetrics()
            elided_text = metrics.elidedText(display_text, Qt.TextElideMode.ElideRight, text_rect.width())
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_text)
            
            # 划线动画 (如果是已完成)
            progress = self.get_strikethrough(task.id)
            if task.status == TaskStatus.DONE and progress > 0:
                painter.setPen(QPen(QColor("#FF4444"), 2))
                text_width = metrics.horizontalAdvance(elided_text)
                line_y = text_rect.center().y()
                # 模拟手写感，稍微抖动一点
                painter.drawLine(text_rect.x(), line_y, int(text_rect.x() + text_width * progress), line_y)


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
        persons = self.all_persons
        existing_rows = []
        for i in range(1, self.container_layout.count()):
            w = self.container_layout.itemAt(i).widget()
            if isinstance(w, GridPersonRow): existing_rows.append(w)
        
        for i, p in enumerate(persons):
            p_tasks = [t for t in self.all_tasks if t.person == p]
            if i < len(existing_rows):
                row = existing_rows[i]
                # 修复：必须通过更新函数刷新内部逻辑
                row.person_name = p
                row.update_tasks(p_tasks)
                row.days = days
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
        """更新按钮和可见性"""
        if mode == ViewMode.SIDEBAR:
            # 侧边栏隐藏拖拽标题文字，仅保留按钮
            self.custom_title_bar.title_label.hide()
            self.pin_btn.show()
            self.toggle_btn.setText("←")
            self.setMouseTracking(True)
        else:
            self.custom_title_bar.show()
            self.custom_title_bar.title_label.show()
            self.pin_btn.hide()
            self.toggle_btn.setText("→")
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
                cell_width = target_row.get_cell_width()
                col = int(x_in_row // cell_width)
                target_date = target_row.start_date + timedelta(days=col)
                self.drag_target_info = (target_row.person_name, target_date)
            else:
                self.drag_target_info = None
        else:
            self.drag_target_info = None

    def finalize_task_drag(self):
        if self.drag_target_info:
            target_p, target_d = self.drag_target_info
            self.dragging_task.person = target_p
            self.dragging_task.date = target_d
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
