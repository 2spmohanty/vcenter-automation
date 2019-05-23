__author__ = 'smrutim'

# -*- coding: utf-8 -*-
# this file is released under public domain and you can use without limitations

#########################################################################
## This is a Cluster controller

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


if False:
    from gluon import *
    request = current.request
    response = current.response
    session = current.session
    cache = current.cache
    T = current.T

def clusterApi():
    return dict()

