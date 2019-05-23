__author__ = 'smrutim'

# -*- coding: utf-8 -*-
# this file is released under public domain and you can use without limitations

#########################################################################
## This is a VC controller

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
import datetime

if False:
    from gluon import *
    request = current.request
    response = current.response
    session = current.session
    cache = current.cache
    T = current.T

def vcApi():
    return dict()

########################## vcMemLeak  Begins ###################################################

def insertIntoopstatusTable_vcMemLeak(form):
    try:
        vcops_launchid = form.vars.launchid
        vcops_launchdate = form.vars.launchdate
        vcops_launchby = form.vars.launchby
        vcops_inputjson = form.vars.inputjson
        vc_ops_json_string = json.dumps(form.vars.inputjson, indent=4)
        vc_ops_json_data = json.loads(vc_ops_json_string)
        if vc_ops_json_data['operation'] == "memoryleak" and "vc" in vc_ops_json_data:
            operation_type = vc_ops_json_data['operation']
            vc_dict = vc_ops_json_data['vc']
            for vc_item in vc_dict:
                host = vc_item['vcname']
                service_name = vc_item['service']
                runTime = datetime.datetime.now().strftime("%d-%m-%y:%H:%M:%S")
                print ("THREAD - %s - Memory Leak - Form Validation - Host: %s , Service Name: %s Operation Type: %s"
                       %(runTime,host,str(service_name),operation_type))

            db.opstatus.insert(launchid=vcops_launchid, launchdate=vcops_launchdate
                               , launchby=vcops_launchby, opstype=operation_type,
                               opsdata=vcops_inputjson)
            db.commit()
        else:
            e = Exception("Invalid JSON input for VC Memory Leak Analysis Operation.")
            session.flash = T(str(e))
    except Exception,e:
        runTime = datetime.datetime.now().strftime("%d-%m-%y:%H:%M:%S")
        print ("THREAD - %s - Memory Leak Analysis - Form Validation Error: %s."%(runTime,str(e)))
        print "Unable to initiate operation due to " + str(e)
        print "Follow the following steps sequentially to debug the error."
        print "1 : Check and validate JSON with sample JSON."
        print "2 : If JSON is valid, Please click the below link to file a bug with description."
        session.flash = T(str(e))


def vcMemLeak():
    form = SQLFORM(db.vcmemleaktable)
    form.custom.widget.inputjson.update(_placeholder="{'Refer Sample JSON':''})")
    if form.process(onvalidation=insertIntoopstatusTable_vcMemLeak).accepted:
        session.flash = 'Success!'
        session.queryfield = form.vars.launchid
        redirect(URL('opStatus', 'opstats', vars=dict(queryfield=session.queryfield)))
    elif form.errors:
        session.flash = 'Form has errors'
    return dict(form=form)

########################## vcMemLeak  Ends ###################################################


########################## vcHeapAnalysis  Begins ###################################################

def insertIntoopstatusTable_vcHeap(form):
    try:

        vcops_launchid = form.vars.launchid
        vcops_launchdate = form.vars.launchdate
        vcops_launchby = form.vars.launchby
        vcops_inputjson = form.vars.inputjson
        vc_ops_json_string = json.dumps(form.vars.inputjson, indent=4)
        vc_ops_json_data = json.loads(vc_ops_json_string)
        if vc_ops_json_data['operation'] == "heapanalysis" and "vc" in vc_ops_json_data:
            operation_type = vc_ops_json_data['operation']
            vc_dict = vc_ops_json_data['vc']
            for vc_item in vc_dict:
                host = vc_item['vcname']
                username = vc_item['username']
                password = vc_item['password']
                jmapPath = vc_item['jmapPath']
                dumpDir = vc_item['dumpDir']
                service_name = vc_item['service']
                hprofname = vc_item.get('hprof', None)
                runTime = datetime.datetime.now().strftime("%d-%m-%y:%H:%M:%S")
                print ("THREAD - %s - Heap Analysis - Form Validation - Host: %s , Service Name: %s Operation Type: %s"
                       %(runTime,host,str(service_name),operation_type))

            db.opstatus.insert(launchid=vcops_launchid, launchdate=vcops_launchdate
                               , launchby=vcops_launchby, opstype=operation_type,
                               opsdata=vcops_inputjson)
            db.commit()
        else:
            e = Exception("Invalid JSON input for VC Heap Analysis Operation.")
            session.flash = T(str(e))
    except Exception,e:
        runTime = datetime.datetime.now().strftime("%d-%m-%y:%H:%M:%S")
        print ("THREAD - %s - Heap Analysis - Form Validation Error: %s."%(runTime,str(e)))
        print "Unable to initiate operation due to " + str(e)
        print "Follow the following steps sequentially to debug the error."
        print "1 : Check and validate JSON with sample JSON."
        print "2 : If JSON is valid, Please click the below link to file a bug with description."
        session.flash = T(str(e))


def vcHeapAnalysis():
    form = SQLFORM(db.vcheapanalyzetable)
    form.custom.widget.inputjson.update(_placeholder="{'Refer Sample JSON':''})")
    if form.process(onvalidation=insertIntoopstatusTable_vcHeap).accepted:
        session.flash = 'Success!'
        session.queryfield = form.vars.launchid
        redirect(URL('opStatus', 'opstats', vars=dict(queryfield=session.queryfield)))
    elif form.errors:
        session.flash = 'Form has errors'
    return dict(form=form)

