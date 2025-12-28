"""Task data model with network sync support"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any
import uuid


@dataclass
class Task:
    """Single task with unique ID and timestamps for sync"""
    content: str
    completed: bool = False
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())
    updated_at: float = field(default_factory=lambda: datetime.now().timestamp())
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to JSON-compatible dict"""
        return {
            'id': self.id,
            'content': self.content,
            'completed': self.completed,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Task':
        """Deserialize from dict"""
        return cls(
            id=data['id'],
            content=data['content'],
            completed=data['completed'],
            created_at=data['created_at'],
            updated_at=data['updated_at']
        )
    
    def update(self, content: str = None, completed: bool = None):
        """Update task and refresh timestamp"""
        if content is not None:
            self.content = content
        if completed is not None:
            self.completed = completed
        self.updated_at = datetime.now().timestamp()
