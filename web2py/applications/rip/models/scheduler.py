__author__ = 'smrutim'

import time
import re
import traceback
from customSSH import RunCmdOverSSH
from misc import DownloadFileFromVC, DownloadVCCore
from pyVim.connect import SmartConnect
from pyVim.connect import Disconnect
import atexit
import ssl
import vcenter
import requests
import json
import ast
from gluon.scheduler import Scheduler
import re
import multiprocessing
from multiprocessing.dummy import Pool as ThreadPool

"""
status=local_import('status')
customSSH = local_import('customSSH')
HeapCoreModules = local_import('HeapCoreModules')
chapMaster = local_import('chapMaster')
ah64Master = local_import('ah64Master')


from customSSH import RunCmdOverSSH
from HeapCoreModules import _CreateAnalysisDirectory, _PushMemoryJar, _TakeHeapDump
from chapMaster import _DownloadChapToVC,RunChap
"""

import customSSH
import status
import chapMaster
import ah64Master
import HeapCoreModules
import VmOperations

scheduler = Scheduler(db)
if False:
    from gluon import *

    request = current.request
    response = current.response
    session = current.session
    cache = current.cache
    T = current.T

################## VM Operation : Power Operation ###################

# vm_power_op_url = "http://127.0.0.1:8000/rip/vm_0/vmPowerOperation"

"""
vm_power_op_url = "http://10.172.46.209/rip/vm_0/vmpoweroperation"


def initiate_vm_power_scheduler(vmPowerOps_row_id):
    vm_power_opstatus_rows = db(db.opstatus.id == vmPowerOps_row_id).select()
    for vm_power_opstatus_row in vm_power_opstatus_rows:
        vm_power_opstatus_row_data = ast.literal_eval(vm_power_opstatus_row.opsdata)

        vm_power_opstatus_row.update_record(status="Queued")
        db.commit()
        vm_power_opstatus_row.update_record(statusdetail="Waiting")
        db.commit()
        power_response = requests.post(vm_power_op_url, json=vm_power_opstatus_row_data)
        status = str(power_response.status_code)
        detail_status = str(power_response.content)
        vm_power_opstatus_row.update_record(status=status)
        db.commit()
        vm_power_opstatus_row.update_record(statusdetail=detail_status)
        db.commit()


vmPowerOps_rows = db((db.opstatus.status == "Initiated") & (db.opstatus.opstype == "vmpowerops")).select()

for vmPowerOps_row in vmPowerOps_rows:
    vmPowerOps_row.update_record(status="Running")
    db.commit()
    vmPowerOps_row.update_record(statusdetail="Running")
    db.commit()
    vmPowerOps_row_id = vmPowerOps_row.id
    scheduler.queue_task(initiate_vm_power_scheduler, pvars=dict(vmPowerOps_row_id=vmPowerOps_row_id), timeout=180)

"""


################## VM Operation : Power Operation Ends ###################

######################### Code to Make Heap Analysis Faster ####################


def _InitiateHeapAnalysis(vcHeap_row_id, host, username, password, jmapPath, dumpDir, service_name, hprofname):
    vc_heap_opstatus_rows = db(db.opstatus.id == vcHeap_row_id).select()
    for vc_heap_opstatus_row in vc_heap_opstatus_rows:
        HeapResults = {}
        try:
            if dumpDir:
                dumpDir = dumpDir + "rip/"
                remDir = "rm -rf " + dumpDir
                try:
                    vc_heap_opstatus_row.update_record(statusdetail="Removing Master Dump directory,if exists.")
                    db.commit()
                    (ret, stdout, stderr) = RunCmdOverSSH(remDir, host, username, password)
                    if ret != 0:
                        raise Exception(str(stderr))
                except Exception, e:
                    HeapResults["Failure"] = "Removing Master Dump directory failed due to %s" % str(e)
                    return HeapResults

                dirCreateCmd = "mkdir -p " + dumpDir

                try:
                    vc_heap_opstatus_row.update_record(statusdetail="Creating Master Dump Analysis directory .")
                    db.commit()
                    (ret, stdout, stderr) = RunCmdOverSSH(dirCreateCmd, host, username, password)
                    if ret != 0:
                        raise Exception(str(stderr))
                except Exception, e:
                    HeapResults["Failure"] = "Master Dump directory creation. %s" % str(e)
                    return HeapResults

                if hprofname:
                    filelistCmd = "ls -l " + hprofname
                    vc_heap_opstatus_row.update_record(statusdetail="Checking User specifed HPROF.")
                    db.commit()
                    try:
                        (ret, stdout, stderr) = RunCmdOverSSH(filelistCmd, host, username, password)
                        if ret != 0:
                            raise Exception(str(stderr))
                    except Exception, e:
                        HeapResults["Failure"] = "User specifed HPROF could not be listed. %s." % str(e)
                        return HeapResults

                if service_name[0] == "all":
                    service_name = ['vsphere-client', 'vsphere-ui', 'vmware-certificatemanagement',
                                    'vmware-content-library',
                                    'vmware-vapi-endpoint', 'vmware-eam', 'vmware-vpxd-svcs', 'vmware-cis-license',
                                    'vmware-sps']
                else:
                    service_name = service_name

                jarPath = None
                try:
                    vc_heap_opstatus_row.update_record(statusdetail="Getting Utility Jars for Heap Analysis.")
                    db.commit()
                    jarPath = HeapCoreModules._PushMemoryJar(dumpDir, host, username, password)
                except Exception, e:
                    HeapResults["Failure"] = "Memory Analysis jar is not available on VC %s " % str(e)
                    return HeapResults

                try:
                    vc_heap_opstatus_row.update_record(statusdetail="Initiating Heap Analysis.")
                    db.commit()
                    finalResults = HeapCoreModules._TriggerHeapAnalysis(host, username, password, jmapPath,
                                                                        dumpDir, jarPath, service_name, hprofname)


                except Exception, e:
                    HeapResults["Failure"] = "Memory Analysis Failed on VC %s " % str(e)
                    return HeapResults

                HeapResults["heapanalysis"] = finalResults

                return HeapResults


            else:
                HeapResults["Failure"] = "No Master Dump directory specified."
                return HeapResults

        except Exception, e:
            HeapResults["Failure"] = str(e)
            return HeapResults


