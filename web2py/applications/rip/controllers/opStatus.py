__author__ = 'smrutim'

# -*- coding: utf-8 -*-
# this file is released under public domain and you can use without limitations

#########################################################################
## This is a Operation Status controller

#########################################################################
import os
import glob
import paramiko
import shutil
import gluon.contenttype as c
from ctypes import *
import sys
import commands
from gluon.tools import Crud
crud = Crud(db)

from pyVmomi import vim
from pyVim.connect import SmartConnect, Disconnect
import atexit
import getpass
import logging
import re
import ssl
import requests
import time

import json

if False:
    from gluon import *
    request = current.request
    response = current.response
    session = current.session
    cache = current.cache
    T = current.T

def opstats():
    if request.vars.queryfield:
        session.queryfield=request.vars.queryfield
    lid = session.queryfield
    query1 = db((db.opstatus.launchid == lid))
    fields = (db.opstatus.launchid, db.opstatus.launchdate, db.opstatus.launchby, db.opstatus.opstype,
              db.opstatus.status,db.opstatus.statusdetail)

    headers = {'db.opstatus.launchid':'ID', 'db.opstatus.launchdate':'Launch Date', 'db.opstatus.launchby': ' User',
               'db.opstatus.opstype':'Operation','db.opstatus.status':'Status','db.opstatus.statusdetail':'Details'}
    grid1 = SQLFORM.grid(query=query1,orderby =~ db.opstatus.id, headers=headers, fields=fields, create=False, user_signature=True,
                         deletable=False, maxtextlength=100, editable=False, paginate=20)
    return dict(grid1=grid1)

def opStatusUser():
    testUser = auth.user.email if auth.user else "Anonymous"
    #print testUser
    query2 = db((db.opstatus.launchby==testUser))
    fields = (db.opstatus.launchid, db.opstatus.launchdate, db.opstatus.launchby, db.opstatus.opstype,
              db.opstatus.status, db.opstatus.statusdetail)

    headers = {'db.opstatus.launchid': 'ID', 'db.opstatus.launchdate': 'Launch Date', 'db.opstatus.launchby': ' User',
               'db.opstatus.opstype': 'Operation', 'db.opstatus.status': 'Status',
               'db.opstatus.statusdetail': 'Details'}
    grid2 = SQLFORM.grid(query=query2, orderby =~ db.opstatus.id, headers=headers, fields=fields, create=False, user_signature=True,
                         deletable=False, maxtextlength=100, editable=False, paginate=20)
    return dict(grid2=grid2)
