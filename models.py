from enum import Enum
from dataclasses import dataclass
from datetime import date
import uuid

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
    scheduled: bool = True
    urgent: bool = True # 是否为紧急任务，影响渲染风格
    id: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:8]