##########################Code to Make Heap Analysis Faster Ends#################

################## VC Operation : Heap Analysis Begins ###################

def initiate_vc_heap_scheduler(vcHeap_row_id):
    vc_heap_opstatus_rows = db(db.opstatus.id == vcHeap_row_id).select()
    final_return_dict = {}
    vac_status = ""
    remarks = ""
    for vc_heap_opstatus_row in vc_heap_opstatus_rows:
        launchid = vc_heap_opstatus_row.launchid
        try:
            vc_heap_opstatus_row_data = ast.literal_eval(vc_heap_opstatus_row.opsdata)
            vc_heap_opstatus_row.update_record(status="Queued")
            db.commit()
            vc_heap_opstatus_row.update_record(statusdetail="Waiting")
            db.commit()
            try:
                vc_mem_json = json.dumps(vc_heap_opstatus_row_data)
                vc_ops_json_data = json.loads(vc_mem_json)
                super_operation_type = vc_ops_json_data['operation']
                vc_dict = vc_ops_json_data['vc']

                statusCode = None
                final_return_dict["Operation"] = super_operation_type
                for vc_item in vc_dict:
                    host = vc_item['vcname']
                    username = vc_item['username']
                    password = vc_item['password']
                    jmapPath = vc_item['jmapPath']
                    dumpDir = vc_item['dumpDir']
                    service_name = vc_item['service']
                    hprofname = vc_item.get('hprof', None)

                    statusCode = str(status.HTTP_202_ACCEPTED)
                    vc_heap_opstatus_row.update_record(status=statusCode)
                    db.commit()
                    vc_heap_opstatus_row.update_record(statusdetail=host + " Heap Analysis In Progress")
                    db.commit()

                    try:
                        final_return_dict[host] = _InitiateHeapAnalysis(vcHeap_row_id, host, username, password,
                                                                        jmapPath, dumpDir,
                                                                        service_name, hprofname)
                    except Exception, e:
                        statusCode = str(status.HTTP_500_INTERNAL_SERVER_ERROR)
                        vc_heap_opstatus_row.update_record(status=statusCode)
                        db.commit()
                        vc_heap_opstatus_row.update_record(statusdetail=str(e))
                        db.commit()

            except Exception, e:
                statusCode = str(status.HTTP_500_INTERNAL_SERVER_ERROR)
                vc_heap_opstatus_row.update_record(status=statusCode)
                db.commit()
                vc_heap_opstatus_row.update_record(statusdetail=str(e))
                db.commit()
        except Exception, e:
            statusCode = str(status.HTTP_500_INTERNAL_SERVER_ERROR)
            vc_heap_opstatus_row.update_record(status=statusCode)
            db.commit()
            vc_heap_opstatus_row.update_record(statusdetail=str(e))
            db.commit()

        statusCode = str("Completed")
        vc_heap_opstatus_row.update_record(status=statusCode)
        db.commit()
        vc_heap_opstatus_row.update_record(statusdetail=json.dumps(final_return_dict))
        db.commit()

        # Post Heap Analysis Data To VAC

        '''

        heap_header_temp = """
        {
            "@id"           :   "RIP_HEAP_ANALYSIS_STAGING_PRODUCTION",
            "@type"         :   "heap_analysis_table_staging_production",
            "name"          :   "Heap Analysis Table Staging production",
            "desciption"    :   "This staging production schema maintains the Historical Heap Analysis Data of All vCenter Java services",
            "vc"            :   [ 
                                    %(VC_DATA)s
                                ]



        }
        """

        vc_data_temp = """
                    {
                    "vcname"    :   "%(VC_NAME)s",
                    "vcbuild"   :   "%(VC_BUILD)s",
                    "uptime"    :   "%(UPTIME)s",
                    "services"  :   [
                                        %(SERVICES_DATA)s            
                                    ]           
                    }
        """

        service_data_temp = """
                    {
                        "name"              :   "%(SERVICE_NAME)s",
                        "%(SERVICE_NAME)s"  : [
                                                %(LEAKS_DATA)s
                                              ] 
                    }

        """

        leak_data_temp = """
                        {

                            "suspect"           :   "%(SUSPECT_NUM)s",
                            "instancename"      :   "%(INSTANCE_NAME)s",
                            "bytesleak"         :   %(BYTESLEAK)s,
                            "numberinstance"    :   %(INSTANCE_NUM)s,
                            "loadedby"          :   "%(LOADEDBY)s"
                        }
        """

        vc_data_post = ""

        try:
            for k, v in final_return_dict.iteritems():
                VC_NAME = ""
                if k == "Operation":
                    pass
                else:
                    VC_NAME = k
                    UPTIME = ""
                    VC_BUILD = ""
                    service_data_post = ""

                    for heapanalysis_key, heapanalysis_value in v.iteritems():
                        if "heapanalysis" in heapanalysis_key:
                            for heap_key, heap_value in heapanalysis_value.iteritems():

                                if "Uptime" in heap_key:
                                    UPTIME = heap_value
                                elif "Build" in heap_key:
                                    VC_BUILD = heap_value
                                elif "Result" in heap_key:
                                    service_data_post = ""
                                    for service_key, service_value in heap_value.iteritems():
                                        SERVICE_NAME = service_key
                                        leak_data_post = ""
                                        if not isinstance(service_value, dict):
                                            continue
                                        for leak_key, leak_value in service_value.iteritems():
                                            SUSPECT_NUM = leak_key
                                            INSTANCE_NAME = ""
                                            BYTESLEAK = ""
                                            INSTANCE_NUM = ""
                                            LOADEDBY = ""
                                            if "Leak Suspect 0" in leak_key:
                                                continue
                                            elif not isinstance(leak_value, dict):
                                                continue

                                            for instance_key, instance_value in leak_value.iteritems():

                                                if "Instance Name" in instance_key:
                                                    INSTANCE_NAME = instance_value
                                                elif "Bytes" in instance_key:
                                                    BYTESLEAK = int(instance_value.replace(",", ""))
                                                elif "Number of Instance" in instance_key:
                                                    if instance_value.lower() == "one":
                                                        INSTANCE_NUM = 1
                                                    else:
                                                        INSTANCE_NUM = int(instance_value.replace(",", ""))
                                                elif "Loaded By" in instance_key:
                                                    LOADEDBY = instance_value

                                            leak_data_post = leak_data_post + "," + leak_data_temp % {
                                                "SUSPECT_NUM": SUSPECT_NUM, "INSTANCE_NAME": INSTANCE_NAME,
                                                "BYTESLEAK": BYTESLEAK, "INSTANCE_NUM": INSTANCE_NUM,
                                                "LOADEDBY": LOADEDBY}

                                        service_data_post = service_data_post + "," + service_data_temp % {
                                            "SERVICE_NAME": SERVICE_NAME, "LEAKS_DATA": leak_data_post.strip(",")}

                        vc_data_post = vc_data_post + "," + vc_data_temp % {"VC_NAME": VC_NAME, "VC_BUILD": VC_BUILD,
                                                                            "UPTIME": UPTIME,
                                                                            "SERVICES_DATA": service_data_post.strip(
                                                                                ",")}

            heap_vac_data = heap_header_temp % {"VC_DATA": vc_data_post.strip(",")}

            # Request Body Format
            body_format = {'Content-Type': 'application/json'}
            response = ""
            uri = "https://vcsa.vmware.com/ph-stg/api/hyper/send?_c=cpbu_vcst_vac_staging.v0&_i=REST_IN_PEAK_STAGING_PRODUCTION"

            response = requests.post(uri, data=heap_vac_data, verify=False, headers=body_format)
            vac_status = str(response.status_code)
            if vac_status == "201":
                remarks = "Posted"
            else:
                remarks = "Post Data could not be sent to VAC."

        except Exception, e:
            vac_status = "500"
            remarks = "Could not post Heap Analysis Data to VAC " + str(e)

        # Update VAC Post Database

        try:
            db.vacpoststatus.insert(launchid=launchid, poststatus=remarks, responsecode=vac_status)
            db.commit()

            # Mark Collect Matric to Be Completed

            vc_heap_opstatus_row.update_record(analystics="Done")
            db.commit()
        except Exception, e:
            pass
        '''


