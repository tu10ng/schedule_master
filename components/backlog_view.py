from typing import List, Dict
from datetime import date, timedelta
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QRect, QPoint
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QFontMetrics
from components.inline_editor import InlineEditor

from models import Task, TaskStatus
from constants import NAME_COL_WIDTH, CELL_HEIGHT

class BacklogView(QWidget):
    def __init__(self, tasks: List[Task], parent=None):
        super().__init__(parent)
        self.tasks = tasks
        self.start_date = date.today()
        self.days = 1
        self.col_widths = [100]
        self.col_offsets = [0]
        self.date_map = {}
        
        self.setMinimumHeight(150)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setStyleSheet("BacklogView { background-color: #1F2329; border-top: 2px solid #3A4049; }")
        
    def update_params(self, start_date: date, days: int, col_widths: List[int], tasks: List[Task]):
        self.start_date = start_date
        self.days = days
        self.col_widths = col_widths
        self.tasks = tasks
        
        # 计算偏移
        self.col_offsets = [0] * len(col_widths)
        curr = 0
        for i in range(len(col_widths)):
            self.col_offsets[i] = curr
            curr += col_widths[i]
            
        # 重构日期映射
        self.date_map = {}
        for t in self.tasks:
            d = t.date
            if d not in self.date_map: self.date_map[d] = []
            self.date_map[d].append(t)
            
        # 动态调整高度：找到任务最多的那一列
        max_tasks = 0
        for d in self.date_map:
            max_tasks = max(max_tasks, len(self.date_map[d]))
        
        # 顶部留白 + 任务高度 + 底部留白
        h = max(150, max_tasks * 36 + 40)
        self.setFixedHeight(h)
        self.setFixedWidth(sum(col_widths) + NAME_COL_WIDTH)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 1. 绘制左侧行表头 "不紧急"
        row_header_rect = QRect(0, 0, NAME_COL_WIDTH, self.height())
        painter.fillRect(row_header_rect, QColor("#2A3039"))
        painter.setPen(QPen(QColor("#3A4049"), 2))
        painter.drawRect(row_header_rect)
        
        painter.setPen(QColor("#FFFFFF"))
        painter.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        painter.drawText(row_header_rect, Qt.AlignmentFlag.AlignCenter, "不紧急")

        # 2. 绘制 7 列网格线
        grid_pen = QPen(QColor("#3A4049"), 1)
        for i in range(self.days):
            cell_x = self.col_offsets[i] + NAME_COL_WIDTH
            cell_width = self.col_widths[i]
            cell_rect = QRect(cell_x, 0, cell_width, self.height())
            
            painter.setPen(grid_pen)
            painter.drawRect(cell_rect)
            
            # 绘制该列的任务
            current_date = self.start_date + timedelta(days=i)
            if current_date in self.date_map:
                self.draw_tasks_in_column(painter, cell_rect, self.date_map[current_date])

    def draw_tasks_in_column(self, painter: QPainter, rect: QRect, tasks: List[Task]):
        y_offset = 10
        row_h = 32
        spacing = 4
        
        for task in tasks:
            task_rect = QRect(rect.x() + 4, y_offset, rect.width() - 8, row_h)
            
            # 背景
            bg_color = QColor(task.color) if task.urgent else QColor("#323844")
            painter.fillRect(task_rect, bg_color)
            painter.setPen(QPen(QColor("#3A4049"), 1))
            painter.drawRect(task_rect)
            
            # 状态开关
            sw_w = 80
            sw_rect = QRect(task_rect.right() - sw_w, task_rect.y(), sw_w, row_h)
            
            sw_font = QFont("Microsoft YaHei", 7)
            if task.urgent: sw_font.setWeight(QFont.Weight.Bold)
            painter.setFont(sw_font)
            
            segments = [
                (TaskStatus.TODO, "待办", "#5B859E"),
                (TaskStatus.BLOCKED, "阻塞", "#E3A857"),
                (TaskStatus.DONE, "完成", "#7FAE8A")
            ]
            
            seg_w = sw_w // 3
            for i, (status, label, color) in enumerate(segments):
                seg_rect = QRect(sw_rect.x() + i * seg_w, sw_rect.y(), seg_w, row_h)
                if task.status == status:
                    painter.fillRect(seg_rect, QColor(color))
                    painter.setPen(QColor("#FFFFFF"))
                else:
                    painter.fillRect(seg_rect, QColor("#2E3440"))
                    painter.setPen(QColor("#888888") if task.urgent else QColor("#666666"))
                
                painter.drawText(seg_rect, Qt.AlignmentFlag.AlignCenter, label)
                if i < 2:
                    painter.setPen(QPen(QColor("#1F2329"), 1))
                    painter.drawLine(seg_rect.right(), seg_rect.top(), seg_rect.right(), seg_rect.bottom())

            # 标题：静音灰色，常规字体
            text_color = QColor("#FFFFFF") if task.urgent else QColor("#999999")
            painter.setPen(text_color)
            
            title_font = QFont("Microsoft YaHei", 10)
            if task.urgent: title_font.setWeight(QFont.Weight.Bold)
            painter.setFont(title_font)
            
            text_rect = task_rect.adjusted(10, 0, -sw_w - 10, 0)
            metrics = painter.fontMetrics()
            elided_text = metrics.elidedText(task.title, Qt.TextElideMode.ElideRight, text_rect.width())
            painter.drawText(text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, elided_text)
            
            y_offset += row_h + spacing

    def mousePressEvent(self, event):
        x = event.position().x()
        if x < NAME_COL_WIDTH: return
        
        # 识别列
        rel_x = x - NAME_COL_WIDTH
        col = -1
        for i, (off, w) in enumerate(zip(self.col_offsets, self.col_widths)):
            if off <= rel_x < off + w:
                col = i
                break
        if col == -1: return
        
        target_date = self.start_date + timedelta(days=col)
        
        # 检测是否点击在任务上
        if target_date in self.date_map:
            y_offset = 10
            row_h = 32
            spacing = 4
            tasks = self.date_map[target_date]
            
            for task in tasks:
                task_rect = QRect(self.col_offsets[col] + NAME_COL_WIDTH + 4, y_offset, self.col_widths[col] - 8, row_h)
                if task_rect.contains(event.position().toPoint()):
                    # 状态切换
                    sw_w = 80
                    sw_rect = QRect(task_rect.right() - sw_w, task_rect.y(), sw_w, row_h)
                    if sw_rect.contains(event.position().toPoint()):
                        local_x = event.position().x() - sw_rect.x()
                        seg_w = sw_w / 3
                        if local_x < seg_w: task.status = TaskStatus.TODO
                        elif local_x < seg_w * 2: task.status = TaskStatus.BLOCKED
                        else: task.status = TaskStatus.DONE
                        self.update()
                        return
                    
                    # 开始拖拽
                    main_window = self.window()
                    if hasattr(main_window, "start_task_drag"):
                        offset = event.position().toPoint() - task_rect.topLeft()
                        main_window.start_task_drag(task, self, offset)
                        return
                y_offset += row_h + spacing

        # 创建任务
        click_y = event.position().y()
        row_h = 32
        rect_editor = QRect(self.col_offsets[col] + NAME_COL_WIDTH + 4, int(click_y - row_h/2), self.col_widths[col] - 8, row_h)
        
        def create_task(title):
            # 创建时设为 unscheduled，且 urgent=False
            new_task = Task(title=title, person="", date=target_date, scheduled=False, urgent=False)
            main_window = self.window()
            if hasattr(main_window, "add_task"):
                main_window.add_task(new_task)

        if hasattr(self, "editor") and self.editor:
            self.editor.finalize()
            
        self.editor = InlineEditor(self, rect_editor, create_task)
        self.editor.show()
        self.editor.setFocus()
        
        super().mousePressEvent(event)
