import os


__all__ = ['get_work_directory', 'format_task_info']


def get_work_directory(base_directory: str, task_id: str):
    return os.path.join(base_directory, task_id)


def format_task_info(task_info):
    return task_info