vcHeap_rows = db((db.opstatus.status == "Initiated") & (db.opstatus.opstype == "heapanalysis")).select()

for vcHeap_row in vcHeap_rows:
    vcHeap_row.update_record(status="Running")
    db.commit()
    vcHeap_row.update_record(statusdetail="Running")
    db.commit()
    vcHeapAnalysis_row_id = vcHeap_row.id

    scheduler.queue_task(initiate_vc_heap_scheduler, pvars=dict(vcHeap_row_id=vcHeapAnalysis_row_id), timeout=72000)


################## VC Operation : Heap Analysis Ends ###################

################## VC Operation : Memory Leak Analysis Begins ###################


# vc_mem_analysis_url = "http://10.172.109.50/rip/vc_0/vcmemleak"

def initiate_memLeak_scheduler(vcMem_row_id):
    vc_memory_opstatus_rows = db(db.opstatus.id == vcMem_row_id).select()

    for vc_memory_opstatus_row in vc_memory_opstatus_rows:
        try:
            launchid = vc_memory_opstatus_row.launchid
            vc_memory_opstatus_row_data = ast.literal_eval(vc_memory_opstatus_row.opsdata)

            # Debug
            db.schedulerdebug.insert(launchid=vc_memory_opstatus_row.launchid,
                                     opsidentifier="Debug Mem Leak inside func",
                                     debugdata=vc_memory_opstatus_row_data)
            db.commit()

            vc_memory_opstatus_row.update_record(status="Queued")
            db.commit()
            vc_memory_opstatus_row.update_record(statusdetail="Waiting")
            db.commit()
            try:
                vc_mem_json = json.dumps(vc_memory_opstatus_row_data)
                vc_ops_json_data = json.loads(vc_mem_json)
                super_operation_type = vc_ops_json_data['operation']
                vc_dict = vc_ops_json_data['vc']
                final_return_dict = {}

                final_return_dict["Operation"] = super_operation_type
                for vc_item in vc_dict:
                    vcName = vc_item['vcname']
                    vcUser = vc_item['username']
                    vcPwd = vc_item['password']
                    service_names_input = vc_item['service']

                    implemented_services = ['analytics', 'applmgmt',
                                            'hvc', 'imagebuilder', 'lookupsvc', 'mbcs', 'netdumper', 'perfcharts',
                                            'pschealth', 'rbd', 'rhttpproxy', 'sca', 'statsmonitor', 'trustmanagement',
                                            'updatemgr', 'vcha', 'vmcam', 'vmonapi', 'vmware-postgres-archiver',
                                            'vmware-vpostgres', 'vsan-dps', 'vsan-health', 'vsm', 'sps']
                    service_name = []

                    if service_names_input[0] == "all":
                        service_name = implemented_services
                    else:
                        for s in service_names_input:
                            service_name.append(s)

                    statusCode = str(status.HTTP_202_ACCEPTED)
                    vc_memory_opstatus_row.update_record(status=statusCode)
                    db.commit()
                    vc_memory_opstatus_row.update_record(statusdetail=vcName + " Analysis In Progress")
                    db.commit()

                    try:
                        final_return_dict[vcName] = chapMaster.CheckMemLeak(vcName, vcUser, vcPwd, service_name)
                    except Exception, e:
                        statusCode = str(status.HTTP_500_INTERNAL_SERVER_ERROR)
                        vc_memory_opstatus_row.update_record(status=statusCode)
                        db.commit()
                        vc_memory_opstatus_row.update_record(statusdetail=str(e))
                        db.commit()

                statusCode = str("Completed")
                vc_memory_opstatus_row.update_record(status=statusCode)
                db.commit()
                vc_memory_opstatus_row.update_record(statusdetail=json.dumps(final_return_dict))
                db.commit()

                # Posting Data To VAC

                '''

                meam_leak_vac_template = """
                {
                	"@id"			:	"RIP_OTHER_SERVICES_MEMORY_LEAK_STAGING_PRODUCTION",
                	"@type"			:	"other_services_leak_table_staging_production",
                	"name"			:	"other Services Memory Leak Staging Production",
                	"desciption"	: 	"This second Staging Production schema maintains the Historical Memory Leak Data of All C and CPP services except VPXD across Builds and Teams",

                	"vc" : [ %(VC_DATA)s]

                }

                """

                vc_data_template = """
                    {

                		"vcname" 	: 	 "%(VC_NAME)s",
                		"vcbuild" 	:	 "%(VC_BUILD)s",
                		"uptime"    :    "%(UPTIME)s",		
                		"services" 	: [

                			%(MEM_LEAK_DATA)s	


                		]		

                	}

                """

                mem_leak_service_template = """
                            {				
                				    "servicename" 	: "%(SERVICE_NAME)s",
                					"chunks"        : %(CHUNKS)s,
                					"bytes"	        : %(BYTES_LEAK)s	

                			}

                """

                VC_POST_DATA = ""
                vac_status = ""
                remarks = ""

                try:
                    for k, v in final_return_dict.iteritems():
                        VC_NAME = ""

                        MEM_LEAK_DATA = ""
                        VC_BUILD = ""

                        UPTIME = ""

                        if k == "Operation":
                            pass
                        else:
                            VC_NAME = k
                            VC_BUILD = ""

                            for vc_data, vc_value in v.iteritems():
                                if "Uptime" in vc_data:
                                    UPTIME = vc_value
                                elif "Build" in vc_data:
                                    VC_BUILD = vc_value
                                elif "Leaks" in vc_data:
                                    for ser_data, ser_value in vc_value.iteritems():

                                        SERVICE_NAME = ser_data.strip()
                                        CHUNKS = ""
                                        BYTES_LEAK = ""

                                        for leak_key, leak_value in ser_value.iteritems():
                                            if "Chunks" in leak_key:
                                                CHUNKS = leak_value

                                            elif "Leak" in leak_key:
                                                m = re.search('.*?\((.*)?\)', leak_value)
                                                if m:
                                                    BYTES_LEAK = int(m.group(1).replace(",", ""))
                                                else:
                                                    BYTES_LEAK = "ERROR"
                                            else:
                                                pass

                                        MEM_LEAK_DATA = MEM_LEAK_DATA + "," + mem_leak_service_template % {
                                            "SERVICE_NAME": SERVICE_NAME, "CHUNKS": CHUNKS, "BYTES_LEAK": BYTES_LEAK}

                            VC_POST_DATA = VC_POST_DATA + "," + vc_data_template % {"VC_NAME": VC_NAME,
                                                                                    "VC_BUILD": VC_BUILD,
                                                                                    "MEM_LEAK_DATA": MEM_LEAK_DATA.strip(
                                                                                        ","), "UPTIME": UPTIME}

                    meam_leak_vac_post = meam_leak_vac_template % {"VC_DATA": VC_POST_DATA.strip(",")}
                    # Request Body Format
                    body_format = {'Content-Type': 'application/json'}
                    response = ""
                    uri = "https://vcsa.vmware.com/ph-stg/api/hyper/send?_c=cpbu_vcst_vac_staging.v0&_i=REST_IN_PEAK_STAGING_PRODUCTION"
                    response = requests.post(uri, data=meam_leak_vac_post, verify=False, headers=body_format)
                    vac_status = str(response.status_code)
                    if vac_status == "201":
                        remarks = "Posted"
                    else:
                        remarks = "Data could not be sent to VAC."

                except Exception, e:
                    vac_status = str(500)
                    remarks = "Could Not Post C Services Leak Analysis to Telemetry due to " + str(e)

                # Update VAC Post Database

                try:
                    db.vacpoststatus.insert(launchid=launchid, poststatus=remarks, responsecode=vac_status)
                    db.commit()
                    # Mark Collect Matric to Be Completed

                    vc_memory_opstatus_row.update_record(analystics="Done")
                    db.commit()
                except Exception, e:
                    pass
                '''


            except Exception, e:
                statusCode = str(status.HTTP_500_INTERNAL_SERVER_ERROR)
                vc_memory_opstatus_row.update_record(status=statusCode)
                db.commit()
                vc_memory_opstatus_row.update_record(statusdetail=str(e))
                db.commit()

                # Debug
                # db.schedulerdebug.insert(launchid=vc_memory_opstatus_row.launchid,   opsidentifier="Error in Debug Mem Leak inside func",        debugdata=str(e))
                # db.commit()

        except Exception, e:
            statusCode = str(status.HTTP_500_INTERNAL_SERVER_ERROR)
            vc_memory_opstatus_row.update_record(status=statusCode)
            db.commit()
            vc_memory_opstatus_row.update_record(statusdetail=str(e))
            db.commit()
            # Debug
            # db.schedulerdebug.insert(launchid=vc_memory_opstatus_row.launchid, opsidentifier="Final Error in Debug Mem Leak inside func",   debugdata=str(e))
            # db.commit()


