# restcelery

## Overview

This repository aims to give the AI, algorithm developer a simple, fast, dockerless, and cross-plateform restful API framework with asynchronous job handler.
This package use the following open packages to reach the proposes:

- **Celery**: A framework used to deal with asynchronous or scheduled jobs, also be an interface of the broker (queue).
- **Flask (flask-restful)**: A framework used to make the restful API


## Features

### Broker Support

- rabbitmq (amqp)
- redis
- sqlite
- mysql, mariadb

### Restful APIs

- ``/task``
    - **GET**: list all the registered tasks

- ``/task/<string:task_id>``
    - **GET**: check task status, results
    - **DELETE**: cancel, revoke task.

        *Notice* This function only work for broker rabbitmq (amqp) and redis.

- ``/download/<string:url>``
    - **GET**: get files from task result folder

- ``/submit/<string:task_name>``
    - **POST**: submit a task


## Install

python 3.7

### Install from master

```sh
$ pip install git+https://github.com/ShihHsuanChen/restcelery.git
```

### Install specific version from tag

```sh
$ pip install git+https://github.com/ShihHsuanChen/restcelery.git@{version tag}
```

## Usage

### Basic Layout

``` sh
<project folder>
├── config.py
├── data
├── tasks.py
└── wsgi.py
```

- ``config.py``

    Setup config classes

- ``data``

    An empty folder to place the task results and log files

- ``tasks.py``

    Python script to put your functions or algorithms. It will be imported in the application by the module name. Of course you can have multiple modules, i.e. tasks1.py, task2.py, ..., this is just the example.

- ``wsgi.py``

    The main script. The entrypoint of flask app and celery. This file can also be named as app.py (see flask run), or any name you like if you use gunicorn to run the app.

### Configuration and setup

#### Celery Setting

- ``CELERY_ACCEPT_CONTENT`` = ['json']

- ``CELERY_TASK_SERIALIZER`` = 'json'

- ``CELERY_RESULT_SERIALIZER`` = 'json'

- ``CELERY_BROKER_URL``

    Queue or database as the job queue.

    Examples:
    - use rabbitmq (recommanded by celery official): ``'amqp://username:password@127.0.0.1:5672/myhost'``
    - use redis: ``'redis://127.0.0.1:6379/0'``
    - use sqlite:  ``'sqla+sqlite:///celery.db'``

- ``CELERY_RESULT_BACKEND``

    Database to save the results

    Examples:
    - use sqlite: ``'db+sqlite:///celery_result.db'``
    - use other databases: // to be updated
    - use rpc for rabbitmq broker: ``rpc://``

- ``CELERYD_PREFETCH_MULTIPLIER``

    Number of tasks per-fork-workers being pre-feteched in the main process.

    Recommand: 1
    
#### Task Related Setting

- ``TASK_WORKDIR`` = './data/'
- ``TASK_FILE_FORMAT`` = ''
- ``TASK_FILE_LEVEL`` = logging.INFO
- ``PRE_STATE_DB`` = f'sqlite:///{pwd}/prestate.db'

Extra setting for ``pre_state_db``

- ``SQLALCHEMY_TRACK_MODIFICATIONS`` = True
- ``SQLALCHEMY_POOL_RECYCLE`` = 300

#### Usage

``` python
# wsgi.py
from restcelery import RestCelery
from config import app_config

task_modules = ['tasks']

def create_app(config_name):
    config = app_config[config_name]
    restcelery = RestCelery(config, task_modules=task_modules)
    return restcelery.app, restcelery.celery, restcelery.worker

app, celery, worker = create_app()
```

``` python
# tasks.py
import time
import logging
from restcelery import RestCelery, get_task_logger
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
    print(workdir)
    for i in range(20):
        msg = f'running [{i}/20]'
        task.record(msg, state='PROGRESS', log=True)
        task.logger.info('[progress] ' + msg)
        time.sleep(1)
    return a**k + b**k


@RestCelery.task(__name__)
def k_mean(task, num_list: list, k: int = 1) -> float:
    workdir = task.work_directory
    print(workdir)
    return sum([x**k for x in num_list]) / len(num_list)
```

### Run


#### Run as an restful API server

- Run with flask

``` sh
$ flask run
```

- Run with gunicorn (linux only)

``` sh 
$ gunicorn wsgi:app
```

#### Run as a celery worker

``` sh
$ celery -A wsgi:celery worker -l info
```

## Examples

See [examples](https://github.com/ShihHsuanChen/restcelery/tree/master/examples)
