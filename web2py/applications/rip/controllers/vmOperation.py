__author__ = 'smrutim'

# -*- coding: utf-8 -*-
# this file is released under public domain and you can use without limitations

#########################################################################
## This is a VM controller

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

############################ VM POWER OPERATION ######################

def insertIntoopstatusTable_vmPowerOps(form):
    vmops_launchid = form.vars.launchid
    vmops_launchdate = form.vars.launchdate
    vmops_launchby= form.vars.launchby
    vmops_inputjson=form.vars.inputjson

    vm_ops_json_string = json.dumps(form.vars.inputjson,indent=4)
    vm_ops_json_data = json.loads(vm_ops_json_string)
    try:
        if "operation" and "vc" in vm_ops_json_data:
            operation_type = vm_ops_json_data['operation']
            vc_dict = vm_ops_json_data['vc']
            db.opstatus.insert(launchid=vmops_launchid,launchdate=vmops_launchdate
                               ,launchby=vmops_launchby,opstype=operation_type,
                               opsdata=vmops_inputjson)
            db.commit()
            for vc_item in vc_dict:
                vcIP = vc_item['vcname']
                vcUser = vc_item['username']
                vcPassword = vc_item['password']
                dc_dict = vc_item['dc']
                for dc_item in dc_dict:
                    dcName = dc_item["dcname"]
                    cluster_dict = dc_item['cluster']
                    for cluster_item in cluster_dict:
                        clusterName = cluster_item['clustername']
                        pattern_array = None
                        vm_array = None
                        if "pattern" in cluster_item:
                            pattern_array = cluster_item['pattern']
                        elif "vm" in cluster_item:
                            vm_array = cluster_item['vm']
                        else:
                            print "No patterns or VMs specified in the string."

                        runTime = datetime.datetime.now().strftime("%d-%m-%y:%H:%M:%S")
                        print "%s- Controller - VC IP: %s , USER: %s, PASSWORD %s, DCName: %s" \
                              "ClusterName: %s, Pattern: %s, VM: %s " \
                              % (runTime,vcIP, vcUser, vcPassword, dcName, clusterName, pattern_array, vm_array)
        else:
            e = Exception("Invalid JSON input for VM Power Operation.")
            raise e
    except Exception,e:
        print "Unable to initiate operation due to "+str(e)
        print "Follow the following steps sequentially to debug the error."
        print "1 : Check and validate JSON with sample JSON."
        print "2 : If JSON is valid, Please click the below link to file a bug with description."
        raise str(e)

def vmPowerOps():
    form = SQLFORM(db.vmpoweropstable)
    form.custom.widget.inputjson.update(_placeholder="{'Refer Sample JSON':''})")
    if form.process(onvalidation=insertIntoopstatusTable_vmPowerOps ).accepted:
        response.flash = 'Success!'
        session.queryfield =form.vars.launchid
        redirect(URL('opStatus','opstats',vars=dict(queryfield=session.queryfield)))
    elif form.errors:
        response.flash = 'Form has errors'
    return dict(form=form)


##################################################################################################


def vmApi():
    return dict()

################################### CLONE OPERATION ######################################

def insertIntoopstatusTable_vmClone(form):
    vmops_launchid = form.vars.launchid
    vmops_launchdate = form.vars.launchdate
    vmops_launchby = form.vars.launchby
    vmops_inputjson = form.vars.inputjson

    vm_ops_json_string = json.dumps(form.vars.inputjson, indent=4)
    vm_ops_json_data = json.loads(vm_ops_json_string)
    operation_type = vm_ops_json_data['operation']
    try:
        if operation_type == "vmclones":
            vc_dict = vm_ops_json_data['vc']
            db.opstatus.insert(launchid=vmops_launchid, launchdate=vmops_launchdate, launchby=vmops_launchby, opstype=operation_type,opsdata=vmops_inputjson)
            db.commit()

            for vcitem in vc_dict:
                vcname = vcitem["vcname"]
                runtime = datetime.datetime.now().strftime("%d-%m-%y:%H:%M:%S")
                print ("%s- Controller - VM Cloning operation started in VC IP: %s"%(runtime,vcname))
        else:
            e = Exception("Invalid JSON input for VM Power Operation.")
            err = str(e)
            response.flash = err
    except Exception,e:
        err = str(e)
        response.flash = err
        print "Unable to initiate operation due to " + err
        print "Follow the following steps sequentially to debug the error."
        print "1 : Check and validate JSON with sample JSON."
        print "2 : If JSON is valid, Please click the below link to file a bug with description."




def vmClone():
    form = SQLFORM(db.vmclonetable)
    form.custom.widget.inputjson.update(_placeholder="{'Refer Sample JSON':''})")
    if form.process(onvalidation=insertIntoopstatusTable_vmClone).accepted:
        response.flash = 'Success!'
        session.queryfield = form.vars.launchid
        redirect(URL('opStatus', 'opstats', vars=dict(queryfield=session.queryfield)))
    elif form.errors:
        response.flash = 'Form has errors'
    return dict(form=form)

################################### CLONE OPERATION ENDS ######################################

def linkedClone():
    return dict()


def registerVm():
    return dict()

def disklessClones():
    return dict()

def destroyVms():
    return dict()

def addDiskToVm():
    return dict()

def userOperationStatus():
    return dict()



