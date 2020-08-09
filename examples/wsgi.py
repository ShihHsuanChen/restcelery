from argparse import ArgumentParser
from restcelery import RestCelery

from config import app_config


task_modules = ['tasks']


def create_app(config_name):
    config = app_config[config_name]
    restcelery = RestCelery(config, task_modules=task_modules)
    return restcelery.app, restcelery.celery, restcelery.worker


app, celery, worker = create_app('development')
"""
Usage:
- Run flask app:
    flask run
- Run celery worker:
    celery -A wsgi:celery worker -l info
"""

if __name__ == '__main__':
    parser = ArgumentParser()
    parser.add_argument('runtype', help='app: flask app; worker: celery worker', choices=['app', 'worker'])
    args = parser.parse_args()
    runtype = args.runtype
    if runtype == 'app':
        app.run()
    elif runtype == 'worker':
        worker.run()
    else:
        print('Unknown runtype')
        print(parser.help)
