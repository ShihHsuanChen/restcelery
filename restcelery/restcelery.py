import os
import re
import shutil
import logging
import traceback
from typing import List
from functools import wraps

from flask import Flask
from flask_cors import CORS
from flask_migrate import Migrate
from flask_restful_swagger_2 import Api

from celery import Celery
from celery import signals
from celery import current_app
from celery import Task as CeleryTask
from celery.bin import worker

from .restful import create_restful
from .prestate import db, create_connection
from .prestate import TaskPrestate
from .prestate import get_prestate
from .prestate import create_task
from .prestate import delete_task
from .custom_task import get_celery_task


__all__ = ['RestCelery']


def from_object(obj):
    if isinstance(obj, type):

        class ConfigClass(obj):

            def __init__(self):
                pass

            def __getitem__(self, key):
                return getattr(self, key)

            def __setitem__(self, key, value):
                setattr(self, key, value)
                
        config_obj = ConfigClass()
    elif hasattr('__setitem__'):
        config_obj = obj
    else:
        class ConfigClass:

            def __init__(self):
                self.obj = obj

            def __getitem__(self, key):
                return getattr(self.obj, key)

            def __setitem__(self, key, value):
                setattr(self.obj, key, value)
                
        config_obj = ConfigClass()
    config_obj['SQLALCHEMY_DATABASE_URI'] = config_obj['PRE_STATE_DB']
    return config_obj


class RestCelery:
    _task_map = dict()

    def __init__(self, config, task_modules: List[str]):
        config = from_object(config)

        self.broker_url = config['CELERY_BROKER_URL']
        m = re.match(r'((^py)|(^.*\+)|(^))(.+):\/\/', self.broker_url)
        self.broker_type = m.group(5)
        """
        broker_type:
            redis, sqlite, rabbitmq, ...
        """

        app = Flask(__name__)
        app.config.from_object(config)
        db.init_app(app)
        db.create_all(app=app)
        self.db = db
        self.migrate = Migrate(app=app, db=db)
        self.api = Api()
        CORS(app)

        wdir = os.path.abspath(config['TASK_WORKDIR'])

        if not os.path.exists(wdir) or not os.path.isdir(wdir):
            os.makedirs(wdir)
        self.base_directory = wdir

        formatter = logging.Formatter(config['TASK_FILE_FORMAT'] or '%(message)s')
        self.session = create_connection(config['PRE_STATE_DB'])
        custom_task_cls = get_celery_task(wdir, formatter, self.session)

        celery = Celery(
            backend=config['CELERY_RESULT_BACKEND'],
            broker=config['CELERY_BROKER_URL'],
            config_source=config,
            task_cls=custom_task_cls
        )

        class ContextTask(CeleryTask):

            def __call__(_self, *args, **kwargs):
                with app.app_context():
                    return _self.run(*args, **kwargs)

        celery.Task = ContextTask
        self.celery = celery

        self.app = app
        self.register(task_modules)
        self.api.init_app(app)
        self.worker = worker.worker(app=self.celery)

    @classmethod
    def task(cls, module_name=''):
        def wrapper(func):

            @wraps(func)
            def decorator(_self, *args, **kwargs):
                _self._base_logger_name = module_name
                try:
                    res = func(_self, *args, **kwargs)
                except Exception as e:
                    _self.logger.error(str(e), exc_info=traceback.format_exc())
                    raise
                return res

            qualname = '.'.join([module_name, decorator.__qualname__])
            cls._task_map[qualname] = decorator
            return decorator
        return wrapper

    def register(self, module_names):
        for m in module_names:
            __import__(m)
        for name, func in self._task_map.items():
            self.celery.task(name=name, bind=True)(func)
        create_restful(
                self.api,
                self.celery,
                self._task_map,
                self.base_directory,
                self.broker_type
                )


@signals.before_task_publish.connect
def on_before_task_publish(sender=None, body=None, exchange=None, routing_key=None, headers=None, properties=None, declare=None, retry_policy=None, **_kwargs):
    # sender=task_name
    print('on_before_task_publish')
    print(body)
    print(exchange)
    print(routing_key)
    print(headers)
    print(properties)
    print(declare)
    print(retry_policy)


