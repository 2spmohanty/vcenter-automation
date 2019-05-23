__author__ = 'smrutim'
# -*- coding: utf-8 -*-
# this file is released under public domain and you can use without limitations

#########################################################################
## This is api for vc operation

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
import re
import ssl
import requests
import time

import xml.etree.ElementTree as ElementTree
import multiprocessing
import json
from time import sleep
import datetime
import psycopg2

import multiprocessing
from multiprocessing.dummy import Pool as ThreadPool





status=local_import('status')
customSSH = local_import('customSSH')
HeapCoreModules = local_import('HeapCoreModules')
chapMaster = local_import('chapMaster')
ah64Master = local_import('ah64Master')

from customSSH import RunCmdOverSSH
from HeapCoreModules import _CreateAnalysisDirectory, _PushMemoryJar, _TakeHeapDump
from chapMaster import _DownloadChapToVC,RunChap
from ah64Master import CheckMemGrowth


if False:
    from gluon import *
    request = current.request
    response = current.response
    session = current.session
    cache = current.cache
    T = current.T


synchObj=multiprocessing.Manager()
#Synchronized Object to Hold Results


########################## Get Results API ########################################


@request.restful()
def getresult():
    response.view = 'generic.json'
    def GET(*args,**vars):
        requestBody = request.args
        #print "Str requests "+ str(request.args)
        try:
            if requestBody is None:
                resp = "No request body"
                return dict(error=resp, status=500)
            else:
                opstype = requestBody[0]
                launchid = requestBody[1]
                #print("getResult Debug Result Request OPs Type %s launchid %s "%(opstype,launchid))
                opsRows = db((db.opstatus.launchid == launchid) & (db.opstatus.opstype == opstype)).select()
                #print("GetResult coming after querying DB")
                statusCol=""
                detailStatusCol=""
                for opsRow in opsRows:
                    statusCol = opsRow.status
                    detailStatusCol = opsRow.statusdetail
                    print("getResult Returns rows "+ str(statusCol) + " " + str(detailStatusCol))
                    return dict(status=str(statusCol), result=(detailStatusCol))

        except Exception,e:
            return dict(status=str(e), result=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return locals()



@request.restful()
def opsresult():
    response.view = 'generic.json'
    def POST(*args,**vars):
        jsonBody = request.vars
        print("Str requests "+ str(jsonBody))
        try:
            if jsonBody is None:
                resp = "No request body"
                return dict(error=resp, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                vc_res_json = json.dumps(jsonBody)
                #print "Debug 2 - vm_0 - After Dump JSONObj %s" % (str(vc_res_json))
                vc_ops_json_data = json.loads(vc_res_json)
                print("Debug 3 - vm_0 - After Dump JSONObj %s" % (str(vc_ops_json_data)))
                opstype = vc_ops_json_data['operation']
                launchid = vc_ops_json_data['launchid']
                #print "Debug Result Request OPs Type %s launchid %s "%(opstype,launchid)
                opsRows = db((db.opstatus.launchid == launchid) & (db.opstatus.opstype == opstype)).select()
                for opsRow in opsRows:
                    statusCol = opsRow.status
                    detailStatusCol = opsRow.statusdetail
                    #print("Status Col " + str(statusCol) + " detail Status " + detailStatusCol)
                    return dict(status=str(statusCol), Result=str(detailStatusCol))
        except Exception,e:
            return dict(error=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return locals()



###################################################################################

################################### vcHeapAnalysis Begins ###########################


@request.restful()
def heapanalysis():
    response.view = 'generic.json'
    runTime = datetime.datetime.now().strftime("%d-%m-%y:%H:%M:%S")

    def POST(*args, **vars):
        jsonBody = request.vars
        #print "%s - Debug 1 - vm_0 - initial JSONObj %s " % (runTime, str(jsonBody))
        try:
            if jsonBody is None:
                resp = "No request body"
                return dict(error=resp, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                vc_mem_json = json.dumps(jsonBody)
                print "%s - Debug 2 - vm_0 - After Dump JSONObj %s" % (runTime, str(vc_mem_json))
                vc_ops_json_data = json.loads(vc_mem_json)
                super_operation_type = vc_ops_json_data['operation']
                vcops_launchid = datetime.datetime.now().strftime("%d%m%y%H%M%S")
                vcops_launchdate = datetime.datetime.now()
                vcops_launchby = "External Client"
                operation_type = "heapanalysis"
                final_return_dict = {}
                final_return_dict["Operation"] = super_operation_type
                if vc_ops_json_data['operation'] == "heapanalysis":
                    db.opstatus.insert(launchid=vcops_launchid, launchdate=vcops_launchdate,
                                       launchby=vcops_launchby, opstype=operation_type, opsdata=vc_ops_json_data)
                    db.commit()
                    result_url = "http://%s/opStatus/opstats?queryfield=%s" % (response.app_uri,str(vcops_launchid))
                    return dict(Results=result_url, status=status.HTTP_200_OK)
                else:
                    return dict(Results="JSON Validation Error.Check Key Value Error.",
                                status=status.HTTP_412_PRECONDITION_FAILED)
        except Exception, e:
            return dict(error=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)



    return locals()




################################### vcHeapAnalysis Ends ###########################


################################### vcMemLeak Begins ##############################

mem_result_dict=synchObj.dict()
no_service_running_dict=synchObj.dict()
long_running_dict=synchObj.dict()
exception_service_dict = synchObj.dict()

def core_analysis_handler(service,chapPath,core_file_path,host,username,password):


    local_result = {}

    #print("THREAD - %s - Triggering CHAP on core %s"%(service,core_file_path))
    chapCmd = "echo count leaked | %s %s"%(chapPath,core_file_path)
    (ret, stdout, stderr) = RunChap(service,chapCmd,host,username,password)
    p = re.compile("\s*(\d+)\s+allocations\s+use(.*)?bytes.*")
    m=p.match(stdout)
    if m:
        #print("THREAD - %s - Analysis Result %s" % (service, m.group(0)))
        local_result['Chunks'] = m.group(1)
        local_result['Memory Leak (Bytes)'] = m.group(2)
        mem_result_dict[service] = local_result


def mem_analysis_handler_wrapper(args):
    """
        Wrapping around mem_analysis_handler
    """
    return mem_analysis_handler(*args)


def mem_analysis_handler(host,username, password, service, chapPath, core_analysis_pool,
                         core_analysis_result_pool):
    try:
        generate_core_cmd = "/usr/lib/vmware-vmon/vmon-cli -d %s" % service
        #print("THREAD- %s - Will run command %s" % (service, generate_core_cmd))
        (ret, stdout, stderr) = RunCmdOverSSH(generate_core_cmd, host, username, password)
        #print("THREAD- %s - Generate core for service returned: %s" % (service,str(ret)))
        s = "Completed dump service livecore request"
        core_file_path = None
        if stdout and s in stdout and ret == 0:
            core_file_path = stdout.split()[-1]
            print("THREAD- %s - The core file for service is at %s" % (service, core_file_path))
        elif ret is None:
            print("THREAD- %s - The core file for service is taking time." % service)
            long_running_dict[service] = "Timeout while generating core. Proceed manually."
        else:
            print("THREAD- %s - Error: %s" % (service, str(stderr)))
            if ret == 4:
                print("THREAD- %s - It seems the service is not running on the appliance." % (service))
                no_service_running_dict[service] = "Service not running on VC"

        if core_file_path:
            print('THREAD %s - Starting Analysis of core file ' % service)
            core_analysis_result_pool.append(
                core_analysis_pool.apply_async(core_analysis_handler, (service,chapPath,core_file_path,host,
                                                                       username, password)))
        else:
            print('THREAD %s - Core file not available for analysis. See Previous errors.' % service)

    except Exception, e:
        print("THREAD- %s - Exception while Generating cores in VC for %s service %s"%(host,service,str(e)))
        exception_service_dict[service] = str(e)




@request.restful()
def vcmemleak():
    response.view = 'generic.json'
    runTime = datetime.datetime.now().strftime("%d-%m-%y:%H:%M:%S")
    def POST(*args, **vars):
        jsonBody = request.vars
        #print "%s - Debug 1 - vm_0 - initial JSONObj %s "%(runTime,str(jsonBody))
        try:
            if jsonBody is None:
                resp="No request body"
                return dict(error=resp, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                vc_mem_json = json.dumps(jsonBody)
                #print "%s - Debug 2 - vm_0 - After Dump JSONObj %s" % (runTime, str(vc_mem_json))
                vc_ops_json_data = json.loads(vc_mem_json)
                super_operation_type = vc_ops_json_data['operation']
                vcops_launchid = datetime.datetime.now().strftime("%d%m%y%H%M%S")
                vcops_launchdate = datetime.datetime.now()
                vcops_launchby = "External Client"
                operation_type = "memoryleak"
                final_return_dict= {}
                final_return_dict["Operation"] = super_operation_type
                if vc_ops_json_data['operation'] == "memoryleak":
                    db.opstatus.insert(launchid=vcops_launchid, launchdate=vcops_launchdate,
                                       launchby=vcops_launchby, opstype=operation_type, opsdata=vc_ops_json_data)
                    db.commit()
                    result_url = "http://%s/opStatus/opstats?queryfield=%s" % (response.app_uri,str(vcops_launchid))
                    return dict(Results=result_url, status=status.HTTP_200_OK)
                else:
                    return dict(Results="JSON Validation Error.Check Key Value Error.", status=status.HTTP_412_PRECONDITION_FAILED)

        except Exception, e:
            return dict(error=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return locals()

################################### vcMemLeak Ends ##############################

################################### vcMemGrowth Begins ##############################


@request.restful()
def vcmemgrowth():
    response.view = 'generic.json'
    runTime = datetime.datetime.now().strftime("%d-%m-%y:%H:%M:%S")
    def POST(*args, **vars):
        jsonBody = request.vars
        #print "%s - Debug 1 - vc_0 - initial JSONObj %s "%(runTime,str(jsonBody))

        try:
            if jsonBody is None:
                resp="No request body"
                return dict(error=resp, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                vc_mem_json = json.dumps(jsonBody)
                #print "%s - Debug 2 - vc_0 - After Dump JSONObj %s" % (runTime, str(vc_mem_json))
                vc_ops_json_data = json.loads(vc_mem_json)
                super_operation_type = vc_ops_json_data['operation']
                vc_dict = vc_ops_json_data['vc']
                vcops_launchid = datetime.datetime.now().strftime("%d%m%y%H%M%S")
                vcops_launchdate = datetime.datetime.now()
                vcops_launchby = "External Client"
                operation_type = "memorygrowth"
                final_return_dict= {}
                final_return_dict["operation"] = super_operation_type
                if vc_ops_json_data['operation'] == "memorygrowth" :
                    db.opstatus.insert(launchid=vcops_launchid, launchdate=vcops_launchdate,
                                       launchby=vcops_launchby,opstype=operation_type,opsdata=vc_ops_json_data)
                    db.commit()
                    result_url = "http://%s/opStatus/opstats?queryfield=%s"%(response.app_uri,str(vcops_launchid))
                    return dict(Results=result_url, status=status.HTTP_200_OK)
                else:
                    return dict(Results="JSON Validation Error.", status=status.HTTP_412_PRECONDITION_FAILED)

        except Exception,e:
            return dict(error=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return locals()


################################### vcMemGrowth Ends ##############################

################################### vpxd Memory Leak Begins ##############################

@request.restful()
def vpxdmemleak():
    response.view = 'generic.json'
    runTime = datetime.datetime.now().strftime("%d-%m-%y:%H:%M:%S")
    def POST(*args, **vars):
        jsonBody = request.vars
        print "%s - Debug 1 - vm_0 - initial JSONObj %s " % (runTime, str(jsonBody))
        finalresults = {}
        try:
            if jsonBody is None:
                resp = "No request body"
                return dict(error=resp, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                vc_mem_json = json.dumps(jsonBody)
                print "%s - Debug 2 - vm_0 - After Dump JSONObj %s" % (runTime, str(vc_mem_json))
                vc_ops_json_data = json.loads(vc_mem_json)
                super_operation_type = vc_ops_json_data['operation']
                vcops_launchid = datetime.datetime.now().strftime("%d%m%y%H%M%S")
                vcops_launchdate = datetime.datetime.now()
                vcops_launchby = "External Client"
                operation_type = "vpxdmemleak"
                if vc_ops_json_data['operation'] == "vpxdmemleak" :
                    db.opstatus.insert(launchid=vcops_launchid, launchdate=vcops_launchdate,
                                       launchby=vcops_launchby,opstype=operation_type,opsdata=vc_ops_json_data)
                    db.commit()
                    result_url = "http://%s/opStatus/opstats?queryfield=%s"%(response.app_uri,str(vcops_launchid))
                    return dict(Results=result_url, status=status.HTTP_200_OK)
                else:
                    return dict(Results="JSON Validation Error.", status=status.HTTP_412_PRECONDITION_FAILED)
        except Exception, e:
            dict(error=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    return locals()

################################### vpxd Memory Leak Ends ##############################









