from enum import Enum
from typing import Union
from sqlalchemy import create_engine
from sqlalchemy import Column, Integer, VARCHAR, CHAR
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.orm.exc import NoResultFound, MultipleResultsFound
from flask_sqlalchemy import SQLAlchemy


def create_connection(conn_str):
    engine = create_engine(conn_str, encoding='utf-8', pool_pre_ping=True)
    session = scoped_session(sessionmaker(bind=engine))
    return session


db = SQLAlchemy()


class TaskPrestate(Enum):
    SENT = 'SENT'
    CANCELED = 'CANCELED'

    @classmethod
    def get(cls, value):
        return getattr(cls, value, None)

    @classmethod
    def all(cls):
        return [x for x in dir(cls) if not x.startswith('_') and not callable(x)]


class PrestateDb(db.Model):
    # create object when task was published
    # update when delete method called
    # delete when task_prerun signal emitted?? task_revoked?? never??
    uid = Column('uid', Integer, primary_key=True)
    task_id = Column('task_id', CHAR(36), unique=True, nullable=False, index=True)
    prestate = Column('prestate', VARCHAR(16), nullable=False)

    def to_dict(self):
        return { 'task_id': self.task_id, 'prestate': self.prestate }


def list_prestate(session):
    objs = session.query(PrestateDb).all()
    task_dict = { obj.task_id: obj.to_dict() for obj in objs }
    session.rollback()
    return task_dict


def get_prestate(session, task_id):
    try:
        obj = session.query(PrestateDb).filter_by(task_id=task_id).one()
        prestate = obj.prestate
        return TaskPrestate.get(prestate)
    except NoResultFound as e:
        return None
    except MultipleResultsFound:
        raise
    finally:
        session.rollback()


def delete_task(session, task_id):
    try:
        obj = session.query(PrestateDb).filter_by(task_id=task_id).one()
        session.delete(obj)
        session.commit()
    except NoResultFound as e:
        return None
    except MultipleResultsFound:
        raise
    finally:
        session.rollback()
    return task_id


def create_task(session, task_id: str, prestate: Union[TaskPrestate, str] = TaskPrestate.SENT):
    if isinstance(prestate, str):
        prestate = TaskPrestate.get(prestate)
        if prestate is None:
            raise ValueError(f'Unknown prestate. Expect either {TaskPrestate.all()}')
    try:
        obj = PrestateDb(task_id=task_id, prestate=prestate.value)
        session.add(obj)
        session.commit()
    finally:
        session.rollback()
    return task_id, prestate


def update_task(session, task_id: str, prestate: Union[TaskPrestate, str]):
    if isinstance(prestate, str):
        prestate = TaskPrestate.get(prestate)
        if prestate is None:
            raise ValueError(f'Unknown prestate. Expect either {TaskPrestate.all()}')
    try:
        obj = session.query(PrestateDb).filter_by(task_id=task_id).one()
        obj.prestate = prestate.value
        session.commit()
    except NoResultFound as e:
        raise
    except MultipleResultsFound:
        raise
    finally:
        session.rollback()
    return task_id, prestate
