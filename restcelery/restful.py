import os
import copy
import pprint
import shutil
import inspect

from collections import OrderedDict
from flask import send_from_directory
from flask_restful import Resource, reqparse
from celery import states as TaskStates
from celery.contrib.testing.mocks import task_message_from_sig

from .prestate import TaskPrestate
from .prestate import get_prestate
from .prestate import update_task

from .utils import get_work_directory
from .utils import format_task_info


__all__ = ['create_restful']

def _get_param_dict(task_name, func):
    sig = inspect.signature(func)
    param_dict = OrderedDict()

    parameters = OrderedDict(sig.parameters)

    for param in parameters.values():
        name = param.name
        typ = param.annotation
        default = param.default
        tmp = dict()
        if typ is not inspect.Parameter.empty:
            tmp['type'] = typ
        if default is not inspect.Parameter.empty:
            tmp['required'] = False
            tmp['default'] = default
        else:
            tmp['required'] = True
        param_dict[name] = tmp
    return param_dict


def create_restful(api, celery, db, task_map: dict, base_directory: str, broker_type: str):

    func_dict = dict()
    for name, func in task_map.items():
        celery.task(name=name, bind=True)(func)
        param_dict = _get_param_dict(name, func)
        func_dict[name] = param_dict
        print(f'register {name}:')
        pprint.pprint(param_dict)

    class Submit(Resource):
        def post(_self, task_name):
            parser = reqparse.RequestParser()
            param_dict = func_dict.get(task_name)
            if param_dict is None:
                raise ValueError('Unknown task name')

            for pname, param in param_dict.items():
                parser.add_argument(pname, **param, location='json')
            kwargs = parser.parse_args()
            kwargs = dict(kwargs)

            task_result = celery.tasks.get(task_name).apply_async(kwargs=kwargs, retry=True)
            return task_result.id

    class Download(Resource):
        def get(_self, url):
            # url: <task_id>/<directory/filename>..
            fullpath = os.path.join(base_directory, url)
            if os.path.exists(fullpath) and not os.path.isdir(fullpath):
                dirname = os.path.dirname(fullpath)
                basename = os.path.basename(fullpath)
                return send_from_directory(dirname, basename)
            else:
                return 'Resource not found', 404

    class Task(Resource):
        def get(_self, task_id: str):
            task_result = celery.AsyncResult(task_id)
            # -> check state
            # PENDING: unknown
            #     -> check prestate
            #     None: no such task
            #     SENT: sent and waiting
            #     CANCELED: task is canceled but not revoked yet
            # > REVOKED: waiting or running
            #     -> pass
            # REVOKED: already revoked
            #     -> pass
            # SUCCESS:
            #     -> remove results ?
            # FAILED, ???
            #     -> ???

            if task_result.state == TaskStates.PENDING:
                prestate = get_prestate(db.session, task_id)
                if prestate is None:
                    return 'Unknown task_id'
                elif prestate == TaskPrestate.SENT:
                    result = {'status': prestate.value, 'result': None, 'info': 'sent'}
                elif prestate == TaskPrestate.CANCELED:
                    result = {'status': prestate.value, 'result': None, 'info': 'canceled'}
                else:
                    raise ValueError(f'Unknown prestate {prestate}')

            elif TaskStates.state(task_result.status) > TaskStates.state(TaskStates.REVOKED):
                info = format_task_info(task_result.info)
                result = {'status': task_result.status, 'result': None, 'info': info}

            elif task_result.state == TaskStates.REVOKED:
                result = {'status': task_result.status, 'result': None, 'info': 'revoked'}

            elif task_result.state == TaskStates.SUCCESS:
                try:
                    data = task_result.get()
                except Exception as e:
                    print(str(e))
                    data = None
                result = {
                        'status': task_result.status,
                        'result': {
                            'data': data,
                            'download_url': f'/download/{task_id}/results.zip'
                            },
                        'info': 'finish'
                        }
            else:
                info = format_task_info(task_result.info)
                result = {'status': task_result.status, 'result': None, 'info': info}
            return result

        def delete(_self, task_id: str):
            # support only for amqp and redis
            # check amqp or redis
            # -> check state
            # PENDING: unknown
            #     -> check prestate
            #     None: no such task
            #         -> pass
            #     SENT: sent and waiting
            #         -> set to CANCELED
            #     CANCELED: task is canceled but not revoked yet
            #         -> pass
            # > REVOKED: waiting or running
            #     -> pass
            # REVOKED: already revoked
            #     -> pass
            # SUCCESS:
            #     -> remove results ?
            # FAILED, ???
            #     -> ???
            task_result = celery.AsyncResult(task_id)

            if broker_type not in ['amqp', 'redis']:
                return f'Delete function does not support current broker type {broker_type}.'

            if task_result.state == TaskStates.PENDING:
                prestate = get_prestate(db.session, task_id)
                if prestate is None:
                    return 'Unknown task_id.'
                elif prestate == TaskPrestate.SENT:
                    update_task(db.session, task_id, TaskPrestate.CANCELED)
                    return f'Cancel task {task_id}.'
                elif prestate == TaskPrestate.CANCELED:
                    return f'Task {task_id} already canceled.'
                else:
                    raise ValueError(f'Unknown prestate {prestate}')

            elif task_result.state == TaskStates.REVOKED:
                return f'Task {task_id} already revoked.'

            elif task_result.state == TaskStates.SUCCESS:
                # remove work directory
                # remove task from prestatedb
                pass

            elif TaskStates.state(task_result.status) < TaskStates.state(TaskStates.REVOKED):
                # STARTED, ...,
                print(task_result.status)
                wdir = get_work_directory(base_directory, task_id)
                if os.path.isdir(wdir):
                    shutil.rmtree(wdir)
                task_result.revoke(terminate=True, signal='SIGKILL')
                return f'Revoke task {task_id}.'

            elif task_result.status == TaskStates.state('PROGRESS'):
                print('PROGRESS')
                # custom state: PROGRESS
                wdir = get_work_directory(base_directory, task_id)
                if os.path.isdir(wdir):
                    shutil.rmtree(wdir)
                task_result.revoke(terminate=True, signal='SIGKILL')
                return f'Revoke task {task_id}.'

            else:
                # remove work directory
                # remove task from prestatedb
                return _self.get(task_id)

    class Tasks(Resource):
        def get(_self):
            parser = reqparse.RequestParser()

            parser.add_argument('task_name', type=str, required=False, location='args')
            kwargs = parser.parse_args()
            kwargs = dict(kwargs)
            task_name = kwargs.pop('task_name')

            ctasks = { name: task_func
                       for name, task_func in celery.tasks.items()
                       if not name.startswith('celery.') }

            flist = list()
            for fname, func in task_map.items():
                if task_name is not None and fname != task_name:
                    continue
                param_dict = copy.deepcopy(func_dict.get(fname))

                mock_args = list()
                mock_kwargs = dict()

                for pname, tmp in param_dict.items():
                    if tmp['required']:
                        mock_args.append(f'${pname}')
                    else:
                        mock_kwargs[pname] = f'${pname}'
                    tmp['type'] = tmp['type'].__name__

                task_func = ctasks.get(fname)
                sig = task_func.s(*mock_args, **mock_kwargs)
                msgmock = task_message_from_sig(celery, sig)
                message = { x: getattr(msgmock, x, None)
                            for x in ['headers',
                                      'body',
                                      'content_type',
                                      'content_encoding',
                                      'payload']
                            }
                message['headers']['id'] = '$task_id'
                message['headers']['task_id'] = '$task_id'
                message['headers']['reply_to'] = '${queue name to reply to}'
                """ message
                {
                    "body": base64(json({
                        "task_id": "055e4170-d3a0-4f82-a3c4-a3b19667d428",
                        "status": "SUCCESS",
                        "result": 89,
                        "traceback": null,
                        "children": []
                    })),
                    "content-encoding": "utf-8",
                    "content-type": "application/json",
                    "headers": {},
                    "properties": {
                        "correlation_id": "055e4170-d3a0-4f82-a3c4-a3b19667d428",
                        "delivery_mode": 1,
                        "delivery_info": {
                            "exchange": "",
                            "routing_key": "bc1c49ea-d33d-3658-9f0d-dc3f069a9c64"
                        },
                        "priority": 0,
                        "body_encoding": "base64",
                        "delivery_tag": "f5422387-e237-4c1f-94d9-bb4dfb283194"
                    }
                }
                """

                flist.append({
                    'name': fname,
                    'params': param_dict,
                    'description': func.__doc__,
                    'message_example': message
                    })
            return flist

    api.add_resource(Submit, f'/submit/<string:task_name>')
    api.add_resource(Download, '/download/<string:url>')
    api.add_resource(Tasks, '/task')
    api.add_resource(Task, '/task/<string:task_id>')
