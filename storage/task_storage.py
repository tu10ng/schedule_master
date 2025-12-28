"""Local storage for tasks"""
import json
from pathlib import Path
from typing import List
from models.task import Task


class TaskStorage:
    """Handles task persistence to local JSON file"""
    
    def __init__(self, storage_dir: Path = None):
        if storage_dir is None:
            storage_dir = Path.home() / ".schedule-master"
        
        self.storage_dir = storage_dir
        self.storage_file = storage_dir / "tasks.json"
        
        # Create directory if it doesn't exist
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    def save_tasks(self, tasks: List[Task]) -> bool:
        """Save tasks to JSON file"""
        try:
            data = [task.to_dict() for task in tasks]
            with open(self.storage_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Failed to save tasks: {e}")
            return False
    
    def load_tasks(self) -> List[Task]:
        """Load tasks from JSON file"""
        if not self.storage_file.exists():
            return []
        
        try:
            with open(self.storage_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return [Task.from_dict(task_dict) for task_dict in data]
        except Exception as e:
            print(f"Failed to load tasks: {e}")
            return []
