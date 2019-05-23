__author__ = 'smrutim'
# -*- coding: utf-8 -*-
# this file is released under public domain and you can use without limitations

#########################################################################
## This is api for vm operation

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
from multiprocessing.dummy import Pool as ThreadPool
from pyVmomi import vim
from pyVim.connect import SmartConnect, Disconnect
import atexit
import getpass
import logging
import re
import ssl
import requests
import time
import urllib2
import urlparse
import base64

import xml.etree.ElementTree as ElementTree
import multiprocessing
import json
from time import sleep
import datetime

VDSprac = local_import('VDSprac')
DatacenterPrac=local_import('DatacenterPrac')
clusterPrac=local_import('clusterPrac')
VMPrac = local_import('VMPrac')
status=local_import('status')

from VDSprac import Login,CreateVDS,FindFreePort,AddHostToVDS,CreateDVPortgroups,GetDVPortgroup,GetVDS
from DatacenterPrac import GetDatacenter, GetAllClusters,GetAllClusterNames,GetAllClusterSummary,GetCluster,\
    CreateDatacenter,CreateCluster
from clusterPrac import GetHostsInCluster,GetHostsInClusters,GetAllResourcePool,ReconfigureDRSHA,GetVms,AddHost
from VMPrac import find_obj,get_container_view, collect_properties

if False:
    from gluon import *
    request = current.request
    response = current.response
    session = current.session
    cache = current.cache
    T = current.T


#########################VM Power Operation Begins#####################################
def vm_ops_handler_wrapper(args):
    """
    Wrapping arround vm_ops_handler
    """
    return vm_ops_handler(*args)

def vm_ops_handler(vm_name, vm_object, operation, maxwait):
    vm = vm_object
    if vm and operation.lower() == "off":
        print('THREAD %s - Powering off VM. This might take a couple of seconds' % vm_name)
        power_off_task = vm.PowerOff()
        print('THREAD %s - Waiting for VM to power off' % vm_name)
        run_loop = True
        while run_loop:
            info = power_off_task.info
            if info.state == vim.TaskInfo.State.success:
                run_loop = False
                break
            elif info.state == vim.TaskInfo.State.error:
                if info.error:
                    print('THREAD %s - Power off has quit with error: %s' % (vm_name, info.error))
                else:
                    print('THREAD %s - Power off has quit with cancelation' % vm_name)
                run_loop = False
                break
            sleep(5)

    elif vm and operation.lower() == "on":
        print('THREAD %s - Powering on VM. This might take a couple of seconds' % vm_name)
        power_off_task = vm.PowerOn()
        print('THREAD %s - Waiting for VM to power on' % vm_name)
        run_loop = True
        while run_loop:
            info = power_off_task.info
            if info.state == vim.TaskInfo.State.success:
                run_loop = False
                print('THREAD %s - Holding for %s seconds before releasing thread for next operation' % (vm_name, maxwait))
                sleep(maxwait)
                break
            elif info.state == vim.TaskInfo.State.error:
                if info.error:
                    print('THREAD %s - Power on has quit with error: %s' % (vm_name, info.error))
                else:
                    print('THREAD %s - Power on has quit with cancelation' % vm_name)
                run_loop = False
                break
            sleep(5)