########################## vcHeapAnalysis  Ends ###################################################

def vcStats():
    return dict()

#################################VC Memory Growth Begins###################################


def insertIntoopstatusTable_vcMemGrowth(form):
    try:
        vcops_launchid = form.vars.launchid
        vcops_launchdate = form.vars.launchdate
        vcops_launchby = form.vars.launchby
        vcops_inputjson = form.vars.inputjson
        vc_ops_json_string = json.dumps(form.vars.inputjson, indent=4)
        vc_ops_json_data = json.loads(vc_ops_json_string)
        if vc_ops_json_data['operation'] == "memorygrowth" and "vc" in vc_ops_json_data:
            operation_type = vc_ops_json_data['operation']
            vc_dict = vc_ops_json_data['vc']
            for vc_item in vc_dict:
                vcName = vc_item["vcname"]
                vcUser = vc_item["ssh_user"]
                vcPwd = vc_item["ssh_pass"]
                vcLocalUser = vc_item["local_user"]
                vcLocalPwd = vc_item["local_pass"]
                vcBuild = vc_item["vc_build"]
                vcVersion = vc_item["vc_version"]
                runTime = datetime.datetime.now().strftime("%d-%m-%y:%H:%M:%S")
                print ("THREAD - %s - Memory Growth Analysis - Form Validation - VC: %s , Operation Type: %s"
                       %(runTime,vcName,operation_type))

            db.opstatus.insert(launchid=vcops_launchid, launchdate=vcops_launchdate
                               , launchby=vcops_launchby, opstype=operation_type,
                               opsdata=vcops_inputjson)
            db.commit()
        else:
            e = Exception("Invalid JSON input for VC Memory Leak Analysis Operation.")
            session.flash = T(str(e))
    except Exception,e:
        runTime = datetime.datetime.now().strftime("%d-%m-%y:%H:%M:%S")
        print ("THREAD - %s - Memory Leak Analysis - Form Validation Error: %s."%(runTime,str(e)))
        print "Unable to initiate operation due to " + str(e)
        print "Follow the following steps sequentially to debug the error."
        print "1 : Check and validate JSON with sample JSON."
        print "2 : If JSON is valid, Please click the below link to file a bug with description."
        session.flash = T(str(e))


def vcMemGrowth():
    form = SQLFORM(db.vcmemgrowthtable)
    form.custom.widget.inputjson.update(_placeholder="{'Refer Sample JSON':''})")
    if form.process(onvalidation=insertIntoopstatusTable_vcMemGrowth).accepted:
        session.flash = 'Success!'
        session.queryfield = form.vars.launchid
        redirect(URL('opStatus', 'opstats', vars=dict(queryfield=session.queryfield)))
    elif form.errors:
        session.flash = 'Form has errors'
    return dict(form=form)

#################################VC Memory Growth Ends###################################

###############################VPXD Memory Leak Begins ###############################

def insertIntoopstatusTable_vpxdMemLeak(form):
    try:
        vcops_launchid = form.vars.launchid
        vcops_launchdate = form.vars.launchdate
        vcops_launchby = form.vars.launchby
        vcops_inputjson = form.vars.inputjson
        vc_ops_json_string = json.dumps(form.vars.inputjson, indent=4)
        vc_ops_json_data = json.loads(vc_ops_json_string)
        if vc_ops_json_data['operation'] == "vpxdmemleak" and "vc" in vc_ops_json_data:
            operation_type = vc_ops_json_data['operation']
            vc_dict = vc_ops_json_data['vc']
            for vc_item in vc_dict:
                host = vc_item['vcname']
                username = vc_item['username']
                password = vc_item['password']
                runTime = datetime.datetime.now().strftime("%d-%m-%y:%H:%M:%S")
                print ("THREAD - %s - VPXD Memory Leak Analysis - Form Validation - VC: %s , Operation Type: %s"
                       % (runTime, host, operation_type))

            db.opstatus.insert(launchid=vcops_launchid, launchdate=vcops_launchdate
                               , launchby=vcops_launchby, opstype=operation_type,
                               opsdata=vcops_inputjson)
            db.commit()

        else:
            e = Exception("Invalid JSON input for VPXD Memory Leak Analysis Operation.")
            session.flash = T(str(e))
    except Exception, e:
        runTime = datetime.datetime.now().strftime("%d-%m-%y:%H:%M:%S")
        print ("THREAD - %s - Memory Leak Analysis - Form Validation Error: %s." % (runTime, str(e)))
        print "Unable to initiate operation due to " + str(e)
        print "Follow the following steps sequentially to debug the error."
        print "1 : Check and validate JSON with sample JSON."
        print "2 : If JSON is valid, Please click the below link to file a bug with description."
        session.flash = T(str(e))


def vpxdMemLeak():
    form = SQLFORM(db.vpxdmemleaktable)
    form.custom.widget.inputjson.update(_placeholder="{'Refer Sample JSON':''})")
    if form.process(onvalidation=insertIntoopstatusTable_vpxdMemLeak).accepted:
        session.flash = 'Success!'
        session.queryfield = form.vars.launchid
        redirect(URL('opStatus', 'opstats', vars=dict(queryfield=session.queryfield)))
    elif form.errors:
        session.flash = 'Form has errors'
    return dict(form=form)



###############################VPXD Memory Leak Ends ###########################