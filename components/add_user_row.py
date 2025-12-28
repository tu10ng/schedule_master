from PyQt6.QtWidgets import QWidget, QLabel
from PyQt6.QtCore import Qt, pyqtSignal, QRect
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QCursor
from components.inline_editor import InlineEditor

from constants import CELL_HEIGHT, NAME_COL_WIDTH

class AddUserRow(QWidget):
    """编辑模式下显示在底部的添加行"""
    add_user_requested = pyqtSignal(str, str) # name, id

    def __init__(self, days=7, col_widths=[], history_users=[], parent=None):
        super().__init__(parent)
        self.days = days
        self.col_widths = col_widths
        self.history_users = history_users
        self.setFixedHeight(CELL_HEIGHT)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.editor = None
        self._ignore_click = False

    def update_params(self, days, col_widths, history_users=None):
        self.days = days
        self.col_widths = col_widths
        if history_users is not None:
             self.history_users = history_users
        self.setMinimumWidth(sum(col_widths) + NAME_COL_WIDTH)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 1. 绘制名字单元格 (虚线框)
        name_rect = QRect(0, 0, NAME_COL_WIDTH, CELL_HEIGHT)
        
        dash_pen = QPen(QColor("#666666"), 1, Qt.PenStyle.DashLine)
        painter.setPen(dash_pen)
        painter.setBrush(QColor("#252A32")) # 稍微淡一点的背景
        painter.drawRect(name_rect.adjusted(1, 1, -1, -1))
        
        # 文字 "+ 添加"
        painter.setPen(QColor("#888888"))
        painter.setFont(QFont("Microsoft YaHei", 12))
        painter.drawText(name_rect, Qt.AlignmentFlag.AlignCenter, "+ 添加人员")

        # 2. 绘制时间轴单元格 (虚线框)
        curr_x = NAME_COL_WIDTH
        for i in range(len(self.col_widths)):
            w = self.col_widths[i]
            cell_rect = QRect(curr_x, 0, w, CELL_HEIGHT)
            
            painter.setPen(dash_pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(cell_rect.adjusted(0, 1, -1, -1)) # 左边界重合
            
            curr_x += w

    def mousePressEvent(self, event):
        if self._ignore_click: return
        
        if self.editor: 
            self.editor.finalize()
            return
            
        # 仅在点击名字区域时触发添加? 或者整行都可以?
        # 用户逻辑: "这一行的人员名称就是添加人员" -> 暗示在名字区域输入
        self.start_editing()

    def start_editing(self):
        if self.editor: return
        
        # 在名字区域显示输入框
        w = NAME_COL_WIDTH - 20
        h = 30
        rect = QRect(10, (self.height() - h)//2, w, h)
        
        self.editor = InlineEditor(self, rect, self.on_input_finished, self.history_users)
        self.editor.setPlaceholderText("姓名 [工号]")
        self.editor.show()
        self.editor.setFocus()

    def on_input_finished(self, text):
        # 防抖: 短时间内忽略点击，防止 phantom click
        self._ignore_click = True
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(300, lambda: setattr(self, "_ignore_click", False))

        parts = text.split()
        if not parts: 
            self.editor = None # 停止链式添加
            return
        
        name = parts[0]
        emp_id = parts[1] if len(parts) > 1 else ""
        
        self.add_user_requested.emit(name, emp_id)
        self.editor = None
        
        # 链式添加: 成功添加后自动重新打开编辑器
        # 使用 Timer 避免在 rebuild_content 过程中操作 UI
        QTimer.singleShot(100, self.start_editing)
