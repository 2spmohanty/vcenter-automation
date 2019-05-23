import time
import re
import traceback
from customSSH import RunCmdOverSSH
from misc import DownloadFileFromVC,DownloadVCCore
from pyVim.connect import SmartConnect
from pyVim.connect import Disconnect
import atexit
import ssl
from vcenter import GetObjectsCountInVCInventory, CompareCounts
import datetime

def _AlternateAH64Install(host,username,password):
   ah64Path = '/root/ah64'
   altah64Url = "wget -O %s https://10.172.46.209/rip/static/Corefiles/ah64 --no-check-certificate"%ah64Path

   (ret, stdout, stderr) = RunCmdOverSSH(altah64Url, host, username, password)

   if ret == 0:
      #print("THREAD - MAIN - AH64 import successful from local server.")
      try:
         changePermissionDir = "chmod 777 %s"%ah64Path
         (ret, stdout, stderr) = RunCmdOverSSH(changePermissionDir, host, username, password)
         if ret == 0:
            #print("THREAD - main - Granting permission to ah64.")
            (ret, stdout, stderr) = RunCmdOverSSH(changePermissionDir, host, username, password)
            if ret == 0:
               #print("THREAD - main - Granting permission to ah64 success.")
               return ah64Path
      except Exception, e:
         #print("THREAD - MAIN - Permission to ah64 failed %s."%str(e))
         return None
   else:
      raise Exception(
         "THREAD -ERROR- MAIN - Failure while getting ah64 from local server. %s" % (stderr))



def _DownloadAH64ToVC(host, username, password):
   '''Download ah64 to the local machine'''

   ah64_url = 'http://engweb.eng.vmware.com/~tim/ah64'
   ah64Path = '/root/ah64'
   ah64_download_cmd = "wget -O %s %s"%(ah64Path,ah64_url)
   ah64_grant_perm = 'chmod 777 %s'%ah64Path
   try:
      startTime = time.time()
      #print("THREAD - main - Downloading ah64 from Tim server to VC %s"%host)
      (ret, stdout, stderr) = RunCmdOverSSH(ah64_download_cmd, host, username, password)
      #print("THREAD - main - %s"%str(stdout))
      if ret == 0:
         DownloadTime = time.time() - startTime
         #print("THREAD - main - Time taken to download ah64 : %d sec" % DownloadTime)
         #print("THREAD - main - Granting permission to ah64")
         (ret, stdout, stderr) = RunCmdOverSSH(ah64_grant_perm, host, username, password)
         if ret == 0:
            #print("THREAD - main - Granting permission to ah64 success")
            return ah64Path
      else:
         #print("THREAD - main - Chap downloading failed from Tim Server. Following alternate path")
         _AlternateAH64Install(host, username, password)

   except Exception as e:
      #print(" Error while retrieving ah64 from Tim's Server %s  : %s" % (ah64_url,str(e)))
      return None


   #os.chmod(chapPath, 0777)
   return ah64Path


