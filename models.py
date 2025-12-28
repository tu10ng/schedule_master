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
class User:
    emp_id: str
    name: str
    is_active: bool = True
    avatar: str = "" # 预留字段

    def to_dict(self):
        return {
            "emp_id": self.emp_id,
            "name": self.name,
            "is_active": self.is_active,
            "avatar": self.avatar
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            emp_id=str(data.get("emp_id", "")),
            name=data.get("name", ""),
            is_active=data.get("is_active", True),
            avatar=data.get("avatar", "")
        )

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

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "person": self.person,
            "date": self.date.isoformat(),
            "start_hour": self.start_hour,
            "duration": self.duration,
            "color": self.color,
            "status": self.status.name,
            "scheduled": self.scheduled,
            "urgent": self.urgent
        }

    @classmethod
    def from_dict(cls, data):
        # 处理日期转换
        d = date.fromisoformat(data["date"]) if isinstance(data["date"], str) else data["date"]
        # 处理枚举
        status = TaskStatus[data["status"]] if "status" in data else TaskStatus.TODO
        
        return cls(
            id=data.get("id", ""),
            title=data.get("title", ""),
            person=data.get("person", ""),
            date=d,
            start_hour=data.get("start_hour", 9),
            duration=data.get("duration", 2),
            color=data.get("color", "#2E3440"),
            status=status,
            scheduled=data.get("scheduled", True),
            urgent=data.get("urgent", True)
        )