@request.restful()
def vmpoweroperation():
    response.view = 'generic.json'
    runTime = datetime.datetime.now().strftime("%d-%m-%y:%H:%M:%S")
    si = None
    def POST(*args, **vars):
        jsonBody = request.vars
        print "%s - Debug 1 - vm_0 - initial JSONObj %s "%(runTime,str(jsonBody))

        finalresults = {}
        if jsonBody is None:
            resp="No request body"
            return dict(error=resp, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            vm_ops_json = json.dumps(jsonBody)
            print "%s - Debug 2 - vm_0 - After Dump JSONObj %s"%(runTime,str(vm_ops_json))
            vm_ops_json_data = json.loads(vm_ops_json)
            super_operation_type = vm_ops_json_data['operation']
            vc_dict = vm_ops_json_data['vc']
            for vc_item in vc_dict:
                vcIP = vc_item['vcname']
                vcUser = vc_item['username']
                vcPassword = vc_item['password']
                maxwait = vc_item.get('wait',60)
                dc_dict = vc_item['dc']

                for dc_item in dc_dict:
                    dcName = dc_item["dcname"]
                    cluster_dict = dc_item['cluster']
                    for cluster_item in cluster_dict:
                        vm_data = {}
                        clusterName = cluster_item['clustername']
                        operation = cluster_item['ops']
                        pattern_array = None
                        vm_array = None
                        if "pattern" in cluster_item:
                            pattern_array = cluster_item['pattern']

                        elif "vm" in cluster_item:
                            #vm_array = cluster_item['vm'] #Have to implement only VM name. Not yet Done
                            pattern_array = cluster_item['vm']
                        else:
                            print "No patterns or VMs specified in the string."


                        print "Date : %s - vm_0 -  VC IP: %s , USER: %s, PASSWORD %s, DCName: %s" \
                              "ClusterName: %s, Pattern: %s, VM: %s WaitTime: %s" \
                              % (runTime,vcIP, vcUser, vcPassword, dcName, clusterName, pattern_array, vm_array,maxwait)
                        try:
                            si = Login(vcIP, vcUser, vcPassword)
                        except Exception, e:
                            resp = str(e)
                            return dict(stat=resp, status=status.HTTP_403_FORBIDDEN)
                        try:

                            dcMor = find_obj(si, dcName, [vim.Datacenter], False)

                            clusterMor = GetCluster(dcMor, clusterName, si)
                            for pattern in pattern_array:
                                print(('Finding VM objects %s via property collector.' % pattern))
                                vm_properties = ["name"]
                                view = get_container_view(si, obj_type=[vim.VirtualMachine], container=clusterMor)
                                vm_data = collect_properties(si, view_ref=view,
                                                             obj_type=vim.VirtualMachine,
                                                             path_set=vm_properties,
                                                             include_mors=True, desired_vm=pattern)
                                if any(vm_data):
                                    print('VM matching %s patteren found for power ops.' % pattern)
                                else:
                                    print('Finding VM matching pattern %s failed .' % pattern)

                                vm_specs = []
                                print('Creating vmoperation pools with %s threads' % 10)

                                pool = ThreadPool(10)
                                for vm_name, vm_object in vm_data.iteritems():
                                    finalresults[vm_name] = operation
                                    vm_specs.append((vm_name, vm_object, operation, maxwait))

                                pool.map(vm_ops_handler_wrapper, vm_specs)

                                pool.close()
                                pool.join()
                        except Exception,e:
                            resp = str(e)
                            return dict(stat=resp, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            print ("Fhinished All %s tasks"% super_operation_type)

            return dict(stat="Triggered VMPowerOPs: "+str(finalresults), status=status.HTTP_200_OK)

    return locals()

#########################VM Power Operation Ends#####################################

@request.restful()
def vm_dummy():
    pass

#########################VM Register Operation Begins#####################################

VMX_PATH = []
DS_VM = {}
INV_VM = []
REGISTER_VMX=[]

def updatevmx_path():
    """
    function to set the VMX_PATH global variable to null
    """
    global VMX_PATH
    VMX_PATH = []

def url_fix(s, charset='utf-8'):
    """
    function to fix any URLs that have spaces in them
    urllib for some reason doesn't like spaces
    function found on internet
    """
    if isinstance(s, unicode):
        s = s.encode(charset, 'ignore')
    scheme, netloc, path, qs, anchor = urlparse.urlsplit(s)
    path = urllib2.quote(path, '/%')
    qs = urllib2.quote(qs, ':&=')
    return urlparse.urlunsplit((scheme, netloc, path, qs, anchor))

def find_vmx(host,dsbrowser, dsname, datacenter, fulldsname):
    """
    function to search for VMX files on any datastore that is passed to it
    """
    #args = get_args()
    search = vim.HostDatastoreBrowserSearchSpec()
    search.matchPattern = "*.vmx"
    search_ds = dsbrowser.SearchDatastoreSubFolders_Task(dsname, search)
    while search_ds.info.state != "success":
        pass
    # results = search_ds.info.result
    # print results

    for rs in search_ds.info.result:
        dsfolder = rs.folderPath
        for f in rs.file:
            try:
                dsfile = f.path
                vmfold = dsfolder.split("]")
                vmfold = vmfold[1]
                vmfold = vmfold[1:]
                vmxurl = "https://%s/folder/%s%s?dcPath=%s&dsName=%s" % \
                         (host, vmfold, dsfile, datacenter, fulldsname)
                VMX_PATH.append(vmxurl)
            except Exception, e:
                print "Caught exception : " + str(e)
                return -1


def examine_vmx(dsname,expectedPattern,username,password):
    """
    function to download any vmx file passed to it via the datastore browser
    and find the 'vc.uuid' and 'displayName'
    """
    #args = get_args()

    try:
        for file_vmx in VMX_PATH:
            # print file_vmx

            username = username
            password = password
            gcontext = ssl._create_unverified_context()
            request = urllib2.Request(url_fix(file_vmx))
            base64string = base64.encodestring(
                '%s:%s' % (username, password)).replace('\n', '')
            request.add_header("Authorization", "Basic %s" % base64string)
            result = urllib2.urlopen(request,context=gcontext)
            vmxfile = result.readlines()
            mylist = []
            for a in vmxfile:
                mylist.append(a)
            for b in mylist:
                if b.startswith("displayName"):
                    dn = b
                if b.startswith("vc.uuid"):
                    vcid = b
            uuid = vcid.replace('"', "")
            uuid = uuid.replace("vc.uuid = ", "")
            uuid = uuid.strip("\n")
            uuid = uuid.replace(" ", "")
            uuid = uuid.replace("-", "")
            newdn = dn.replace('"', "")
            newdn = newdn.replace("displayName = ", "")
            newdn = newdn.strip("\n")
            if any(item in newdn for item in expectedPattern) :
                #Debug
                #print newdn
                vmfold = file_vmx.split("folder/")
                vmfold = vmfold[1].split("/")
                vmfold = vmfold[0]
                dspath = "[%s]/%s" % (dsname, vmfold)
                tempds_vm = dspath+"/"+newdn+".vmx"
                DS_VM[uuid] = tempds_vm
            else:
                pass

    except Exception, e:
        print "Caught exception : " + str(e)


def getvm_info(vm, depth=1):
    """
    Print information for a particular virtual machine or recurse
    into a folder with depth protection
    from the getallvms.py script from pyvmomi from github repo
    """
    maxdepth = 10

    # if this is a group it will have children. if it does,
    # recurse into them and then return

    if hasattr(vm, 'childEntity'):
        if depth > maxdepth:
            return
        vmlist = vm.childEntity
        for c in vmlist:
            getvm_info(c, depth+1)
        return
    if hasattr(vm, 'CloneVApp_Task'):
        vmlist = vm.vm
        for c in vmlist:
            getvm_info(c)
        return

    try:
        uuid = vm.config.instanceUuid
        uuid = uuid.replace("-", "")
        INV_VM.append(uuid)
    except Exception, e:
        print "Caught exception : " + str(e)
        return -1


def find_match(uuid,logger):
    """
    function takes vc.uuid from the vmx file and the instance uuid from
    the inventory VM and looks for match if no match is found
    it is printed out.
    """
    global REGISTER_VMX
    a = 0
    for temp in INV_VM:
        if uuid == temp:
            a = a+1
    if a < 1:
        REGISTER_VMX.append(DS_VM[uuid])
        print(DS_VM[uuid] + " will be registered to the inventory")


@request.restful()
def registerVms():
    response.view = 'generic.json'
    runTime = datetime.datetime.now().strftime("%d-%m-%y:%H:%M:%S")
    si = None

    def POST(*args, **vars):
        jsonBody = request.vars
        print "%s - Debug 1 - vm_0 - initial JSONObj %s " % (runTime, str(jsonBody))

        finalresults = {}
        if jsonBody is None:
            resp = "No request body"
            return dict(error=resp, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        else:
            vm_ops_json = json.dumps(jsonBody)
            print "%s - Debug 2 - vm_0 - After Dump JSONObj %s" % (runTime, str(vm_ops_json))
            vm_ops_json_data = json.loads(vm_ops_json)
            super_operation_type = vm_ops_json_data['operation']
            vc_dict = vm_ops_json_data['vc']
            final_result = {}
            for vc_item in vc_dict:
                host = vc_item['vcname']
                username = vc_item['username']
                password = vc_item['password']
                datacenter_name = vc_item['dc']
                clusterArray = vc_item['cluster']
                datastoreList = vc_item['datastore']
                userPattern = vc_item['pattern']
                power = vc_item['power']
                pause = vc_item['wait']
                si = None
                try:
                    si = Login(host, username, password)
                except Exception, e:
                    final_result['Result'] = "Unable to Login to VC %s due to %s "%(host,str(e))
                    final_result['status'] = status.HTTP_401_UNAUTHORIZED
                    continue

                datacenter = None

                if datacenter_name:
                    print('THREAD %s - Finding datacenter %s' % ("MAIN", datacenter_name))
                    datacenter = find_obj(si,datacenter_name, [vim.Datacenter], False)
                    if datacenter is None:
                        final_result['Result'] = "Unable to spot DC %s in VC %s " % (datacenter_name,host)
                        final_result['status'] = status.HTTP_412_PRECONDITION_FAILED
                        continue

                    print('THREAD %s - Datacenter %s found' % ("MAIN", datacenter_name))

                datastores = datacenter.datastore
                vmfolder = datacenter.vmFolder
                vmlist = vmfolder.childEntity
                dsvmkey = []

                for ds in datastores:
                    if ds.info.name in datastoreList:
                        print("Processing Datastore " + ds.info.name)
                        find_vmx(host,ds.browser, "[%s]" % ds.summary.name, datacenter.name, ds.summary.name)
                        examine_vmx(ds.summary.name, userPattern, username, password)
                        updatevmx_path()
                    else:
                        pass

                    # each VM found in the inventory is passed to the getvm_info
                    # function to get it's instanceuuid

                    # Debug
                    # print "Coming Here 1"

                    for vm in vmlist:
                        getvm_info(vm)

                    # each key from the DS_VM hashtable is added to a separate
                    # list for comparison later


                    for a in DS_VM.keys():
                        dsvmkey.append(a)

                    # each uuid in the dsvmkey list is passed to the find_match
                    # function to look for a match

                    if REGISTER_VMX:
                        orphanedVmCount = len(REGISTER_VMX)
                    else:
                        print("THREAD MAIN - No VMX found to be registered in VC %s."%host)
                        final_result['Result'] = "No VMX found to be registered in VC %s."%host
                        final_result['status'] = status.HTTP_412_PRECONDITION_FAILED
                        continue







#########################VM Register Operation Ends#####################################


######################## VM New Power Operation #####################################

@request.restful()
def vmpowerops():
    response.view = 'generic.json'
    runTime = datetime.datetime.now().strftime("%d-%m-%y:%H:%M:%S")

    def POST(*args, **vars):
        jsonBody = request.vars
        # print "%s - Debug 1 - vm_0 - initial JSONObj %s "%(runTime,str(jsonBody))
        try:
            if jsonBody is None:
                resp = "No request body"
                return dict(error=resp, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                vm_ops_json = json.dumps(jsonBody)
                # print "%s - Debug 2 - vm_0 - After Dump JSONObj %s" % (runTime, str(vc_mem_json))
                vm_ops_json_data = json.loads(vm_ops_json)
                super_operation_type = vm_ops_json_data['operation']
                vmops_launchid = datetime.datetime.now().strftime("%d%m%y%H%M%S")
                vmops_launchdate = datetime.datetime.now()
                vmops_launchby = "External Client"
                operation_type = "vmpowerops"
                final_return_dict = {}
                final_return_dict["Operation"] = super_operation_type
                if vm_ops_json_data['operation'] == "vmpowerops":
                    db.opstatus.insert(launchid=vmops_launchid, launchdate=vmops_launchdate,
                                       launchby=vmops_launchby, opstype=operation_type, opsdata=vm_ops_json_data)
                    db.commit()
                    #result_url = "http://rip.eng.vmware.com/opStatus/opstats?queryfield=%s" % str(vcops_launchid)

                    result_url = "http://%s/opStatus/opstats?queryfield=%s" % (response.app_uri,str(vmops_launchid))
                    return dict(Results=result_url, status=status.HTTP_200_OK)
                else:
                    return dict(Results="JSON Validation Error.Check Key Value Error.",
                                status=status.HTTP_412_PRECONDITION_FAILED)

        except Exception, e:
            return dict(error=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return locals()



##################### VM New Power Operation Ends #################################


##############################  VM Clone Operation ################################

@request.restful()
def vmclone():
    response.view = 'generic.json'
    runTime = datetime.datetime.now().strftime("%d-%m-%y:%H:%M:%S")
    def POST(*args, **vars):
        jsonBody = request.vars
        # print "%s - Debug 1 - vm_0 - initial JSONObj %s "%(runTime,str(jsonBody))
        try:
            if jsonBody is None:
                resp = "No request body"
                return dict(error=resp, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            else:
                vm_ops_json = json.dumps(jsonBody)
                # print "%s - Debug 2 - vm_0 - After Dump JSONObj %s" % (runTime, str(vc_mem_json))
                vm_ops_json_data = json.loads(vm_ops_json)
                super_operation_type = vm_ops_json_data['operation']
                vmops_launchid = datetime.datetime.now().strftime("%d%m%y%H%M%S")
                vmops_launchdate = datetime.datetime.now()
                vmops_launchby = "External Client"
                operation_type = "vmclones"
                final_return_dict = {}
                final_return_dict["Operation"] = super_operation_type
                if vm_ops_json_data['operation'] == "vmclones":
                    db.opstatus.insert(launchid=vmops_launchid, launchdate=vmops_launchdate,
                                       launchby=vmops_launchby, opstype=operation_type, opsdata=vm_ops_json_data)
                    db.commit()
                    #result_url = "http://rip.eng.vmware.com/opStatus/opstats?queryfield=%s" % str(vcops_launchid)

                    result_url = "http://%s/opStatus/opstats?queryfield=%s" % (response.app_uri,str(vmops_launchid))
                    return dict(Results=result_url, status=status.HTTP_200_OK)
                else:
                    return dict(Results="JSON Validation Error.Check Key Value Error.",
                                status=status.HTTP_412_PRECONDITION_FAILED)

        except Exception, e:
            return dict(error=str(e), status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return locals()

##################################################################################
