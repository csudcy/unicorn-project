import psycopg2
import time, uuid, os, json
from sqlalchemy import Column, ForeignKey, Integer, BigInteger, String, Float, Text, Boolean, PickleType, Enum, create_engine, UniqueConstraint
from sqlalchemy.orm import relationship, sessionmaker, scoped_session
from sqlalchemy.exc import OperationalError
from sqlalchemy.sql import expression
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.associationproxy import association_proxy

Session = scoped_session(sessionmaker())
Base = declarative_base()

def get_engine(user, password, name, ip_address, port):
    """Returns the sql alchemy engine using the supplied parameters
    """
    #TODO FIX THIS
    conn_str = 'postgresql://%s:%s@%s:%s/%s' % (user, password, ip_address, port, name)
    return create_engine(conn_str,echo=False, client_encoding='utf8')

def create_db(user, password, name, ip_address, port):
    """Creates a database using the supplied paramters"""
    print ('User: {0}, Password: {1}, Db Name: {2}'.format(user, password, name))
    # Leave name out of connection string (we want to connect to the engine,
    # not the db that might not be there)
    tmp_create_engine = get_engine(user, password, '', ip_address, port)
    # Need to change the isolation level because otherwise PostgreSQL will
    # try to execute CREATE DATABASE inside a transaction and barf
    tmp_create_engine.raw_connection().set_isolation_level(
                            psycopg2.extensions.ISOLATION_LEVEL_AUTOCOMMIT)
    tmp_create_engine.execute(expression.text(
                                      "CREATE DATABASE %s WITH OWNER = "\
                                      "%s ENCODING 'UTF8'" % \
                                        (name, user)))
    tmp_create_engine.dispose()
    del tmp_create_engine

def create_tables(user, password, name, ip_address, port):
    try:
        Base.metadata.create_all(engine)
    except OperationalError, ex:
        # -- Set the DB engine
        create_db(user, password, name, ip_address, port)
        Base.metadata.create_all(engine)

def set_up(user, password, name, ip_address, port):
    global engine, Base, Session
    engine = get_engine(user, password, name, ip_address, port)
    Session = scoped_session(sessionmaker(bind=engine))


def tear_down(user, password, name, ip_address, port):
    try:
        tear_down_engine = get_engine(user, password, name, ip_address, port)
        TearDownBase = declarative_base()
        TearDownBase.metadata.reflect(tear_down_engine)
        TearDownBase.metadata.drop_all(tear_down_engine)
        tear_down_engine.dispose()
    except OperationalError:
        #TODO Proper logging here
        print 'Error dropping database'

def close_session(function):
    """
    Decorator that ensures that the db scoped_session is closed after a function (only needed on non-request funcs)
    """
    def wrapped_function(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        finally:
            # wrap the session remove so no problems obscure an issue in the underlying function
            try:
                Session.remove()
            except:
                pass
    return wrapped_function

def _close_session():
    """Closes the database session - called by cherrypy end of request handler
        - may be redundant
    """
    # print "Closing session"
    Session.remove()

class Log(Base):
    __tablename__ = 'log'
    id = Column(Integer, nullable=False, primary_key=True, index=True)
    datestamp   = Column(Float())
    track_type = Column(String(50))
    site_id  = Column(String(30))

