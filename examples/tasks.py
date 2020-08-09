import time
import logging
from restcelery import RestCelery, get_task_logger
from celery.signals import after_task_publish
from celery import current_app


logger = get_task_logger(__name__)
logger.setLevel(logging.INFO)


@RestCelery.task(__name__)
def add_number(task, a: int, b: int, k: int = 1) -> int:
    """
    k-th order add number
    y = a**k + b**k
    """
    workdir = task.work_directory
    for i in range(20):
        msg = f'running [{i}/20]'
        task.record(msg, state='PROGRESS', log=True)
        task.logger.info('[progress] ' + msg)
        time.sleep(1)
    return a**k + b**k


@RestCelery.task(__name__)
def k_mean(task, num_list: list, k: int = 1) -> float:
    return sum([x**k for x in num_list]) / len(num_list)
