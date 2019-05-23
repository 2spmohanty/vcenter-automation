import time
import re
import traceback
from misc import DownloadFileFromVC,DownloadVCCore
from pyVim.connect import SmartConnect
from pyVim.connect import Disconnect
import atexit
import ssl
from vcenter import GetObjectsCountInVCInventory, CompareCounts
import urllib
import os
import subprocess
from customSSH import SFTPManager,RunCmdOverSSH
import multiprocessing
from multiprocessing.dummy import Pool as ThreadPool

def _AlternateChapInstall(host,username,password):
   chapPath = '/root/chap'
   altChapUrl = "wget -O %s https://10.172.46.209/rip/static/Corefiles/chap --no-check-certificate"%chapPath

   (ret, stdout, stderr) = RunCmdOverSSH(altChapUrl, host, username, password)

   if ret == 0:
      #print("THREAD - MAIN - Chap import successful from local server.")
      try:
         changePermissionDir = "chmod 777 %s"%chapPath
         (ret, stdout, stderr) = RunCmdOverSSH(changePermissionDir, host, username, password)
         if ret == 0:
            #print("THREAD - main - Granting permission to chap.")
            (ret, stdout, stderr) = RunCmdOverSSH(changePermissionDir, host, username, password)
            if ret == 0:
               #print("THREAD - main - Granting permission to chap success.")
               return chapPath
      except Exception, e:
         #print("THREAD - MAIN - Permission to chap failed %s."%str(e))
         return None
   else:
      return



def _DownloadChapToVC(host, username, password):

   '''Download chap to the local machine'''

   chap_url = 'http://engweb.eng.vmware.com/~tim/chap'
   chapPath = '/root/chap'
   chap_download_cmd = "wget -O %s %s"%(chapPath,chap_url)
   chap_grant_perm = 'chmod 777 %s'%chapPath
   try:
      startTime = time.time()
      #print("THREAD - main - Downloading chap from Tim server to VC %s"%host)
      (ret, stdout, stderr) = RunCmdOverSSH(chap_download_cmd, host, username, password)
      #print("THREAD - main - %s"%str(stdout))
      if ret == 0:
         DownloadTime = time.time() - startTime
         #print("THREAD - main - Time taken to download chap : %d sec" % DownloadTime)
         #print("THREAD - main - Granting permission to chap")
         (ret, stdout, stderr) = RunCmdOverSSH(chap_grant_perm, host, username, password)
         if ret == 0:
            #print("THREAD - main - Granting permission to chap success")
            return chapPath
      else:
         #print("THREAD - main - Chap downloading failed from Tim Server. Following alternate path")
         _AlternateChapInstall(host, username, password)

   except Exception as e:
      #print(" Error while retrieving chap from Tim's Server %s  : %s" % (chap_url,str(e)))
      return None


   #os.chmod(chapPath, 0777)
   return chapPath

def RunChap(service,ChapCmd, vc, vcUser, vcPwd):
   '''Run chap on VC Host and log the output'''

   ret = None
   stdout = None
   stderr = None
   print("Running chap on service %s"%service)

   (ret, stdout, stderr) = RunCmdOverSSH(ChapCmd, vc, vcUser,vcPwd, timeout=3600)
   # Remove below comment
   #log.info("ah64 command ran: %s" % ah64Cmd)
   s = "allocations"
   #log.debug("THREAD - %s - Returned: %s" % (service,str(ret)))
   #log.debug("THREAD - %s - Output: %s" % (service,str(stdout)))
   #log.debug("THREAD - %s - Error: %s" % (service,str(stderr)))
   if stdout and s in stdout:
      #print('\n' + ('*' * 25) + 'CHAP OUTPUT %s'%service + ('*' * 25) + '\n')
      #print("THREAD - %s - RETURN VALUE = %d" %(service, ret))
      print("THREAD - %s - STDOUT : \n %s" % (service,stdout))
      print(("THREAD - %s - STDERR: \n %s \n" % (service,stderr) + ('*' * 60)))
   else:
      print("THREAD - %s - STDERR: \n %s \n" % (service,"CHAP didn't yield a success result.") + ('*' * 60))


   return (ret, stdout, stderr)


#########################   VC Operation Memory Leak Multi Threaded Code Begins ###########################

#Synchronized Object to Hold Results