def RunAh64(ah64Cmd, vc, vcUser, vcPwd, vcVersion,vcBuild,corefile,getSymReqs=False):
   '''Run ah64 on VC Host and print the output'''
   runTime = datetime.datetime.now().strftime("%d-%m-%y:%H:%M:%S")
   #print("%s VC %s vcBuild is %s" % (runTime,vc,vcBuild))
   numRetry = 1
   TotalTry = 3
   ret = None
   stdout = None
   stderr = None
   while (numRetry <= TotalTry):
      (ret, stdout, stderr) = RunCmdOverSSH(ah64Cmd, vc, vcUser,vcPwd, timeout=3600)
      # Remove below comment
      #print("ah64 command ran: %s" % ah64Cmd)
      s = "Symbolic information is not yet available"
      #print("VC %s Returned: %s" %(vc,str(ret)))
      #print("VC %s Output: %s" % (vc,str(stdout)))
      #print("VC %s Error: %s" % (vc,str(stderr)))
      if stdout and s in stdout:
         #print("VC %s Found string in the ah64 output: '%s'. Will attempt to generate symbols if needed." % (vc,s))
         if getSymReqs is True:
            try:
               GetVpxdSymbols(vc, vcUser, vcPwd, corefile,vcVersion,vcBuild)
            except Exception as e:
               #print("VC %s Exception raised while getting symbols for vpxd: %s " % (vc,str(e)))
               #print("VC %s Traceback: %s" % (vc,traceback.format_exc()))
               raise

      if (s not in str(stdout)) or getSymReqs is False:
         ##print ('\n' + ('*'*25) + ' VC %s AH64 OUTPUT'%vc + ('*'*25) + '\n')
         #print (" RETURN VALUE = %d" %ret)
         ##print ("STDOUT : \n %s" %stdout)
         print (("STDERR: \n %s \n" % stderr)+ ('*' *60))
         break
      numRetry += 1

   if numRetry > TotalTry:
      #print ("Could not run Ah64 successfully on VC %s with necessary symbols after %s attempts, GIVING UP." % (vc,TotalTry))
      raise Exception("Could not run Ah64 successfully with necessary symbols ")

   return (ret, stdout, stderr)

def instalVpxdSymbol(vc, vcUser, vcPwd,version,build):
   installState = False
   debugFileName = "VMware-vpxd-debuginfo-"+str(version)+"-"+str(build)+".x86_64.rpm"
   debugFilePath = "http://build-squid.eng.vmware.com/build/mts/release/bora-"+str(build)+\
                   "/publish/"+debugFileName
   getDebugFileCmd = 'wget -O /var/core/%s %s'%(debugFileName,debugFilePath)
   #print("VC %s Trying to get debug files from buildweb :%s " % (vc,getDebugFileCmd))
   (ret, stdout, stderr) = RunCmdOverSSH(getDebugFileCmd, vc, vcUser, vcPwd, timeout=3600)
   if ret != 0:
      raise Exception("Failed to get debug file %s to VC %s due to %s" % (debugFileName,vc, str(stderr)))
   else:
      pass
      #print("VC %s Debug file downloaded"%vc)
   installRpmCmd =  "rpm -i /var/core/" + debugFileName
   #print("Installing Debug Symbols : " + debugFileName)
   (ret, stdout, stderr) = RunCmdOverSSH(installRpmCmd, vc, vcUser, vcPwd, timeout=1800)
   if ret != 0:
      raise Exception("Failed to install %s in VC %s due to %s" % (debugFileName, vc, str(stderr)))
   else:
      installState = True

   return installState




def GetDebugFileType(f, vc, vcUser, vcPwd):
   '''Get file type for a given file in VC'''

   checkFileCmd = 'file  %s' % f
   #print("Check for file type in VC (developers build). cmd: %s" % checkFileCmd)
   (ret, stdout, stderr) = RunCmdOverSSH(checkFileCmd, vc, vcUser,vcPwd, timeout=1800)
   #print("ret=%d, stdout=%s, stderr=%s" % (ret, stdout, stderr))
   fileInfo = {'name':'%s'%f, 'exists':True, 'ftype':''}
   if 'No such file or directory' in stdout:
      fileInfo['exists'] = False
      fileInfo['ftype'] = None
   elif 'broken symbolic link' in stdout:
      fileInfo['ftype'] = 'brokenSymbolicLink'
   elif stdout.startswith('symbolic link to'):
      fileInfo['ftype'] = 'symbolicLink'
   else:
      fileInfo['ftype'] = 'regular'
   return fileInfo


