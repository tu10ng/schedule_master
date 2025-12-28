#!/usr/bin/env python3
import sys
import os
from datetime import date, timedelta
from typing import List

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, 
    QHBoxLayout, QLabel, QPushButton, QScrollArea, QLineEdit
)
from PyQt6.QtCore import Qt, QRect, QTimer, QPropertyAnimation, QEasingCurve, QPoint, pyqtProperty, QUrl
from PyQt6.QtMultimedia import QSoundEffect
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QCursor, QFontMetrics

# Import modular components and models
from models import ViewMode, TaskStatus, Task
from constants import CELL_WIDTH_FULL, CELL_WIDTH_SIDE, CELL_HEIGHT, NAME_COL_WIDTH
from components.title_bar import CustomTitleBar
from components.grid_row import GridPersonRow
from components.header import ModeHeader
from components.backlog_view import BacklogView

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
        self.collapsed_width = 4
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
        self.drag_target_info = None # (person_name, date)
        
        self.init_ui()
        self.load_demo_data()
        
        # 记录初始几何位置
        screen = QApplication.primaryScreen().availableGeometry()
        self.current_y = (screen.height() - 500) // 2
        
        # 预先隐藏，确保所有初始化完成后再一次性显示
        self.fullscreen_geometry = QRect(screen.width() - 1100, self.current_y, 1100, 600)
        self.sidebar_geometry = QRect(screen.width() - 360, self.current_y, 360, 400)
        
        # 2. 设置初始位置 (必须在 show 之前)
        self.setGeometry(self.sidebar_geometry)
        
        # 3. 静默更新 UI 状态和内容 (计算真正的高度)
        self.update_ui_state(ViewMode.SIDEBAR, animate=False)
        
        # 4. 再次强制设置最终几何 (rebuild_content 之后可能更新了 sidebar_geometry)
        self.setGeometry(self.sidebar_geometry)
        self.setWindowOpacity(0.85)

        # 5. 最后显示
        self.show()

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
        
        # 垂直分割：上方是网格，下方是不紧急任务
        self.backlog_view = BacklogView([])
        self.main_layout.addWidget(self.scroll, stretch=1)
        self.main_layout.addWidget(self.backlog_view)

    def load_demo_data(self):
        self.all_persons = ["张三", "李四", "王五", "周七"] # 固定人员列表
        t = date.today()
        self.all_tasks = [
            Task("周期巡检", "张三", t, 9, 1),
            Task("供氧维护", "张三", t, 10, 2),
            Task("哈奇喂养", "李四", t, 8, 1),
            Task("实验室分析", "张三", t + timedelta(days=1), 14, 2),
            Task("整理工具箱", "", t, scheduled=False, urgent=False), # 明确标记为非紧急
        ]

    def rebuild_content(self, animate=True):
        """流式更新内容，适配父窗体拉伸"""
        today = date.today()
        days = 1 if self.current_mode == ViewMode.SIDEBAR else 7
        
        # 筛选已排期和未排期任务
        scheduled_tasks = [t for t in self.all_tasks if t.scheduled]
        backlog_tasks = [t for t in self.all_tasks if not t.scheduled]
        
        # 0. 计算动态列宽 (必须在更新 BacklogView 前计算，因为 BacklogView 需要对齐)
        self.col_widths = []
        metrics = QFontMetrics(QFont("Microsoft YaHei", 12, QFont.Weight.Bold))
        for i in range(days):
            target_date = today + timedelta(days=i)
            # 关键修复：计算列宽时应考虑当天所有任务（含不紧急任务）
            tasks_on_day = [t for t in self.all_tasks if t.date == target_date]
            if not tasks_on_day:
                w = 80 
            else:
                max_txt_w = 0
                for t in tasks_on_day:
                    max_txt_w = max(max_txt_w, metrics.horizontalAdvance(t.title))
                w = max_txt_w + 80 + 30 
                min_w = 120 if self.current_mode == ViewMode.FULLSCREEN else 180
                w = max(min_w, w)
            self.col_widths.append(w)

        # 1. 更新 BacklogView
        self.backlog_view.update_params(today, days, self.col_widths, backlog_tasks)
        
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
            p_tasks = [t for t in scheduled_tasks if t.person == p]
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

        # 5. 同步窗口几何尺寸 (通过动画应用，且始终保持右侧贴边)
        screen = QApplication.primaryScreen().availableGeometry()
        
        # 计算理想高度: 标题栏(35) + 表头(40) + 人行(N*CELL_HEIGHT) + Backlog(动态) + 边距
        backlog_h = self.backlog_view.height() if hasattr(self, 'backlog_view') else 100
        
        target_content_h = 35 + 40 + (len(persons) * CELL_HEIGHT) + backlog_h + 20
        max_h = screen.height() - 100
        target_h = min(target_content_h, max_h)
        
        # 计算侧边栏和全屏模式的目标几何 (记录当前 Y 以保持位置)
        sidebar_w = max(200, min(800, total_grid_w + 2))
        self.sidebar_geometry = QRect(screen.width() - sidebar_w, self.current_y, sidebar_w, target_h)
        
        fullscreen_w = max(400, min(screen.width() - 50, total_grid_w + 2))
        self.fullscreen_geometry = QRect(screen.width() - fullscreen_w, self.current_y, fullscreen_w, target_h)

        # 应用几何更新
        if not self.is_collapsed:
            target_geo = self.sidebar_geometry if self.current_mode == ViewMode.SIDEBAR else self.fullscreen_geometry
            if animate:
                self.apply_geometry_animation(target_geo)
            else:
                self.setGeometry(target_geo)

    def apply_geometry_animation(self, target_geo: QRect):
        """统一的宽度/位置平滑过渡动画"""
        if self.geometry() == target_geo: return
        
        # 如果已经有动画在运行且目标一致，则跳过
        if hasattr(self, "geo_anim") and self.geo_anim.state() == QPropertyAnimation.State.Running:
            if self.geo_anim.endValue() == target_geo:
                return
            self.geo_anim.stop()

        self.geo_anim = QPropertyAnimation(self, b"geometry")
        self.geo_anim.setDuration(400)
        self.geo_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.geo_anim.setEndValue(target_geo)
        self.geo_anim.start()

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
        if self.is_collapsed: self.expand_sidebar()
        
        # 1. 启动透明度动画
        target_opacity = 1.0 if target_mode == ViewMode.FULLSCREEN else 0.85
        self.opa_anim = QPropertyAnimation(self, b"windowOpacity")
        self.opa_anim.setDuration(400)
        self.opa_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self.opa_anim.setEndValue(target_opacity)
        self.opa_anim.start()

        # 2. 更新模式和UI状态 (这会触发 rebuild_content -> apply_geometry_animation)
        self.current_mode = target_mode
        self.update_ui_state(target_mode)

    def moveEvent(self, event):
        """移动窗口时记录 Y 坐标，用于跟随模式切换"""
        super().moveEvent(event)
        # 如果不是在执行动画，且没有折叠，记录 Y
        if not self.is_collapsed:
            is_geo_anim = hasattr(self, "geo_anim") and self.geo_anim.state() == QPropertyAnimation.State.Running
            is_exp_anim = hasattr(self, "exp_anim") and self.exp_anim.state() == QPropertyAnimation.State.Running
            if not is_geo_anim and not is_exp_anim:
                self.current_y = self.y()
                # 同时更新几何缓存，防止 rebuild 被旧值覆写
                if hasattr(self, "sidebar_geometry"):
                    self.sidebar_geometry.moveTop(self.current_y)
                if hasattr(self, "fullscreen_geometry"):
                    self.fullscreen_geometry.moveTop(self.current_y)

    def update_ui_state(self, mode: ViewMode, animate=True):
        """更新状态 (任务栏可见性、置顶、按钮、可见性)"""
        # 1. 透明度动画
        target_opacity = 1.0 if mode == ViewMode.FULLSCREEN else 0.85
        if animate:
            self.opa_anim = QPropertyAnimation(self, b"windowOpacity")
            self.opa_anim.setDuration(400)
            self.opa_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
            self.opa_anim.setEndValue(target_opacity)
            self.opa_anim.start()
        else:
            self.setWindowOpacity(target_opacity)

        # 2. 窗口 Flag 切换 (控制任务栏图标 / 置顶)
        # 侧边栏: Frameless + Tool (无任务栏图标) + StaysOnTop
        # 全屏: Frameless (有任务栏图标，可 Alt+Tab)
        if mode == ViewMode.SIDEBAR:
            # 针对 Linux 环境，增加一些 hint 尝试更强力地隐藏任务栏图标
            target_flags = (
                Qt.WindowType.FramelessWindowHint | 
                Qt.WindowType.WindowStaysOnTopHint | 
                Qt.WindowType.Tool
            )
        else:
            target_flags = Qt.WindowType.FramelessWindowHint
            
        if self.windowFlags() != target_flags:
            # 记录当前几何，因为修改 Flag 导致窗口重建，位置会重置
            old_geo = self.geometry()
            self.setWindowFlags(target_flags)
            self.setGeometry(old_geo) 
            self.show() # 重置 Flag 后必须重新显示

        if mode == ViewMode.SIDEBAR:
            self.custom_title_bar.show()
            self.custom_title_bar.title_label.show()
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
        
        self.rebuild_content(animate=animate)

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
        
        QTimer.singleShot(150, lambda: self.main_widget.hide() if self.is_collapsed else None)
        self.coll_anim.start()

    def expand_sidebar(self):
        if not self.is_collapsed: return
        self.is_collapsed = False
        
        self.exp_anim = QPropertyAnimation(self, b"geometry")
        self.exp_anim.setDuration(200)
        self.exp_anim.setEasingCurve(QEasingCurve.Type.OutQuad)
        self.exp_anim.setEndValue(self.sidebar_geometry)
        
        self.main_widget.show()
        self.exp_anim.start()

    # --- 拖拽系统实现 ---
    def start_task_drag(self, task, row_widget, offset):
        self.dragging_task = task
        self.drag_origin_row = row_widget
        self.drag_offset = offset
        self.setCursor(Qt.CursorShape.ClosedHandCursor)
        self.grabMouse()
        self.update()

    def mouseMoveEvent(self, event):
        if self.dragging_task:
            self.drag_ghost_pos = event.position().toPoint() - self.drag_offset
            self.update_drag_preview(event.position().toPoint())
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.dragging_task:
            self.releaseMouse()
            self.finalize_task_drag()
            self.setCursor(Qt.CursorShape.ArrowCursor)
        super().mouseReleaseEvent(event)

    def update_drag_preview(self, global_point):
        rel_pos = self.main_widget.mapFromGlobal(self.mapToGlobal(global_point))
        if self.backlog_view.geometry().contains(rel_pos):
            # 识别 backlog 中的具体日期列
            backlog_local_x = rel_pos.x() - self.backlog_view.x() - NAME_COL_WIDTH
            if backlog_local_x >= 0:
                col = -1
                for i, (off, w) in enumerate(zip(self.backlog_view.col_offsets, self.backlog_view.col_widths)):
                    if off <= backlog_local_x < off + w:
                        col = i
                        break
                if col != -1:
                    target_date = self.backlog_view.start_date + timedelta(days=col)
                    self.drag_target_info = ("BACKLOG", target_date)
                else:
                    self.drag_target_info = "BACKLOG" # 降级处理
            else:
                self.drag_target_info = "BACKLOG"
            return

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
        if isinstance(self.drag_target_info, tuple) and self.drag_target_info[0] == "BACKLOG":
            self.dragging_task.scheduled = False
            self.dragging_task.person = ""
            self.dragging_task.date = self.drag_target_info[1]
            self.rebuild_content()
        elif self.drag_target_info == "BACKLOG":
            self.dragging_task.scheduled = False
            self.dragging_task.person = ""
            self.rebuild_content()
        elif self.drag_target_info:
            target_p, target_d = self.drag_target_info
            
            self.dragging_task.person = target_p
            self.dragging_task.date = target_d
            self.dragging_task.scheduled = True
            self.dragging_task.status = TaskStatus.TODO
            
            # 清除划线进度
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
