import os
import logging
from celery.app.task import Task as BaseTask
from celery.utils.log import get_task_logger


def get_celery_task(base_directory: str, formatter: str, session):

    class CustomTask(BaseTask):

        _base_directory = base_directory
        _base_logger_name = ''
        _fileformatter = formatter
        session = session

        def record(_self, msg: str, state='PROGRESS', log=True):
            if log:
                _self.logger.info(msg)
            return super(CustomTask, _self).update_state(state=state, meta={'message': msg})

        @property
        def work_directory(_self):
            print(_self._base_directory, _self.request.id)
            return os.path.join(_self._base_directory, _self.request.id)

        @property
        def logger(_self):
            _logger = get_task_logger('.'.join([
                _self._base_logger_name,
                _self.__name__,
                _self.request.id
                ]))
            fhs = [h for h in _logger.handlers if isinstance(h, logging.FileHandler)]
            if len(fhs) == 0:
                wd = _self.work_directory
                log_path = os.path.join(wd, 'auto.log')
                fh = logging.FileHandler(log_path)
                fh.setFormatter(_self._fileformatter)
                _logger.addHandler(fh)
            return _logger

    return CustomTask