vcMem_rows = db((db.opstatus.status == "Initiated") & (db.opstatus.opstype == "memoryleak")).select()

for vcMem_row in vcMem_rows:
    vcMem_row.update_record(status="Running")
    db.commit()
    vcMem_row.update_record(statusdetail="Running")
    db.commit()
    vcMem_row_id = vcMem_row.id
    # db.schedulerdebug.insert(launchid=vcMem_row.launchid,     opsidentifier="Debug Memory Leaks",  debugdata="Initiating Scheduler")
    # db.commit()
    scheduler.queue_task(initiate_memLeak_scheduler, pvars=dict(vcMem_row_id=vcMem_row_id), timeout=7200)


################## VC Operation : Memory Leak Analysis Ends ###################


################## VC Operation : VPXD Memory Leak Analysis Begins ###################

def initiate_vpxdmemleak_scheduler(vpxMem_row_id):
    vc_vpxdLeaks_opstatus_rows = db(db.opstatus.id == vpxMem_row_id).select()
    for vc_vpxdLeaks_opstatus_row in vc_vpxdLeaks_opstatus_rows:
        vc_memory_opstatus_row_data = ast.literal_eval(vc_vpxdLeaks_opstatus_row.opsdata)
        launchid = vc_vpxdLeaks_opstatus_row.launchid
        vc_vpxdLeaks_opstatus_row.update_record(status="Queued")
        db.commit()
        vc_vpxdLeaks_opstatus_row.update_record(statusdetail="Waiting")
        db.commit()
        try:
            vc_mem_json = json.dumps(vc_memory_opstatus_row_data)
            vc_ops_json_data = json.loads(vc_mem_json)
            super_operation_type = vc_ops_json_data['operation']
            vc_dict = vc_ops_json_data['vc']
            final_return_dict = {}
            statusCode = None
            final_return_dict["Operation"] = super_operation_type
            for vc_item in vc_dict:
                host = vc_item['vcname']
                username = vc_item['username']
                password = vc_item['password']
                try:
                    vc_vpxdLeaks_opstatus_row.update_record(status="In Progress")
                    db.commit()
                    vc_vpxdLeaks_opstatus_row.update_record(statusdetail="Downloading Chap to VC " + host)
                    db.commit()
                    chapPath = chapMaster._DownloadChapToVC(host, username, password)
                    vc_vpxdLeaks_opstatus_row.update_record(statusdetail="CHAP Downloaded in VC " + host)
                    db.commit()

                    if chapPath is None:
                        statusCode = status.HTTP_412_PRECONDITION_FAILED
                        msg = "CHAP could not be downloaded."
                        vpxdMemLeakResult = str(statusCode) + "," + msg
                        final_return_dict[host] = vpxdMemLeakResult
                        continue

                    vc_vpxdLeaks_opstatus_row.update_record(statusdetail="Generating core in VC " + host)
                    db.commit()
                    generate_core_cmd = "/usr/lib/vmware-vmon/vmon-cli -d vpxd"
                    (ret, stdout, stderr) = customSSH.RunCmdOverSSH(generate_core_cmd, host, username, password)
                    s = "Completed dump service livecore request"
                    core_file_path = None
                    if stdout and s in stdout and ret == 0:
                        core_file_path = stdout.split()[-1]
                        vc_vpxdLeaks_opstatus_row.update_record(statusdetail="vpxd core generated in VC " + host)
                        db.commit()
                    elif ret is None:
                        statusCode = status.HTTP_412_PRECONDITION_FAILED
                        msg = "Timeout while generating core"
                        vpxdMemLeakResult = str(statusCode) + "," + msg
                        final_return_dict[host] = vpxdMemLeakResult
                        continue
                    else:
                        if ret == 4:
                            statusCode = status.HTTP_412_PRECONDITION_FAILED
                            msg = "Service not running on VC"
                            vpxdMemLeakResult = str(statusCode) + "," + msg
                            final_return_dict[host] = vpxdMemLeakResult
                            continue
                    if core_file_path:
                        resDict = {}
                        vc_vpxdLeaks_opstatus_row.update_record(statusdetail="Analysing vpxd core in VC " + host)
                        db.commit()
                        chapCmd = "echo count leaked | %s %s" % (chapPath, core_file_path)
                        (ret, stdout, stderr) = chapMaster.RunChap("vpxd", chapCmd, host, username, password)
                        p = re.compile("\s*(\d+)\s+allocations\s+use(.*)?bytes.*")
                        m = p.match(stdout)
                        if m:
                            # print("THREAD - %s - Analysis Result %s" % (service, m.group(0)))
                            resDict['Chunks'] = m.group(1)
                            resDict['Memory Leak (Bytes)'] = m.group(2)
                            # Code for uptime.
                            try:
                                uptimecmd = "uptime -p"
                                (ret, stdout, stderr) = RunCmdOverSSH(uptimecmd, host, username, password)
                                if ret != 0:
                                    resDict["Uptime"] = str(stderr)
                                else:
                                    resDict["Uptime"] = str(stdout)
                            except Exception, e:
                                resDict["Uptime"] = "Could not obtain duration of uptime %s." % str(e)

                            try:
                                uptimecmd = "grep 'BUILDNUMBER' /etc/vmware/.buildInfo | cut -d\":\" -f2"
                                (ret, stdout, stderr) = RunCmdOverSSH(uptimecmd, host, username, password)
                                if ret != 0:
                                    resDict["Build"] = str(stderr)
                                else:
                                    resDict["Build"] = str(stdout)
                            except Exception, e:
                                resDict["Build"] = "Could not obtain Build %s." % str(e)

                            final_return_dict[host] = resDict
                            statusCode = str(status.HTTP_200_OK)



                except Exception, e:
                    statusCode = status.HTTP_412_PRECONDITION_FAILED
                    vpxdMemLeakResult = str(statusCode) + "," + str(e)
                    final_return_dict[host] = vpxdMemLeakResult
                    continue
            vc_vpxdLeaks_opstatus_row.update_record(status=statusCode)
            db.commit()
            vc_vpxdLeaks_opstatus_row.update_record(statusdetail=json.dumps(final_return_dict))
            db.commit()

            # Posting Data to VAC

            '''
            

            vac_data = """
                         {
                "@id"		:	"RIP_VPXD_LEAK_STAGING_PRODUCTION",
                "@type"		:	"vpxd_leak_table_staging_production",
                "name"		: 	"VPXD Memory Leak Staging Production",
                "desciption": "This Staging Production schema maintains the Historical Memory Leak Data of VPXD across Builds and Teams",

                "vc" :                
                    [
                     %(VC_DATA)s
                    ]


            }
            """

            vc_data_template = """
                         {

                                "vcname" 		:	"%(VC_NAME)s",	
                                "build" 		: 	%(VC_BUILD)s,	
                                "uptime"		: 	"%(UPTIME)s",	
                                "chunks" 		: 	%(CHUNKS)s,
                                "bytesmemleak" 	: 	%(BYTES_LEAK)s


                        }
            """

            try:
                vc_data = ""
                uri = "https://vcsa.vmware.com/ph-stg/api/hyper/send?_c=cpbu_vcst_vac_staging.v0&_i=REST_IN_PEAK_STAGING_PRODUCTION"
                for k, v in final_return_dict.iteritems():
                    if k == "Operation":
                        pass
                    else:
                        VC_NAME = k
                        CHUNKS = ""
                        UPTIME = ""
                        VC_BUILD = ""
                        BYTES_LEAK = ""
                        for leak_key, leak_value in v.iteritems():
                            if "Chunks" in leak_key:
                                CHUNKS = leak_value
                            elif "Uptime" in leak_key:
                                UPTIME = leak_value
                            elif "Build" in leak_key:
                                VC_BUILD = leak_value
                            elif "Memory" in leak_key:
                                m = re.search('.*?\((.*)?\)', leak_value)
                                if m:
                                    BYTES_LEAK = int(m.group(1).replace(",", ""))
                                else:
                                    BYTES_LEAK = "ERROR"
                            else:
                                pass
                        vc_data = vc_data + "," + vc_data_template % {"VC_NAME": VC_NAME, "CHUNKS": CHUNKS,
                                                                      "VC_BUILD": VC_BUILD, "BYTES_LEAK": BYTES_LEAK,
                                                                      "UPTIME": UPTIME}

                VC_DATA = vc_data.strip(",")

                vac_data = vac_data % {"VC_DATA": VC_DATA}

                # Request Body Format
                body_format = {'Content-Type': 'application/json'}
                response = ""
                try:
                    response = requests.post(uri, data=vac_data, verify=False, headers=body_format)
                    vac_status = str(response.status_code)
                    if vac_status == "201":
                        remarks = "Posted"
                    else:
                        remarks = "Data could not be sent to VAC."
                except Exception, e1:
                    vac_status = str(response.status_code)
                    remarks = "Could Not Post VPXD Leak Analysis to Telemetry due to " + str(e1)

                db.vacpoststatus.insert(launchid=launchid, poststatus=remarks, responsecode=vac_status)
                db.commit()

            except Exception, e:
                remarks = "Could Not Post VPXD Leak Analysis to Telemetry due to " + str(e)
                db.vacpoststatus.insert(launchid=launchid, poststatus=remarks, responsecode=503)
                db.commit()

            # Mark Collect Matric to Be Completed

            vc_vpxdLeaks_opstatus_row.update_record(analystics="Done")
            db.commit()
            '''



        except Exception, e:
            vc_vpxdLeaks_opstatus_row.update_record(status="412")
            db.commit()
            vc_vpxdLeaks_opstatus_row.update_record(statusdetail=str(e))
            db.commit()
        




