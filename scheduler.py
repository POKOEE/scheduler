import argparse
import json
import logging
import os
import shutil
import schedule
import time
from datetime import datetime



class Task:
    """Описывает одну задачу шедулера."""

    def __init__(self, task_id, operation, filename, destination=None,
                 content=None, line_num=None, schedule_time=None):
        self.task_id = task_id
        self.operation = operation
        self.filename = filename
        self.destination = destination
        self.content = content
        self.line_num = line_num
        self.schedule_time = schedule_time

    def to_dict(self):
        return {
            "task_id": self.task_id,
            "operation": self.operation,
            "filename": self.filename,
            "destination": self.destination,
            "content": self.content,
            "line_num": self.line_num,
            "schedule_time": self.schedule_time,
        }

    @staticmethod
    def from_dict(d):
        return Task(
            task_id=d["task_id"],
            operation=d["operation"],
            filename=d["filename"],
            destination=d.get("destination"),
            content=d.get("content"),
            line_num=d.get("line_num"),
            schedule_time=d.get("schedule_time"),
        )

    def __repr__(self):
        return (f"<Task id={self.task_id}, operation={self.operation}, "
                f"file={self.filename}, schedule={self.schedule_time}>")



class SimpleScheduler:
    """Управляет задачами, сохраняет их в tasks.json, выполняет по расписанию."""

    STORAGE_FILE = "tasks.json"

    def __init__(self):
        self.tasks = self._load_tasks()
        self.next_id = max([t.task_id for t in self.tasks], default=0) + 1

    # ── Загрузка задач из файла ──
    def _load_tasks(self):
        if not os.path.exists(self.STORAGE_FILE):
            return []
        try:
            with open(self.STORAGE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [Task.from_dict(d) for d in data]
        except (json.JSONDecodeError, OSError, KeyError):
            return []

    # ── Сохранение задач в файл ──
    def _save_tasks(self):
        with open(self.STORAGE_FILE, "w", encoding="utf-8") as f:
            json.dump([t.to_dict() for t in self.tasks],
                      f, ensure_ascii=False, indent=2)

    # ── Добавление задачи ──
    def add_task(self, operation, filename, destination=None,
                 content=None, line_num=None, schedule_time=None):
        task = Task(self.next_id, operation, filename, destination,
                    content, line_num, schedule_time)
        self.tasks.append(task)
        self.next_id += 1
        self._save_tasks()
        print(f"✅ Добавлена задача: {task}")

    # ── Удаление задачи ──
    def remove_task(self, task_id):
        before = len(self.tasks)
        self.tasks = [t for t in self.tasks if t.task_id != task_id]
        if len(self.tasks) < before:
            self._save_tasks()
            print(f"🗑️ Задача {task_id} удалена.")
        else:
            print(f"❌ Задача {task_id} не найдена.")

    # ── Выполнение задачи ──
    def run_task(self, task):
        try:
            if task.operation == "create":
                with open(task.filename, "w", encoding="utf-8") as f:
                    if task.content:
                        f.write(task.content)
                self.log_task(task, "Success")

            elif task.operation == "append":
                with open(task.filename, "a", encoding="utf-8") as f:
                    f.write((task.content or "") + "\n")
                self.log_task(task, "Success")

            elif task.operation == "delete_line":
                with open(task.filename, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                if task.line_num and 1 <= task.line_num <= len(lines):
                    del lines[task.line_num - 1]
                    with open(task.filename, "w", encoding="utf-8") as f:
                        f.writelines(lines)
                    self.log_task(task, "Success")
                else:
                    self.log_task(task, "Failed - Line number out of range")

            elif task.operation == "copy":
                shutil.copy2(task.filename, task.destination)
                self.log_task(task, "Success")

            elif task.operation == "move":
                shutil.move(task.filename, task.destination)
                self.log_task(task, "Success")

            elif task.operation == "delete":
                os.remove(task.filename)
                self.log_task(task, "Success")

            elif task.operation == "archive":
                archive_name = task.destination or (task.filename + ".zip")
                shutil.make_archive(archive_name.replace(".zip", ""),
                                    "zip", task.filename)
                self.log_task(task, "Success")

            else:
                self.log_task(task, f"Failed - Unknown operation: {task.operation}")

        except Exception as e:
            self.log_task(task, f"Failed - {str(e)}")

    # ── Логирование ──
    def log_task(self, task, status):
        logging.info(
            f"Task ID {task.task_id}: {task.operation} on {task.filename} "
            f"- Status: {status}"
        )
        print(f"[{datetime.now():%H:%M:%S}] Задача {task.task_id} "
              f"({task.operation}) — {status}")

    # ── Планирование задачи по расписанию ──
    def _schedule_task(self, task):
        if not task.schedule_time:
            return
        parts = task.schedule_time.split(":")

        if parts[0] == "daily" and len(parts) == 3:
            schedule.every().day.at(f"{parts[1]}:{parts[2]}").do(
                self.run_task, task)

        elif parts[0] == "weekly" and len(parts) == 4:
            day = parts[1].lower()
            time_str = f"{parts[2]}:{parts[3]}"
            getattr(schedule.every(), day).at(time_str).do(
                self.run_task, task)

        elif parts[0] == "hourly":
            schedule.every().hour.do(self.run_task, task)

        else:
            print(f"⚠️ Неизвестный формат расписания: {task.schedule_time}")

    # ── Запуск шедулера ──
    def start(self):
        # Перепланировать все сохранённые задачи
        schedule.clear()
        for task in self.tasks:
            if task.schedule_time:
                self._schedule_task(task)

        if not self.tasks:
            print("📭 Нет сохранённых задач. Сначала добавьте через 'add'.")
            return

        print(f"🚀 Шедулер запущен ({len(self.tasks)} задач). "
              f"Нажмите Ctrl+C для остановки.\n")
        try:
            while True:
                schedule.run_pending()
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Шедулер остановлен.")

    # ── Немедленный запуск задачи по ID ──
    def run_now(self, task_id):
        for t in self.tasks:
            if t.task_id == task_id:
                print(f"▶️ Выполняю задачу {task_id} сейчас...")
                self.run_task(t)
                return
        print(f"❌ Задача {task_id} не найдена.")

    # ── Просмотр задач ──
    def view_tasks(self):
        if not self.tasks:
            print("📭 Задач нет.")
            return
        print("📋 Запланированные задачи:")
        for t in self.tasks:
            print(" ", t)



def main():
    logging.basicConfig(
        filename="simple_scheduler.log",
        level=logging.INFO,
        format="%(asctime)s - %(message)s",
        encoding="utf-8"
    )

    scheduler = SimpleScheduler()

    parser = argparse.ArgumentParser(
        description="Файловый шедулер — планирование операций с файлами"
    )
    parser.add_argument("command",
                        choices=["add", "view", "start", "remove", "run_now"],
                        help="Команда: add / view / start / remove / run_now")
    parser.add_argument("--operation",
                        choices=["create", "append", "delete_line",
                                 "copy", "move", "delete", "archive"],
                        help="Тип операции")
    parser.add_argument("--filename", help="Имя файла")
    parser.add_argument("--destination",
                        help="Куда копировать / перемещать / архивировать")
    parser.add_argument("--content", help="Текст для записи")
    parser.add_argument("--line_num", type=int,
                        help="Номер строки для удаления")
    parser.add_argument("--schedule",
                        help="Расписание: daily:10:00 или weekly:mon:12:00")
    parser.add_argument("--task_id", type=int,
                        help="ID задачи (для remove / run_now)")

    args = parser.parse_args()

    if args.command == "add":
        if not (args.operation and args.filename):
            print("❌ Укажите --operation и --filename")
            return
        scheduler.add_task(
            operation=args.operation,
            filename=args.filename,
            destination=args.destination,
            content=args.content,
            line_num=args.line_num,
            schedule_time=args.schedule
        )

    elif args.command == "view":
        scheduler.view_tasks()

    elif args.command == "remove":
        if args.task_id is None:
            print("❌ Укажите --task_id")
            return
        scheduler.remove_task(args.task_id)

    elif args.command == "run_now":
        if args.task_id is None:
            print("❌ Укажите --task_id")
            return
        scheduler.run_now(args.task_id)

    elif args.command == "start":
        scheduler.start()


if __name__ == "__main__":
    main()