def CheckDebugFilesInDevBuild(vc, vcUser, vcPwd,version,build,corefile):
   '''Check if dev build style VC has required files to generate debug
      symbols'''

   vpxdInfo = GetDebugFileType('/usr/lib/vmware-vpx/vpxd',vc,vcUser,vcPwd)
   vpxdDebugInfo = GetDebugFileType('/usr/lib/debug/usr/lib/vmware-vpx/vpxd.debug',
                                    vc,vcUser,vcPwd)

   """

   buildVpxdMsg = "Please make sure to build vpxd target. For vcenter: "\
                  "'scons PRODUCT=vcenter vpxd'.  Run load-vc after building"\
                  " vpxd"

   """


   buildVpxdMsg = "Attempting to Install vpxd Symbols."

   #If vpxd exists as a file and vpxd.debug does not, suggest that symbols
   #should be installed
   if vpxdInfo['exists'] and not vpxdDebugInfo['exists']:
      """
      #print('**File %s exists but file %s does not exist. Please make sure '\
               'symbols are installed. %s **' %(vpxdInfo['name'],
               vpxdDebugInfo['name'],buildVpxdMsg))
      """
      installState = instalVpxdSymbol(vc, vcUser, vcPwd,version,build)
      return installState

   #If vpxd is a link and vpxd.debug does not exist, that probably means that
   #load-vc was run but didn't complete properly.
   if vpxdInfo['ftype'] == 'symbolicLink' and not vpxdDebugInfo['exists']:
      """
      #print('**%s file is a link, %s does not exist.load-vc probably failed'\
               'to set up links properly. %s**' % (vpxdInfo['name'],
                                            vpxdDebugInfo['name'],buildVpxdMsg))
      """
      installState = instalVpxdSymbol(vc, vcUser, vcPwd, version, build)
      return installState

   #If either symbolic link is broken, flag that broken link
   if vpxdInfo['ftype'] == 'brokenSymbolicLink':
      """
      #print('**Symbolic link broken for %s. Please check your tree**' %
               vpxdInfo['name'])
      """
      installState = instalVpxdSymbol(vc, vcUser, vcPwd,version,build)
      return installState

   if vpxdDebugInfo['ftype'] == 'brokenSymbolicLink':
      """
      #print('**Symbolic link broken for %s. Please check your tree**' %
               vpxdDebugInfo['name'])
      """
      installState = instalVpxdSymbol(vc, vcUser, vcPwd, version, build)
      return installState

   #If one is a file and one is a link,the symbols are probably not consistent
   #with the binaries
   if vpxdInfo['ftype'] != vpxdDebugInfo['ftype']:
      """
      #print('**The file type for files are not same.File type for file %s'\
               ' is %s. File type for file %s is %s.This suggests that the '\
               'symbols are probably not consistent with the binaries**' %
               (vpxdInfo['name'], vpxdInfo['ftype'], vpxdDebugInfo['name'],
                vpxdDebugInfo['ftype']))
      """
      installState = instalVpxdSymbol(vc, vcUser, vcPwd, version, build)
      return installState

   #If both the files are either symbolic link or both are regular files,can
   #proceed with the checks
   if ((vpxdInfo['ftype'] != '') and (vpxdInfo['ftype'] == vpxdDebugInfo['ftype'])):
      #print("Both files have same file type: %s.Will try to generate debugsymbols on this VC" % vpxdInfo['ftype'])

      symDefGenCmd = "echo source %s.symreqs | gdb -c %s /usr/lib/vmware-vpx/vpxd" % (corefile, corefile)
      (ret, stdout, stderr) = RunCmdOverSSH(symDefGenCmd, vc, vcUser, vcPwd, timeout=600)
      print "Coming Here"
      if ret==0:
         return True
      else:
         return False

#////////////////////////////////////////////////////////////////////////////////#