vpxMem_rows = db((db.opstatus.status == "Initiated") & (db.opstatus.opstype == "vpxdmemleak")).select()

for vpxMem_row in vpxMem_rows:
    vpxMem_row.update_record(status="Running")
    db.commit()
    vpxMem_row.update_record(statusdetail="Running")
    db.commit()
    vpxMem_row_id = vpxMem_row.id

    scheduler.queue_task(initiate_vpxdmemleak_scheduler, pvars=dict(vpxMem_row_id=vpxMem_row_id), timeout=3600)


################## VC Operation : VPXD Memory Leak Analysis Ends ###################


################## VC Operation : Memory Growth Analysis Begins ###################

# vc_mem_growth_url = "http://10.172.109.50/rip/vc_0/vcmemgrowth"

def initiate_memGrowth_scheduler(vcMem_row_id):
    vc_memory_opstatus_rows = db(db.opstatus.id == vcMem_row_id).select()

    for vc_memory_opstatus_row in vc_memory_opstatus_rows:
        try:
            vc_memory_opstatus_row_data = ast.literal_eval(vc_memory_opstatus_row.opsdata)
            vc_memory_opstatus_row.update_record(status="Queued")
            db.commit()
            vc_memory_opstatus_row.update_record(statusdetail="Waiting")
            db.commit()
            try:
                vc_mem_json = json.dumps(vc_memory_opstatus_row_data)
                vc_ops_json_data = json.loads(vc_mem_json)
                super_operation_type = vc_ops_json_data['operation']
                vc_dict = vc_ops_json_data['vc']
                final_return_dict = {}
                statusCode = None
                final_return_dict["Operation"] = super_operation_type

                for vc_item in vc_dict:
                    vcName = vc_item["vcname"]
                    vcUser = vc_item["ssh_user"]
                    vcPwd = vc_item["ssh_pass"]
                    vcLocalUser = vc_item["local_user"]
                    vcLocalPwd = vc_item["local_pass"]
                    vcBuild = vc_item["vc_build"]
                    vcVersion = vc_item["vc_version"]
                    """
                    current_result = ah64Master.CheckMemGrowth(vcName, vcUser, vcPwd, vcLocalUser, vcLocalPwd,
                                                               vcVersion, vcBuild)
                    """

                    MemGrowthDict = {}

                    try:

                        vc_memory_opstatus_row.update_record(status="In Progress")
                        db.commit()
                        vc_memory_opstatus_row.update_record(statusdetail="Downloading AH64 to VC")
                        db.commit()
                        remoteAh64Path = ah64Master._DownloadAH64ToVC(vcName, vcUser, vcPwd)
                        # Inventory Object map with (obj type , obj name) records
                        invtObjMap = {'vim.Datastore': 'Datastore', 'vim.Folder': 'Folder', \
                                      'vim.VirtualMachine': 'Vm', 'vim.HostSystem': 'Host', 'vim.Network': 'Network'}
                        si = None
                        try:
                            # print("Getting connection to Vcenter")
                            si = ah64Master.GetSI(vcName, vcLocalUser, vcLocalPwd)
                            atexit.register(Disconnect, si)
                            # print("Successfully got connection to VC %s"% vc)
                        except Exception, e:
                            return "Error while connecting: " + str(e)

                        vc_memory_opstatus_row.update_record(status="In Progress")
                        db.commit()
                        vc_memory_opstatus_row.update_record(statusdetail="Getting Inventory Objects count in VC")
                        db.commit()
                        invtCounts, moIdList = vcenter.GetObjectsCountInVCInventory(si, invtObjMap)

                        vc_memory_opstatus_row.update_record(status="In Progress")
                        db.commit()
                        vcMor = sorted(invtCounts.items())
                        MemGrowthDict["MOR in VC"] = vcMor
                        final_return_dict[vcName] = MemGrowthDict
                        vc_memory_opstatus_row.update_record(statusdetail=json.dumps(final_return_dict))
                        db.commit()

                        totalRetry = 2
                        numRetry = 1
                        moCounts = None
                        while (numRetry <= totalRetry):
                            try:
                                generate_core_cmd = "/usr/lib/vmware-vmon/vmon-cli -d vpxd"
                                (ret, stdout, stderr) = RunCmdOverSSH(generate_core_cmd, vcName, vcUser, vcPwd,
                                                                      timeout=1800)
                                s = "Completed dump service livecore request"
                                corefile = None
                                if stdout and s in stdout and ret == 0:
                                    corefile = stdout.split()[-1]

                                vc_memory_opstatus_row.update_record(status="In Progress")
                                db.commit()
                                vc_memory_opstatus_row.update_record(
                                    statusdetail="Corefile %s Generated in attempt %s" % (corefile, str(numRetry)))
                                db.commit()

                                try:

                                    vc_memory_opstatus_row.update_record(status="In Progress")
                                    db.commit()
                                    vc_memory_opstatus_row.update_record(
                                        statusdetail="Getting MOR count from corefile %s" % (corefile))
                                    db.commit()

                                    try:
                                        moCounts = ah64Master.GetVCMoCounts(vcName, vcUser, vcPwd, remoteAh64Path,
                                                                            corefile, vcVersion, vcBuild, invtObjMap)
                                    except Exception, e:
                                        statusCode = str(status.HTTP_412_PRECONDITION_FAILED)
                                        vc_memory_opstatus_row.update_record(status=statusCode)
                                        db.commit()
                                        vc_memory_opstatus_row.update_record(
                                            statusdetail="Could not get MOR count from core file in %s try. %s" % (
                                            str(numRetry), str(e)))
                                        db.commit()

                                    if not moCounts:
                                        errMsg = (
                                                    'Failed to run ah64 on %s, Managed Objects were returned as None' % vcName)
                                        statusCode = str(status.HTTP_412_PRECONDITION_FAILED)
                                        vc_memory_opstatus_row.update_record(status=statusCode)
                                        db.commit()
                                        vc_memory_opstatus_row.update_record(
                                            statusdetail="MOR count is None from core file in %s try. %s" % (
                                            str(numRetry), errMsg))
                                        db.commit()
                                        time.sleep(5)
                                        numRetry += 1
                                        continue

                                    vc_memory_opstatus_row.update_record(status="In Progress")
                                    db.commit()
                                    vc_memory_opstatus_row.update_record(
                                        statusdetail="Comparing MOR counts in live VC and core file" % (corefile))
                                    db.commit()

                                    countsMismatch, diffCounts = vcenter.CompareCounts(moCounts, invtCounts)

                                    if countsMismatch:
                                        MemGrowthDict["MOR in Core. Attempt #%s" % numRetry] = sorted(moCounts.items())
                                        time.sleep(5)
                                        numRetry += 1
                                    else:
                                        MemGrowthDict["MOR in Core. Attempt #%s" % numRetry] = sorted(moCounts.items())
                                        break

                                except Exception, e:
                                    statusCode = str(status.HTTP_500_INTERNAL_SERVER_ERROR)
                                    vc_memory_opstatus_row.update_record(status=statusCode)
                                    db.commit()
                                    vc_memory_opstatus_row.update_record(
                                        statusdetail="Could not get MOR count from core file due to error %s in attempt %s" % (
                                        str(e), str(numRetry)))
                                    db.commit()
                                    break
                            except Exception as e:
                                statusCode = str(status.HTTP_500_INTERNAL_SERVER_ERROR)
                                vc_memory_opstatus_row.update_record(status=statusCode)
                                db.commit()
                                vc_memory_opstatus_row.update_record(
                                    statusdetail="Corefile could not be generated due to serror %s in attempt %s" % (
                                    str(e), str(numRetry)))
                                db.commit()
                                break

                        if numRetry > totalRetry:
                            memoryGrowthMsg = "MEMORY GROWTH FOUND"
                            MemGrowthDict["Analysis"] = memoryGrowthMsg

                        else:
                            noMemoryGrowthMsg = ('No Memory Growth found after ATTEMPT# %s' % (numRetry))
                            MemGrowthDict["Analysis"] = noMemoryGrowthMsg

                        final_return_dict[vcName] = MemGrowthDict

                        statusCode = str("Completed")
                        vc_memory_opstatus_row.update_record(status=statusCode)
                        db.commit()
                        vc_memory_opstatus_row.update_record(statusdetail=json.dumps(final_return_dict))
                        db.commit()

                    except Exception, e:  # AH64 Download
                        statusCode = str(status.HTTP_412_PRECONDITION_FAILED)
                        vc_memory_opstatus_row.update_record(status=statusCode)
                        db.commit()
                        vc_memory_opstatus_row.update_record(
                            statusdetail="Downloading AH64 to VC failed due to error %s." % str(e))
                        db.commit()
                        break



            except Exception, e:  # JSON Validation
                vc_memory_opstatus_row.update_record(status="412")
                db.commit()
                vc_memory_opstatus_row.update_record(statusdetail="JSON vlaidation error " + str(e))
                db.commit()
                break
        except Exception, e:
            vc_memory_opstatus_row.update_record(status="412")
            db.commit()
            vc_memory_opstatus_row.update_record(statusdetail=str(e))
            db.commit()
            break


