import json
import os
from datetime import date, timedelta
from typing import List, Optional
from models import User, Task, TaskStatus

DATA_FILE = "data/schedule_data.json"

class DataManager:
    def __init__(self):
        self.users: List[User] = []
        self.tasks: List[Task] = []
        self.ensure_data_dir()

    def ensure_data_dir(self):
        if not os.path.exists("data"):
            os.makedirs("data")

    def load_data(self):
        if not os.path.exists(DATA_FILE):
            self.load_demo_data()
            self.save_data()
            return

        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.users = [User.from_dict(u) for u in data.get("users", [])]
                self.tasks = [Task.from_dict(t) for t in data.get("tasks", [])]
        except Exception as e:
            print(f"Error loading data: {e}")
            self.load_demo_data()

    def save_data(self):
        data = {
            "users": [u.to_dict() for u in self.users],
            "tasks": [t.to_dict() for t in self.tasks]
        }
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving data: {e}")

    def get_next_emp_id(self) -> str:
        # 简单查找最大整数 ID
        max_id = -1
        for u in self.users:
            if u.emp_id.isdigit():
                max_id = max(max_id, int(u.emp_id))
        return str(max_id + 1)

    def add_user(self, name: str, emp_id: Optional[str] = None) -> User:
        # 如果 ID 已存在且是 inactive，则恢复
        # 如果 ID 未指定，自动生成
        
        target_id = emp_id if emp_id else ""
        
        # 1. 尝试按 ID 查找
        if target_id:
            for u in self.users:
                if u.emp_id == target_id:
                    u.name = name # 更新名字
                    u.is_active = True
                    self.save_data()
                    return u
        
        # 2. 尝试按名字查找 (如果没指定ID)
        if not target_id:
            for u in self.users:
                if u.name == name:
                    u.is_active = True
                    self.save_data()
                    return u
            # 生成新 ID
            target_id = self.get_next_emp_id()

        # 3. 创建新用户
        new_user = User(emp_id=target_id, name=name, is_active=True)
        self.users.append(new_user)
        self.save_data()
        return new_user

    def soft_delete_user(self, emp_id: str):
        for u in self.users:
            if u.emp_id == emp_id:
                u.is_active = False
                break
        self.save_data()

    def load_demo_data(self):
        # 迁移旧的 demo 数据逻辑到这里
        self.users = [
            User("1001", "张三"),
            User("1002", "李四"),
            User("1003", "王五"),
            User("1004", "周七")
        ]
        
        today = date.today()
        # Monday
        t1 = Task("周期巡检", "张三", today, 9, 2, "#5E81AC", TaskStatus.TODO)
        t2 = Task("供氧维护", "张三", today, 11, 2, "#5E81AC", TaskStatus.TODO)
        t3 = Task("哈奇喂养", "李四", today, 14, 2, "#5E81AC", TaskStatus.TODO)
        
        # Tuesday
        t4 = Task("种植箱调试", "王五", today + timedelta(days=1), 10, 3, "#5E81AC", TaskStatus.BLOCKED)
        t5 = Task("液冷管道", "周七", today + timedelta(days=1), 15, 2, "#A3BE8C", TaskStatus.DONE) # 绿色
        
        # Unscheduled
        t_backlog_1 = Task("整理工具箱", "", today, scheduled=False, urgent=False)

        self.tasks = [t1, t2, t3, t4, t5, t_backlog_1]