synchObj=multiprocessing.Manager()


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
            #print("THREAD- %s - The core file for service is at %s" % (service, core_file_path))
        elif ret is None:
            #print("THREAD- %s - The core file for service is taking time." % service)
            long_running_dict[service] = "Timeout while generating core. Proceed manually."
        else:
            #print("THREAD- %s - Error: %s" % (service, str(stderr)))
            if ret == 4:
                #print("THREAD- %s - It seems the service is not running on the appliance." % (service))
                no_service_running_dict[service] = "Service not running on VC"

        if core_file_path:
            #print('THREAD %s - Starting Analysis of core file ' % service)
            core_analysis_result_pool.append(
                core_analysis_pool.apply_async(core_analysis_handler, (service,chapPath,core_file_path,host,
                                                                       username, password)))
        else:
           exception_service_dict[service] = "Core file could not be generated."

    except Exception, e:
        #print("THREAD- %s - Exception while Generating cores in VC for %s service %s"%(host,service,str(e)))
        exception_service_dict[service] = str(e)


def CheckMemLeak(host, username, password,service_name_array):
   finalresults = {}
   service_name=[]
   implemented_services = ['analytics', 'applmgmt',
                           'hvc', 'imagebuilder', 'lookupsvc', 'mbcs', 'netdumper', 'perfcharts',
                           'pschealth', 'rbd', 'rhttpproxy', 'sca', 'statsmonitor', 'trustmanagement',
                           'updatemgr', 'vcha', 'vmcam', 'vmonapi', 'vmware-postgres-archiver',
                           'vmware-vpostgres', 'vsan-dps', 'vsan-health', 'vsm','sps']
   for s in service_name_array:
      if s not in implemented_services:
         finalresults["Analysis not implemented"] = finalresults.get("Analysis not implemented", None) + "," + s
      else:
         service_name.append(s)

   exception_services = ["vmdird"]
   chapPath = _DownloadChapToVC(host, username, password)
   if chapPath is None:
       finalresults["Failure"] = "CHAP could not be downloaded to VC."
       return finalresults

   threads = 10
   pool = ThreadPool(threads)
   core_analysis_pool = ThreadPool(threads)
   core_analysis_result_pool = []
   service_specs = []
   try:
      for service in service_name:
         if service not in exception_services:
            service_specs.append((host, username, password, service,
                                  chapPath, core_analysis_pool, core_analysis_result_pool))

      #print('THREAD - main - Running Memory Analysis Thread pool')
      pool.map(mem_analysis_handler_wrapper, service_specs)

      #print('THREAD - main - Closing Memory Analysis Thread pool')
      pool.close()
      pool.join()
      # main_logger.debug("THREAD - main - Closing the core analysis thread pool.")
      core_analysis_pool.close()
      core_analysis_pool.join()
   except (KeyboardInterrupt, SystemExit):
      print('THREAD - main - Recieved Manual Interrupt Signal. Exiting')
   except Exception, e:
      finalresults['Internal Error'] = str(e)
      return finalresults

   mem_result = dict(mem_result_dict)
   no_service_running = dict(no_service_running_dict)
   long_running = dict(long_running_dict)
   exception_service = dict(exception_service_dict)

   finalresults['Memory Leaks'] = mem_result
   finalresults['Service Not Running'] = no_service_running
   finalresults['Cores Generation Failure'] = long_running
   finalresults['Failure'] = exception_service
   try:
       uptimecmd = "uptime -p"
       (ret, stdout, stderr) = RunCmdOverSSH(uptimecmd, host, username, password)
       if ret != 0:
           finalresults["Uptime"] = str(stderr)
       else:
           finalresults["Uptime"] = str(stdout)
   except Exception, e:
       finalresults["Uptime"] = "Could not obtain duration of uptime %s." % str(e)

   # Get Build

   try:
       uptimecmd = "grep 'BUILDNUMBER' /etc/vmware/.buildInfo | cut -d\":\" -f2"
       (ret, stdout, stderr) = RunCmdOverSSH(uptimecmd, host, username, password)
       if ret != 0:
           finalresults["Build"] = str(stderr)
       else:
           finalresults["Build"] = str(stdout)
   except Exception, e:
       finalresults["Build"] = "Could not obtain Build %s." % str(e)

   return finalresults

#########################   VC Operation Memory Leak Multi Threaded Code Ends ###########################