def GetVpxdSymbols(vc, vcUser, vcPwd, corefile,version,vcBuild):

   # check if symdefs file for the pid already exists, use that file.
   #print("Checking if there is an existing usable symdef file....")
   pidCmd = 'pidof vpxd'
   #print("Get pid of vpxd. cmd: %s" % pidCmd)
   (ret, stdout, stderr) = RunCmdOverSSH(pidCmd, vc, vcUser,vcPwd, timeout=3600)
   #print("ret=%d, stdout=%s, stderr=%s" % (ret, stdout, stderr))
   vpxdPid = stdout
   #vpxdPid = "9020" #Remove this .. Debug Only
   dirListCmd = 'ls /var/core'
   #print("Listing files in remote dir. cmd: %s" % dirListCmd)

   (ret, stdout, stderr) = RunCmdOverSSH(dirListCmd, vc, vcUser,vcPwd, timeout=3600)

   #(ret, stdout, stderr) = RunCmdOverSSH(vc,vcLocalUser,vcLocalPwd,dirListCmd)
   #print("ret=%d, stdout=%s, stderr=%s" % (ret, stdout, stderr))
   files = stdout.split('\n')
   symDefFound = False
   symDefFile = None
   for f in files:
      if re.match('livecore(.)*\.%s\.symdefs'%vpxdPid, f):
         symDefFound = True
         #print("Found an existing symdefs file:%s for pid=%s. Will try touse it." % (f,vpxdPid))
         symDefFile = f
         break

   if symDefFile:
      createSymlinkCmd = 'ln -s /var/core/%s %s.symdefs' % (symDefFile,corefile)
      #print("Creating symlink to existing symdef file. cmd: %s"% createSymlinkCmd)
      (ret, stdout, stderr) = RunCmdOverSSH(createSymlinkCmd, vc, vcUser,vcPwd, timeout=3600)
      #print("ret=%d, stdout=%s, stderr=%s" % (ret, stdout, stderr))
      return True


   if vcBuild and version:
      #Check if the correct debug files exists
      #print("This is developer's build...")
      #print("Initiating Symdef file generation..")
      reqdFileExists = CheckDebugFilesInDevBuild(vc, vcUser,vcPwd,version,vcBuild,corefile)
      if not reqdFileExists:
         raise Exception("Files necessary on the dev build VC does not exist,"\
                         "Please check logs for details")
   else:
      raise Exception("VC Build is not specified for VC %s. Symdefs file could not be generated."
                      "Memory growth Analysis is quitting now.")

   return True


#change the user in below function to root user
def GetVCMoCounts(vc, vcUser, vcPwd, remoteAh64Path, corefile, vcVersion, vcBuild, invtObjMap):
   '''Get MoCounts running ah64 cmd  '''

   ah64Cmd = "echo summarize allocated | %s %s"%(remoteAh64Path,corefile)
   try:
      #print("Getting Allocated chunks in VC by running Debugger tool.")
      (ret, stdout, stderr) = RunAh64(ah64Cmd, vc, vcUser, vcPwd,
                                      vcVersion, vcBuild,corefile,getSymReqs=True)
      if ret != 0:
         raise Exception("ah64 cmd failed to get allocated summary. ret=%d,\
                          ah64Cmd=%s" % (ret, ah64Cmd))
   except Exception as e:
      #print("Exception raise when running Ah64: %s" % str(e))
      #print("Traceback: %s" % traceback.format_exc())
      raise Exception(str(e))

   # Getting managed objects to compare with VC Inventory
   #print("Getting Managed objects in %s by running parser query."%vc)
   managedObjects = {}
   # Build the managed objects dict
   for obj in invtObjMap.values():
      managedObjects[obj + 'Mo'] = 0
   moStr = "|".join(str(Mo) for Mo in managedObjects)
   ##print "Debug: The moStr is "+ str(moStr)
   # Parse allocated managed objects
   output = stdout.split('\n')
   p = re.compile("[A-Za-z0-9\s]* \((%s)\) has (\d+) instances" % moStr)
   for line in output:
      m = p.match(line)
      if m:
         managedObjects[m.group(1)] = int(m.group(2))

   if not managedObjects:
      pass
      #print("AH64 RUN DID NOT RETURN VALID OUTPUT ")
   #print "Debug: The managed objects are "+ str(managedObjects)
   return managedObjects

def GetSI(vc, vcLocalUser, vcLocalPwd):
   si = None
   try:

      context = ssl._create_unverified_context()
      si = SmartConnect(host=vc, user=vcLocalUser, pwd=vcLocalPwd, port=443, sslContext=context)
   except IOError, e:
      pass
   except Exception,e1:
      raise
   return si