vcMem_rows = db((db.opstatus.status == "Initiated") & (db.opstatus.opstype == "memorygrowth")).select()

for vcMem_row in vcMem_rows:
    vcMem_row.update_record(status="Running")
    db.commit()
    vcMem_row.update_record(statusdetail="Running")
    db.commit()
    vcMem_row_id = vcMem_row.id

    scheduler.queue_task(initiate_memGrowth_scheduler, pvars=dict(vcMem_row_id=vcMem_row_id), timeout=3600)

################## VC Operation : Memory Growth Analysis Ends ###################


########################################################## VM Power Operation ###########################################


def vm_power_cycle_task(vm_powerops_row_id):
    vm_power_rows = db(db.opstatus.id == vm_powerops_row_id).select()
    vm_cluster = {}
    vm_dc = {}
    vm_vc = {}
    result = {}
    for vm_powerops_row in vm_power_rows:
        vm_power_opstatus_row_data = ast.literal_eval(vm_powerops_row.opsdata)
        vm_powerops_row.update_record(status="Queued")
        db.commit()
        vm_powerops_row.update_record(statusdetail="Waiting")
        db.commit()
        try:
            vm_power_json = json.dumps(vm_power_opstatus_row_data)
            vm_power_json_data = json.loads(vm_power_json)
            super_operation_type = vm_power_json_data['operation']
            vc_dict = vm_power_json_data['vc']
            for vc_item in vc_dict:
                vcIp = vc_item['vcname']
                vcPassword = vc_item['password']
                vcUser = vc_item['username']
                dc_dict = vc_item['dc']
                maxwait = vc_item.get('wait', 60)
                for dc_item in dc_dict:
                    dcName = dc_item["dcname"]
                    cluster_dict = dc_item['cluster']
                    for cluster_item in cluster_dict:
                        clusterName = cluster_item['clustername']
                        pattern_array = None
                        vm_array = None
                        operation = cluster_item['ops']
                        if "pattern" in cluster_item:
                            pattern_array = cluster_item['pattern']
                        if "vm" in cluster_item:
                            #vm_array = cluster_item['vm'] # Needs to be Implemented
                            pattern_array = cluster_item['vm']
                        if "pattern" not in cluster_item and "vm" not in cluster_item:
                            vm_cluster[clusterName] = "No patterns or VMs specified in the string."
                            continue

                        try:
                            vm_cluster[clusterName] = VmOperations.executePowerOps(vcIp, vcUser, vcPassword,dcName,clusterName,operation,pattern_array,vm_array,maxwait)
                        except Exception, e:
                            vm_cluster[clusterName] = "Power operation failed due to %s"%(e)

                    vm_dc[dcName] = vm_cluster

                result[vcIp] = vm_dc

            vm_powerops_row.update_record(status="Completed")
            db.commit()
            vm_powerops_row.update_record(statusdetail=json.dumps(result))
            db.commit()

        except Exception , e:
            result['error'] = "Power operation failed in VC due to %s "%(e)
            vm_powerops_row.update_record(status="Failed")
            db.commit()
            vm_powerops_row.update_record(statusdetail=json.dumps(result))
            db.commit()