@signals.after_task_publish.connect
def on_after_task_publish(sender=None, body=None, exchange=None, routing_key=None, **_kwargs):
    # sender=task_name
    print('on_after_task_publish')
    # the task may not exist if sent using `send_task` which
    # sends tasks by name, so fall back to the default result backend
    # if that is the case.
    task_id = body['id']
    create_task(db.session, task_id)


@signals.worker_process_init.connect
def on_worker_process_init(sender=None, **_kwargs):
    # sender=None
    # establish connction to prestatedb
    print(sender)
    print('on_worker_process_init')


@signals.worker_init.connect
def on_worker_init(sender=None, **_kwargs):
    # sender=WorkController
    print('on_worker_init')


@signals.worker_ready.connect
def on_worker_ready(sender=None, **_kwargs):
    # sender=consumer
    print('on_worker_ready')


@signals.task_received.connect
def on_task_receive(sender=None, request=None, **_kwargs):
    # sender=consumer
    print('on_task_receive')


@signals.task_prerun.connect
def on_task_prerun(sender=None, task_id=None, task=None, args=None, kwargs=None, **_kwargs):
    # sender=task
    print(type(sender))
    print(type(task))
    print('on_task_prerun')

    # create work directory
    workdir = sender.work_directory
    if not os.path.exists(workdir) or not os.path.isdir(workdir):
        os.makedirs(workdir)

    # check prestate
    task_id = sender.request.id
    task_result = current_app.AsyncResult(task_id)
    prestate = get_prestate(sender._session, task_id)

    # revoke canceled task
    if prestate == TaskPrestate.CANCELED:
        print('cancel')
        wdir = sender.work_directory
        if os.path.isdir(wdir):
            shutil.rmtree(wdir)
        task_result.revoke(terminate=True, signal='SIGKILL')


@signals.task_postrun.connect
def on_task_postrun(sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, state=None, **_kwargs):
    # sender=task
    print('on_task_postrun')


@signals.task_revoked.connect
def on_task_revoked(sender=None, request=None, terminated=None, signum=None, expired=None, **_kwargs):
    # sender=task
    # this signal was emitted only when task.revoke(terminate=True)
    # and only broker of amqp and redis support this function
    print('on_task_revoked')
    # cannot get work_directory from request
    task_id = request.id
    delete_task(sender._session, task_id)


@signals.task_unknown.connect
def on_task_unknown(sender=None, message=None, exc=None, name=None, id=None, **_kwargs):
    # sender=consumer
    print('on_task_unknown')


@signals.task_success.connect
def on_task_success(sender=None, result=None, **_kwargs):
    # sender=task
    # pack contents in work_directory
    print('on_task_success')


@signals.task_retry.connect
def on_task_retry(sender=None, request=None, reason=None, einfo=None, **_kwargs):
    # sender=task
    print('on_task_retry')


@signals.task_failure.connect
def on_task_failure(sender=None, task_id=None, exception=None, args=None, kwargs=None, traceback=None, einfo=None, **_kwargs):
    # sender=task
    print('on_task_failure')


@signals.task_rejected.connect
def on_task_rejected(sender=None, message=None, exc=None, **_kwargs):
    # sender=consumer
    print('on_task_rejected')


@signals.worker_shutting_down.connect
def on_worker_shutting_down(sender=None, sig=None, how=None, exitcode=None, **_kwargs):
    # sender=worker.hostname
    print('on_worker_shutting_down')


@signals.worker_process_shutdown.connect
def on_worker_process_shutdown(sender=None, pid=None, exitcode=None, **_kwargs):
    # sender=None
    # disconnect to prestatedb
    print('on_worker_process_shutdown')


@signals.worker_shutdown.connect
def on_worker_shutdown(sender=None, **_kwargs):
    # sender=WorkController
    print('on_worker_shutdown')
