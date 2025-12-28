from datetime import date, timedelta
from typing import List
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QPainter, QColor, QPen, QFont

from models import ViewMode
from constants import NAME_COL_WIDTH

class ModeHeader(QWidget):
    def __init__(self, start_date: date, days: int, col_widths: List[int], mode: ViewMode, parent=None):
        super().__init__(parent)
        self.start_date, self.days, self.mode = start_date, days, mode
        self.col_widths = col_widths
        self.setFixedHeight(40)
        total_w = sum(col_widths) + NAME_COL_WIDTH
        self.setFixedWidth(total_w)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#2A3039"))
        
        # 名字部分
        painter.setPen(QPen(QColor("#3A4049"), 1))
        painter.drawRect(0, 0, NAME_COL_WIDTH, 40)
        
        # 列位置计算
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
