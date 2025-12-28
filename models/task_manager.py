"""Task manager with event signals for network sync"""
from typing import List, Optional
from PyQt6.QtCore import QObject, pyqtSignal
from models.task import Task


class TaskManager(QObject):
    """Manages tasks with signals for UI and network sync"""
    
    # Signals for observers (UI + future network module)
    task_added = pyqtSignal(Task)
    task_updated = pyqtSignal(Task)
    task_deleted = pyqtSignal(str)  # task_id
    tasks_loaded = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.tasks: List[Task] = []
    
    def add_task(self, content: str = "") -> Task:
        """Add new task and emit signal"""
        task = Task(content=content)
        self.tasks.append(task)
        self.task_added.emit(task)
        return task
    
    def update_task(self, task_id: str, content: str = None, completed: bool = None) -> bool:
        """Update existing task"""
        task = self.get_task(task_id)
        if task:
            task.update(content=content, completed=completed)
            self.task_updated.emit(task)
            return True
        return False
    
    def delete_task(self, task_id: str) -> bool:
        """Delete task by ID"""
        task = self.get_task(task_id)
        if task:
            self.tasks.remove(task)
            self.task_deleted.emit(task_id)
            return True
        return False
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get task by ID"""
        for task in self.tasks:
            if task.id == task_id:
                return task
        return None
    
    def get_all_tasks(self) -> List[Task]:
        """Get all tasks sorted by creation time"""
        return sorted(self.tasks, key=lambda t: t.created_at)
    
    def merge_remote_task(self, task_dict: dict) -> bool:
        """
        Merge task from network (future use)
        Uses last-write-wins conflict resolution
        """
        remote_task = Task.from_dict(task_dict)
        local_task = self.get_task(remote_task.id)
        
        if local_task:
            # Conflict resolution: newer timestamp wins
            if remote_task.updated_at > local_task.updated_at:
                local_task.content = remote_task.content
                local_task.completed = remote_task.completed
                local_task.updated_at = remote_task.updated_at
                self.task_updated.emit(local_task)
                return True
        else:
            # New task from remote
            self.tasks.append(remote_task)
            self.task_added.emit(remote_task)
            return True
        
        return False
    
    def to_dict_list(self) -> List[dict]:
        """Serialize all tasks"""
        return [task.to_dict() for task in self.tasks]
    
    def load_from_dict_list(self, task_list: List[dict]):
        """Load tasks from dict list"""
        self.tasks = [Task.from_dict(data) for data in task_list]
        self.tasks_loaded.emit()
