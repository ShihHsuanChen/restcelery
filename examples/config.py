import os
import logging


pwd = os.path.dirname(__file__)


class Config:

    SECRET_KEY = os.environ.get('SECRET_KEY')
    SESSION_PROTECTION = 'strong'
    STATIC_DIR = os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))) + '/static'

    # celery config
    CELERY_ACCEPT_CONTENT = ['json']
    CELERY_TASK_SERIALIZER = 'json'
    CELERY_RESULT_SERIALIZER = 'json'
    # CELERY_BROKER_URL = 'amqp://root:1234@127.0.0.1:5672/myhost'
    #  CELERY_BROKER_URL = 'redis://127.0.0.1:6379/0'
    CELERY_BROKER_URL = 'sqla+sqlite:///celery.db'
    # CELERY_RESULT_BACKEND = 'rpc://'
    CELERY_RESULT_BACKEND = 'db+sqlite:///celery_result.db'
    # CELERY_STATE_DB = './data/worker.state'
    CELERY_SEND_SENT_EVENT = True
    CELERYD_PREFETCH_MULTIPLIER = 1 # number of tasks per-fork-workers being pre-feteched in the main process

    TASK_WORKDIR = './data/'
    TASK_FILE_FORMAT = ''
    TASK_FILE_LEVEL = logging.INFO
    PRE_STATE_DB = f'sqlite:///{pwd}/prestate.db'

    SQLALCHEMY_TRACK_MODIFICATIONS = True
    SQLALCHEMY_POOL_RECYCLE = 300


class TestingConfig(Config):
    pass


class DevelopmentConfig(Config):
    DEBUG = True
    TASK_AUTO_LEVEL = logging.DEBUG


class ProductionConfig(Config):
    DEBUG = False


app_config = {
    'testing': TestingConfig,
    'development': DevelopmentConfig,
    'production': ProductionConfig
}
