__author__ = 'smrutim'
import os
import shutil
from ctypes import *
import datetime
from gluon.tools import *
if False:
    from gluon import *
    request = current.request
    response = current.response
    session = current.session
    cache = current.cache
    T = current.T

if not request.env.web2py_runtime_gae:
    ## if NOT running on Google App Engine use SQLite or other DB
    db = DAL("postgres://spm:12345678@vdb:5432/mydb", pool_size=5, check_reserved=['all'],
             adapter_args=dict(foreign_keys=False), migrate_enabled=True,
             folder='/home/www-data/web2py/applications/rip/databases')
    """
    if str(platform.system()) == "Darwin":
        db = DAL('sqlite://storage.sqlite', pool_size=4, check_reserved=['all'], adapter_args=dict(foreign_keys=False),
                 migrate_enabled=True)
    else:
        db = DAL("postgres://spm:12345678@localhost:5432/mydb", pool_size=5, check_reserved=['all'],
                 adapter_args=dict(foreign_keys=False), migrate_enabled=True,
                 folder='/home/www-data/web2py/applications/rip/databases')
    """

    #db = DAL("postgres://spm:12345678@127.0.0.1:5432/mydb",pool_size=10,check_reserved=['all'],adapter_args=dict(foreign_keys=False),migrate_enabled=True)
else:
    ## connect to Google BigTable (optional 'google:datastore://namespace')
    db = DAL('google:datastore+ndb')
    ## store sessions and tickets there
    session.connect(request, response, db=db)
    ## or store session in Memcache, Redis, etc.
    ## from gluon.contrib.memdb import MEMDB
    ## from google.appengine.api.memcache import Client
    ## session.connect(request, response, db = MEMDB(Client()))


db.define_table('vmpoweropstable',
                Field('launchid',label=T('Launch ID'),default =datetime.datetime.now().strftime("%d%m%y%H%M%S")),
                Field('launchdate',label=T('Launched On'),default=datetime.datetime.now()),
                Field('launchby',label=T('Launched By'),default = auth.user.email if auth.user else "Anonymous"),
                Field('inputjson','text',label=T('Input JSON*'),
                      requires = [IS_NOT_EMPTY(error_message='Input JSON is required'),IS_JSON(error_message='Invalid JSON')]),
                migrate=True)

db.define_table('opstatus',
                Field('launchid',label=T('Launch ID')),
                Field('launchdate',label=T('Launched On'),writable=False),
                Field('launchby',label=T('Launched By')),
                Field('opstype',label=T('Operation')),
                Field('opsdata',label=T('Operation Data')),
                Field('status',label=T('Status'),default="Initiated"),
                Field('statusdetail',label=T('Detailed Status'),length=10240,default="Pending"),
                Field('analystics',label=T('Collect Metrics'),default="Pending"),
                migrate=True
                )

db.define_table('schedulerdebug',
                Field('launchid',label=T('Launch ID')),
                Field('opsidentifier',label=T('Ops Type')),
                Field('debugdata',label=T('Operation Data')),
                migrate=True
                )

db.define_table('vcheapanalyzetable',
                Field('launchid',label=T('Launch ID'),default =datetime.datetime.now().strftime("%d%m%y%H%M%S")),
                Field('launchdate',label=T('Launched On'),default=datetime.datetime.now()),
                Field('launchby',label=T('Launched By'),default = auth.user.email if auth.user else "Anonymous"),
                Field('inputjson','text',label=T('Input JSON*'),
                      requires = [IS_NOT_EMPTY(error_message='Input JSON is required'),IS_JSON(error_message='Invalid JSON')]),
                migrate=True)


db.define_table('vcmemleaktable',
                Field('launchid',label=T('Launch ID'),default =datetime.datetime.now().strftime("%d%m%y%H%M%S")),
                Field('launchdate',label=T('Launched On'),default=datetime.datetime.now()),
                Field('launchby',label=T('Launched By'),default = auth.user.email if auth.user else "Anonymous"),
                Field('inputjson','text',label=T('Input JSON*'),
                      requires = [IS_NOT_EMPTY(error_message='Input JSON is required'),IS_JSON(error_message='Invalid JSON')]),
                migrate=True)

db.define_table('vcmemgrowthtable',
                Field('launchid',label=T('Launch ID'),default =datetime.datetime.now().strftime("%d%m%y%H%M%S")),
                Field('launchdate',label=T('Launched On'),default=datetime.datetime.now()),
                Field('launchby',label=T('Launched By'),default = auth.user.email if auth.user else "Anonymous"),
                Field('inputjson','text',label=T('Input JSON*'),
                      requires = [IS_NOT_EMPTY(error_message='Input JSON is required'),IS_JSON(error_message='Invalid JSON')]),
                migrate=True)

db.define_table('vpxdmemleaktable',
                Field('launchid', label=T('Launch ID'), default=datetime.datetime.now().strftime("%d%m%y%H%M%S")),
                Field('launchdate',label=T('Launched On'),default=datetime.datetime.now()),
                Field('launchby',label=T('Launched By'),default = auth.user.email if auth.user else "Anonymous"),
                Field('inputjson','text',label=T('Input JSON*'),
                      requires = [IS_NOT_EMPTY(error_message='Input JSON is required'),IS_JSON(error_message='Invalid JSON')]),
                migrate=True)

db.define_table('vacpoststatus',
                Field('launchid', label=T('Launch ID')),
                Field('poststatus', label=T('Post Status')),
                Field('responsecode', label=T('Response Code')),
                migrate=True)


db.define_table('vmclonetable',
                Field('launchid',label=T('Launch ID'),default =datetime.datetime.now().strftime("%d%m%y%H%M%S")),
                Field('launchdate',label=T('Launched On'),default=datetime.datetime.now()),
                Field('launchby',label=T('Launched By'),default = auth.user.email if auth.user else "Anonymous"),
                Field('inputjson','text',label=T('Input JSON*'),
                      requires = [IS_NOT_EMPTY(error_message='Input JSON is required'),IS_JSON(error_message='Invalid JSON')]),
                migrate=True)
