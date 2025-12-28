from PyQt6.QtWidgets import QLineEdit, QCompleter
from PyQt6.QtCore import Qt

class InlineEditor(QLineEdit):
    def __init__(self, parent, rect, callback, suggestions=None):
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
        
        if suggestions:
            completer = QCompleter(suggestions, self)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            self.setCompleter(completer)

        self.setFocus()
        self.returnPressed.connect(self.finalize)
        
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Escape:
            self.finalized = True
            self.deleteLater()
        else:
            super().keyPressEvent(event)
    def finalize(self):
        if self.finalized: return
        self.finalized = True
        
        # 即使为空也回调，以便父级清理引用
        self.callback(self.text().strip())
            
        self.deleteLater()

    def focusOutEvent(self, event):
        # 失去焦点时自动提交，实现“无感”转化
        self.finalize()
        super().focusOutEvent(event)