vm_powerops_rows = db((db.opstatus.status == "Initiated") & (db.opstatus.opstype == "vmpowerops")).select()

for vm_poweroperation_row in vm_powerops_rows:
    vm_poweroperation_row.update_record(status="Running")
    db.commit()
    vm_powerops_row_id = vm_poweroperation_row.id

    scheduler.queue_task(vm_power_cycle_task,pvars=dict(vm_powerops_row_id=vm_powerops_row_id),timeout = 1800)



##################################### Power Operation Ends #############################

################################# Clone Operation Begins ######################################

def vm_clone_cycle_task(vm_clone_row_id):
    vm_clone_rows = db(db.opstatus.id == vm_clone_row_id).select()
    for vm_clone_row in vm_clone_rows:
        vm_clone_row_data = ast.literal_eval(vm_clone_row.opsdata)
        vm_clone_row.update_record(status="Queued")
        db.commit()
        vm_clone_row.update_record(statusdetail="Waiting")
        db.commit()
        vcresult = {}
        try:
            vm_clone_json = json.dumps(vm_clone_row_data)
            vm_clone_json_data = json.loads(vm_clone_json)
            super_operation_type = vm_clone_json_data['operation']
            vcdict = vm_clone_json_data['vc']
            for vcitem in vcdict:
                vc = vcitem["vcname"]
                vcresult[vc] = VmOperations.VMFullClones(vcitem)
            vm_clone_row.update_record(status="Completed")
            db.commit()
            vm_clone_row.update_record(statusdetail=json.dumps(vcresult))
            db.commit()

        except Exception,e:
            vm_clone_row.update_record(status="Failed")
            db.commit()
            vm_clone_row.update_record(statusdetail=str(e))
            db.commit()





vm_clone_rows = db((db.opstatus.status == "Initiated") & (db.opstatus.opstype == "vmclones")).select()

for vm_clone_row in vm_clone_rows:
    vm_clone_row.update_record(status="Running")
    db.commit()
    vm_clone_row_id = vm_clone_row.id
    scheduler.queue_task(vm_clone_cycle_task, pvars=dict(vm_clone_row_id=vm_clone_row_id), timeout=1800)