def CheckMemGrowth(vc, vcUser, vcPwd, vcLocalUser, vcLocalPwd, vcVersion,vcBuild):
   '''Check for memory growth in VC'''

   MemGrowthMasterDict={}

   try:
      try:
         remoteAh64Path = _DownloadAH64ToVC(vc, vcUser, vcPwd)
      except Exception as e:
         #print("Exception raised while getting ah64 : %s" % str(e))
         #print("Traceback: %s" % traceback.format_exc())
         raise

      # Inventory Object map with (obj type , obj name) records
      invtObjMap = {'vim.Datastore': 'Datastore',  'vim.Folder': 'Folder', \
         'vim.VirtualMachine': 'Vm', 'vim.HostSystem': 'Host', 'vim.Network': 'Network'}
      try:
         #print("Getting connection to Vcenter")
         si = GetSI(vc, vcLocalUser, vcLocalPwd)
         atexit.register(Disconnect, si)
         #print("Successfully got connection to VC %s"% vc)
      except Exception, e:
         return "Error while connecting: " + str(e)

      #print("Getting Inventory Objects count in VC using VMODL Query %s" % vc)
      invtCounts, moIdList = GetObjectsCountInVCInventory(si, invtObjMap)
      #print("Inventory Object count in %s VC is %s" % (vc, str(invtCounts)))

      totalRetry = 2
      numRetry = 1
      moCounts = None
      while(numRetry <= totalRetry):
         try:
            generate_core_cmd = "/usr/lib/vmware-vmon/vmon-cli -d vpxd"
            (ret, stdout, stderr) = RunCmdOverSSH(generate_core_cmd, vc, vcUser, vcPwd,timeout=1800)
            s = "Completed dump service livecore request"
            corefile = None
            if stdout and s in stdout and ret == 0:
               corefile = stdout.split()[-1]
               #print("THREAD- %s - The core file for service is at %s" % (vc, corefile))

         except Exception as e:
            return "Exception raised while generating VC %s core: %s" % (vc,str(e))


         #print("Getting Managed Object count in VC from core file %s" % vc)
         moCounts = GetVCMoCounts(vc, vcUser, vcPwd, remoteAh64Path,corefile, vcVersion,vcBuild,invtObjMap)
         #print("Managed Object count in VC %s is %s" % (vc, moCounts))
         if not moCounts:
            errMsg = ('\nFailed to run ah64 on %s, Managed Objects were returned '\
                      'as None' % vc)
            #print("%s" % errMsg)

            return "%s" % errMsg

         countsMismatch, diffCounts = CompareCounts(moCounts, invtCounts)
         MemGrowthDict = {}
         if countsMismatch:
            #print("Managed Object counts and Inventory counts did not match, ATTEMPT# %s" %numRetry)
            #print("Extra objects found at the end of ATTEMPT# %s: %s" %  (numRetry, diffCounts))
            MemGrowthDict["MOR in VC"] = sorted(invtCounts.items())
            MemGrowthDict["MOR in Core"] = vc,sorted(moCounts.items())

            MemGrowthMasterDict[numRetry] = MemGrowthDict
            time.sleep(5)
            numRetry += 1
         else:
            MemGrowthDict["MOR in VC"] = sorted(invtCounts.items())
            MemGrowthDict["MOR in Core"] = vc, sorted(moCounts.items())
            MemGrowthMasterDict[numRetry] = MemGrowthDict
            break

      if numRetry > totalRetry:
         memoryGrowthMsg = "MEMORY GROWTH FOUND"
         MemGrowthMasterDict["Analysis"] = memoryGrowthMsg
         #print("%s" % memoryGrowthMsg)

      else:
         noMemoryGrowthMsg = ('VC: %s - No Memory Growth found after ATTEMPT# %s' % (vc,numRetry))
         MemGrowthMasterDict["Analysis"] = noMemoryGrowthMsg
         #print("%s" % noMemoryGrowthMsg)

   finally:
      #print("The Memory growth Test is over for VC %s."%vc)
      return MemGrowthMasterDict


