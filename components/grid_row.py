from typing import List, Dict
from datetime import date, timedelta
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QRect, QPoint, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QFontMetrics
from PyQt6.QtMultimedia import QSoundEffect

from models import Task, TaskStatus
from constants import CELL_HEIGHT, NAME_COL_WIDTH
from components.inline_editor import InlineEditor

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

        # 编辑模式状态
        self.is_edit_mode = False
        self._shake_offset = 0
        self.shake_anim = None
        
        # 删除按钮区域缓存
        self.delete_btn_rect = QRect()

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

    def _get_shake(self): return self._shake_offset
    def _set_shake(self, val): 
        self._shake_offset = val
        self.update()
    shake_offset = pyqtProperty(float, _get_shake, _set_shake)

    def set_edit_mode(self, active: bool):
        self.is_edit_mode = active
        if active:
            # 开启抖动动画
            self.shake_anim = QPropertyAnimation(self, b"shake_offset")
            self.shake_anim.setDuration(200)
            self.shake_anim.setLoopCount(-1) # 无限循环
            self.shake_anim.setStartValue(-2.0)
            self.shake_anim.setEndValue(2.0)
            self.shake_anim.setEasingCurve(QEasingCurve.Type.SineCurve) # 模拟抖动
            
            # 使用 KeyValueAt 来精确控制摇晃节奏 (Qt 6.0+)
            # 简单起见，使用 SineCurve + 往复运动
            self.shake_anim.setKeyValueAt(0, 0)
            self.shake_anim.setKeyValueAt(0.25, -2)
            self.shake_anim.setKeyValueAt(0.75, 2)
            self.shake_anim.setKeyValueAt(1, 0)
            
            self.shake_anim.start()
        else:
            if self.shake_anim: 
                self.shake_anim.stop()
                self._shake_offset = 0
        self.update()

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
        # 1. 绘制名字单元格
        name_rect = QRect(0, 0, NAME_COL_WIDTH, CELL_HEIGHT)
        painter.fillRect(name_rect, QColor("#2A3039"))
        painter.setPen(QPen(QColor("#3A4049"), 2))
        painter.drawRect(name_rect)
        
        # 名字绘制 (带抖动)
        text_x_offset = self._shake_offset if self.is_edit_mode else 0
        name_text_rect = name_rect.adjusted(5 + int(text_x_offset), 0, -5 + int(text_x_offset), 0)
        
        painter.setPen(QColor("#FFFFFF"))
        painter.setFont(QFont("Microsoft YaHei", 10, QFont.Weight.Bold))
        painter.drawText(name_text_rect, Qt.AlignmentFlag.AlignCenter, self.person_name)
        
        # 编辑模式：绘制删除按钮
        if self.is_edit_mode:
            del_size = 20
            self.delete_btn_rect = QRect(
                name_rect.right() - del_size - 5, 
                name_rect.center().y() - del_size // 2,
                del_size, del_size
            )
            
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor("#BF616A"))
            painter.drawEllipse(self.delete_btn_rect)
            
            painter.setPen(QPen(QColor("white"), 2))
            # 画叉
            r = self.delete_btn_rect
            painter.drawLine(r.center().x() - 4, r.center().y() - 4, r.center().x() + 4, r.center().y() + 4)
            painter.drawLine(r.center().x() + 4, r.center().y() - 4, r.center().x() - 4, r.center().y() + 4)
        else:
            self.delete_btn_rect = QRect() # 清空区域避免误触
        
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
        
        # 优先处理删除按钮点击
        if self.is_edit_mode and self.delete_btn_rect.contains(event.position().toPoint()):
            main_window = self.window()
            if hasattr(main_window, "delete_user"):
                main_window.delete_user(self.person_name) # 这里最好传 ID，暂传名字
            return

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
                        
                        # 保存变更
                        main_window = self.window()
                        if hasattr(main_window, "save_data"):
                            main_window.save_data()
                            
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
            if not title or not title.strip(): return
            new_task = Task(title=title, person=self.person_name, date=target_date)
            main_window = self.window()
            if hasattr(main_window, "add_task"):
                main_window.add_task(new_task)
            else:
                print("[ERROR] main_window does not have add_task!")

        if hasattr(self, "editor") and self.editor:
            self.editor.finalize()
            
        self.editor = InlineEditor(self, rect_editor, create_task)
        self.editor.show()
        self.editor.setFocus()
        
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
            
            # 1. 背景
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            bg_color = QColor(task.color) if task.urgent else QColor("#323844")
            painter.fillRect(task_rect, bg_color)
            
            # 2. 绘制右侧状态开关 (待办 | 阻塞 | 完成) - 使用小字体
            sw_w = 80
            sw_rect = QRect(task_rect.right() - sw_w, y, sw_w, block_h)
            
            # 非紧急任务移除 Bold
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
                seg_rect = QRect(sw_rect.x() + i * seg_w, sw_rect.y(), seg_w, block_h)
                if task.status == status:
                    # 激活态：有色背景 + 白色文字
                    painter.fillRect(seg_rect, QColor(color))
                    painter.setPen(QColor("#FFFFFF"))
                else:
                    # 未激活：深灰色背景 + 灰度文字
                    painter.fillRect(seg_rect, QColor("#3A4049"))
                    painter.setPen(QColor("#888888") if task.urgent else QColor("#666666"))
                
                painter.drawText(seg_rect, Qt.AlignmentFlag.AlignCenter, label)
                # 分隔线
                if i < 2:
                    painter.setPen(QPen(QColor("#1F2329"), 1))
                    painter.drawLine(seg_rect.right(), seg_rect.top(), seg_rect.right(), seg_rect.bottom())

            # 3. 边框
            painter.setPen(QPen(QColor("#3A4049"), 2)) # 加深边框感
            painter.drawRect(task_rect)
            
            # 4. 任务标题文字
            text_color = QColor("#FFFFFF") if task.urgent else QColor("#999999")
            painter.setPen(text_color)
            
            title_font = QFont("Microsoft YaHei", 12)
            if task.urgent: title_font.setWeight(QFont.Weight.Bold)
            painter.setFont(title_font)
            
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
