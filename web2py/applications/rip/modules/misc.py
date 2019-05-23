import sys
import os
import re
import platform
import errno
import multiprocessing
import time
import random
import signal
import subprocess
from six.moves import queue
import threading
import socket
from functools import wraps
import exceptions
import tarfile
import tvpxglobals

VIMDEVTOOLSPATH="/mts/vimdevtools/"

# Functions

def IsWindows():
   return platform.system() == 'Windows'

def IsMacOsX():
   return platform.system() == 'Darwin'

def Is64Bit():
   return True if sys.maxsize > 2 ** 32 else False

def Makedirs(path):
   try:
      os.makedirs(path)
   except OSError as e:
      if e.errno == errno.EEXIST:
         pass
      else:
         raise

def GetTcRoot():
   return os.environ.get('TCROOT') or \
          'C:\\toolchain' if IsWindows() else '/build/toolchain'

def Display(msg, newLine=True, eraseLine=True):
   if eraseLine:
      msg = '\r%s' % msg
   if newLine:
      print(msg)
   elif sys.stdout.isatty():
      sys.stdout.write(msg)
      sys.stdout.flush()

def TerminateProcesses(processes, timeout=0):
   for process in processes:
      process.join(timeout)
      if process.is_alive():
         process.terminate()

def Untar(tarFile, desDir):
   tf = tarfile.open(tarFile)
   tf.extractall(desDir)
   tf.close()

def Unzip(zipfile, destDir):
   if IsWindows():
      unzip = GetTcRoot() + '/win32/unzip-5.52-2/bin/unzip.exe'
   elif IsMacOsX():
      unzip = GetTcRoot() + '/mac32/unzip-5.52/bin/unzip'
   else:
      unzip = GetTcRoot() + '/lin32/unzip-5.52/bin/unzip'
   process = subprocess.Popen([unzip, zipfile, '-d', destDir],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
   stdout, stderr = process.communicate()
   if process.returncode != 0:
      sys.stdout.write('unzip failed:\n')
      sys.stdout.write(stdout)
      sys.stdout.write(stderr)

def GetFQDN(hostname, domain='eng.vmware.com'):
   return hostname if '.' in hostname else '%s.%s' % (hostname, domain)

# Classes

class Spinner(multiprocessing.Process):
   '''Console spinner to signify an "in progress" state for longer tasks.'''
   # XXX: Make spinning depend on actual work being done.

   def __init__(self):
      self.chars = '-\\|/'
      multiprocessing.Process.__init__(self)

   def run(self):
      try:
         while True:
            for char in self.chars:
               Display('\b%s' % char, newLine=False, eraseLine=False)
               time.sleep(random.uniform(0.1, 3))
      except KeyboardInterrupt:
         pass

class AutoVivifyingDict(dict):
   '''Implementation of Perl's autovivification feature.'''

   def __getitem__(self, item):
      try:
         return dict.__getitem__(self, item)
      except KeyError:
         value = self[item] = type(self)()
         return value

class LocalProcess(multiprocessing.Process):
   '''Process object that runs a command locally'''

   def __init__(self, cmd, executable=None, queue=None, errQueue=None, env=None):
      multiprocessing.Process.__init__(self)
      self.cmd = cmd
      self.executable = executable
      self.queue = queue
      self.errQueue = errQueue
      self.env = env
      self.cmd_return_code = multiprocessing.Value("i", -1)

   def run(self):
      '''
      Override multiprocessing.Process's run() method with our own that
      executed a command locally
      '''

      if self.cmd:
         process = subprocess.Popen(self.cmd.split(), executable=self.executable,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    env=self.env)
         stdout, stderr = process.communicate()

         self.queue.put(stdout.strip())
         self.errQueue.put(stderr.strip())
         self.cmd_return_code.value = process.returncode

         if process.returncode != 0:
            sys.stdout.write('cmd failed: %s\n' % self.cmd.split())
            sys.stdout.write(stdout)
            sys.stdout.write(stderr)

         self.queue.cancel_join_thread()
         self.errQueue.cancel_join_thread()

class Threads(threading.Thread):
   ''' This class will execute a given function mentioned in "target"
       as a separate thread.
   '''
   def __init__(self, group=None, target=None, name=None, args=(), kwargs={}):
      ''' This constructor simply takes in the same
          parameters as that by the parent class' constructor
      '''
      threading.Thread.__init__(self, group, target, name, args, kwargs)
      self._target = target
      self._args = args
      self._kwargs = kwargs

   def run(self):
      ''' Calls the target function and stores
          the return value in a member variable
      '''
      self._return = self._target(*self._args, **self._kwargs)

   def result(self):
      return self._return

def RunCmdLocally(cmd, timeout=15, env=None, cmd_return_code=False):
   '''Wrapper for LocalProcess() to run a single command'''

   stdout, stderr = '', ''
   stdoutQueue = multiprocessing.Queue()
   stderrQueue = multiprocessing.Queue()
   process = LocalProcess(cmd, queue=stdoutQueue, errQueue=stderrQueue, env=env)
   try:
      process.start()
      process.join(timeout)
      if process.is_alive():
         process.terminate()

      stdout = stdoutQueue.get(True, timeout)
      stderr = stderrQueue.get(True, timeout)
   except (KeyboardInterrupt, queue.Empty):
      if process.is_alive():
         process.terminate()

   if cmd_return_code:
       return process.exitcode, stdout, stderr, process.cmd_return_code.value
   else:
       return process.exitcode, stdout, stderr

def GetESXMemoryStats(host, user, pwd, log):
   from customSSH import RunCmdOverSSH
   memStatsCmd = 'memstats -r comp-stats -u mb -s total'
   (ret, stdout, stderr) = RunCmdOverSSH(memStatsCmd, host, user, pwd,
                                         timeout=8)
   if stdout is None:
      totalMemory = -1
      log.info("Failed to query ESX memory size for host %s: ret=%s, stdout=%s, stderr=%s" %
              (host,ret,stdout, stderr))
   else:
      try:
         splitStr = stdout.split('\n')
         totalMemory = int(splitStr[-2].strip())
      except Exception as e:
         totalMemory = -1
         log.info("Exception while getting esx memory for host=%s: %s" % (host, str(e)))
   return totalMemory

def GenerateCoreFile(vcHost, vcUser, vcPwd, log, suffix=''):
   '''Generate a cloudvm core file using gcore'''
   from customSSH import RunCmdOverSSH

   suffix = '-'+str(suffix) if suffix != '' else ''
   corePath = '/var/core/liveVpxdCore'+suffix
   cmd = ("gcore -o %s `pidof vpxd`" % corePath)
   log.info("cloudvm: %s, command to be run: %s" % (vcHost, cmd))
   (ret, stdout, stderr) = RunCmdOverSSH(cmd , vcHost, vcUser, vcPwd, 180)
   log.info("Return value : %d" % ret)
   if ret != 0 or not stdout:
      return None

   match = re.search("Saved corefile (/var/core/liveVpxdCore(-\d*)?\.(\d)*)", stdout)
   if not match:
      log.info("Could not find core file name in stdout: %s" % stdout)
      return None
   coreFileName = match.group(1)
   log.info("core file full path is %s" % coreFileName)
   return coreFileName

def MountVimDevTools(vcHost, vcUser, vcPwd, log):
   '''Mount tools folder on cloudvm'''
   from customSSH import RunCmdOverSSH

   remoteToolsPath = "pa-group2.eng.vmware.com:/ifs/pa-group2/vimdevtools"
   #Create path for nfs mount
   cmd = 'mkdir -p %s' % VIMDEVTOOLSPATH
   log.info("Cloudvm: %s, command to be run: %s" %  (vcHost,cmd))
   (ret, stdout, stderr) = RunCmdOverSSH(cmd, vcHost, vcUser, vcPwd)
   log.info("ret=%s, stdout = %s ,stderr = %s" % (ret, stdout,stderr))
   if stderr:
      log.info("Could not create required directory, Failed to run command %s" % cmd)
      return False

   cmd= "mount -t nfs %s %s -o nolock" % (remoteToolsPath, VIMDEVTOOLSPATH)
   log.info("cloudvm: %s, Command to be run: %s" %  (vcHost,cmd))
   (ret, stdout, stderr) = RunCmdOverSSH(cmd, vcHost, vcUser, vcPwd)
   log.info("ret=%s, stdout = %s ,stderr = %s" % (ret, stdout,stderr))
   if stderr:
      log.info("Could not mount successfully, Failed to run command %s" % cmd)
      return False

   log.info("Tools folder mounted succesfully to %s" % VIMDEVTOOLSPATH)
   return True

def DownloadVCCore(corefile, vcHost, vcUser, vcPwd, logDir, log):
   '''Download the VC  core to local host'''
   from customSSH import SFTPManager

   log.info('Trying to download the VC core file locally...')
   coreName = os.path.basename(corefile)
   localCorePath = os.path.join(logDir, coreName)
   sftp = SFTPManager(host=vcHost, user=vcUser,
                     pwd=vcPwd, timeout=1500)
   sftp.InitiateSFTPSession()
   try:
      sftp.GetRemoteFile(corefile, localCorePath)
      log.info("VC core locally available at %s" %localCorePath)
   except:
      log.error('Unable to download the VC core file locally')
   sftp.TerminateSFTPSession()


def DownloadFileFromVC(filename, srcDir, destDir, vcHost, vcUser, vcPwd, log):
   '''Download file from VC host locally'''
   from customSSH import SFTPManager

   log.info('Trying to download the %s file locally...'%filename)
   remotePath=os.path.join(srcDir, filename)
   localPath = os.path.join(destDir, filename)
   sftp = SFTPManager(host=vcHost, user=vcUser,
                     pwd=vcPwd, timeout=1500)
   sftp.InitiateSFTPSession()
   try:
      sftp.GetRemoteFile(remotePath, localPath)
      log.info("%s locally available at %s" %(filename,localPath))
   except:
      log.error('Unable to download the %s  file locally'%filename)
   sftp.TerminateSFTPSession()

def RunPGAuditTool(vcHost, vcUser, vcPwd, log):
   '''Install and Enable Postgres Audit tool'''

   from customSSH import RunCmdOverSSH
   mounted = MountVimDevTools(vcHost, vcUser, vcPwd, log)
   if mounted is False:
      log.info("Unable to mount %s" % VIMDEVTOOLSPATH)
      return 1
   createDir_cmd = "mkdir -p /storage/pg_audit"
   (ret,stdout,stderr) = RunCmdOverSSH(createDir_cmd, vcHost, vcUser, vcPwd)
   log.info("cmd: %s,ret:%d,stdout:%s,stderr%s" % (createDir_cmd, ret, stdout, stderr))
   if ret !=0:
      log.info("Creating direcotry failed, command run: %s" % createDir_cmd)
      return 1

   copyTool_cmd = "cp %s/pg_audit/Prod/* /storage/pg_audit" % VIMDEVTOOLSPATH
   (ret,stdout,stderr) = RunCmdOverSSH(copyTool_cmd, vcHost, vcUser, vcPwd)
   log.info("cmd: %s,ret:%d,stdout:%s,stderr%s" % (copyTool_cmd, ret, stdout, stderr))
   if ret !=0:
      log.info("Copying pgaudit tool to VC host failed, command run: %s" % copyTool_cmd)
      return 1
   chmod_cmd = "chmod  755 /storage/pg_audit/*.sh"
   (ret,stdout,stderr) = RunCmdOverSSH(chmod_cmd, vcHost, vcUser, vcPwd)
   log.info("cmd: %s,ret:%d,stdout:%s,stderr%s" % (chmod_cmd, ret, stdout, stderr))
   if ret !=0:
      log.info("Could not change file persmission, command run: %s" % chmod_cmd)
      return 1
   totalRetryInstall = 3
   numretry = 0
   while (numretry < totalRetryInstall):
      #Retry installing pgaudit tool in case it fails.  We saw deadlock issues
      #in past when installing pgaudit tool.
      install_cmd = "/storage/pg_audit/main.sh install"
      (ret,stdout,stderr) = RunCmdOverSSH(install_cmd, vcHost, vcUser, vcPwd)
      log.info("cmd: %s,ret:%d,stdout:%s,stderr%s" % (install_cmd, ret, stdout, stderr))
      if ret !=0:
         log.info("Failed to install postgres audit tool, command run: %s, "\
                  "ATTEMPT# %s" % (install_cmd, numretry))
         time.sleep(60)
         numretry += 1
      else:
         break
      #Wait for a minute before retrying to install pgaudit tool
   if (numretry >= totalRetryInstall):
      log.info("Failed to install postgres audit tool, giving up ... ")
      return 1
   enableCDC_cmd = "/storage/pg_audit/main.sh enable"
   (ret,stdout,stderr) = RunCmdOverSSH(enableCDC_cmd, vcHost, vcUser, vcPwd)
   log.info("cmd: %s,ret:%d,stdout:%s,stderr%s" % (enableCDC_cmd, ret, stdout, stderr))
   if ret !=0:
      log.info("Failed to enable postgres audit tool: %s" % enableCDC_cmd)
      return 1

   return 0



# Decorators

class Cache(object):
   '''Decorator class to cache expensive method calls.'''

   def __init__(self, cache_function):
      self._cache = cache_function

   def __get__(self, obj, _=None):
      if obj is None:
         return self
      value = self._cache(obj)
      if hasattr(self._cache, '__name__'):
         setattr(obj, self._cache.__name__, value)
      else:
         setattr(obj, self._cache.func_name, value)
      return value

class DotDict(dict):
   '''
   Makes a dictionary behave like an object
   Not the safest thing to do in a general case
   But it does give it a nicer interface in terms
   of attribute access with the '.'
   '''

   def __getattr__(self, name):
      try:
         return self[name]
      except KeyError:
         raise AttributeError(name)

   def __setattr__(self, name, value):
      self[name] = value



def IgnoreCtrlC(func):
   '''Disable Ctrl-C before the function call; re-enable it after.'''

   def PrintCtrlcMsg(*args):
      print('Ctrl-C is disabled during clean-up and other critical operations.')

   def OriginalFunctionIgnoringCtrlC(*args):
      ctrlcHandler = signal.signal(signal.SIGINT, PrintCtrlcMsg)
      f = func(*args)
      signal.signal(signal.SIGINT, ctrlcHandler)

   return OriginalFunctionIgnoringCtrlC

def timeout(seconds=10, error_message='Timer expired'):
    def decorator(func):
        def _handle_timeout(signum, frame):
            raise exceptions.TimeoutError(error_message)

        def _handle_windows_timeout():
            raise exceptions.TimeoutError(error_message)

        def wrapper(*args, **kwargs):
            t = None
            if IsWindows():
                t = threading.Timer(seconds, _handle_windows_timeout)
                t.start()
            else:
                signal.signal(signal.SIGALRM, _handle_timeout)
                signal.alarm(seconds)
            try:
                result = func(*args, **kwargs)
            finally:
                if IsWindows():
                    t.cancel()
                else:
                    signal.alarm(0)
            return result

        return wraps(func)(wrapper)

    return decorator

def GetDependencies():
    '''Get list of python dependencies required by all the modules in pyVpx'''
    tc_root = GetTcRoot()
    dependencies = []
    dependencies.append(os.path.join(tc_root, 'noarch', 'six-1.9.0', 'lib',
                                     'python2.7', 'site-packages'))
    dependencies.append(os.path.join(tc_root, 'noarch', 'setuptools-5.7', 'lib',
                                     'python2.7', 'site-packages',
                                     'setuptools-5.7-py2.7.egg'))
    dependencies.append(os.path.join(tc_root, 'noarch', 'requests-2.6.0', 'lib',
                                     'python2.7', 'site-packages'))

    # Platform specific dependencies
    if IsWindows():
        dependencies.append(os.path.join(tc_root, 'win32',
                                         'pyopenssl-0.13-openssl1.0.1p', '2.7',
                                         'Lib', 'site-packages'))
        dependencies.append(os.path.join(tc_root, 'win32', 'lxml-3.6.0',
                                         'python2.7', 'Lib', 'site-packages'))
    elif IsMacOsX():
        dependencies.append(os.path.join(tc_root, 'mac32', 'pyopenssl-0.13-2',
                                         'lib', 'python2.7', 'site-packages'))
        dependencies.append(os.path.join(
            tc_root, 'mac32', 'lxml-3.6.0', 'lib', 'python2.7', 'site-packages',
            'lxml-3.6.0-py2.7-macosx-10.5-x86_64.egg'))
    else:
        # linux host
        lin_type = 'lin64' if Is64Bit() else 'lin32'
        dependencies.append(os.path.join(tc_root, lin_type, 'pyopenssl-0.13-5',
                                         'lib', 'python2.7', 'site-packages'))
        dependencies.append(os.path.join(tc_root, lin_type, 'lxml-3.3.1',
                                         'lib', 'python2.7', 'site-packages'))
    return dependencies

def GetHostIpType(host,log):
   #Find out if the host passed is ip address or fqdn
   if ':' not in host and  re.search('[a-zA-Z]',host):
      #host is fqdn
      try:
         host = socket.gethostbyname(host)
      except:
         #exception will be raised for ipv6 host, ignore it.
         try:
            host=socket.getaddrinfo(host,None)[0][4][0]
         except:
            if log:
               log.info("Unable to determine ip address for host=%s", host)
            return 'invalid'

   try:
     socket.inet_pton(socket.AF_INET, host)
     return 'ipv4'
   except:
     pass
   try:
     socket.inet_pton(socket.AF_INET6, host)
     return 'ipv6'
   except:
     return 'invalid'


def IsVCWindows(vcHost, log, vcHttpsPort=443):
   '''Check if the VC Platform is Windows.'''
   from pyVmomi import Vim, SoapStubAdapter, SoapAdapter
   try:
      soapStub = SoapStubAdapter(vcHost, port=vcHttpsPort)
      vcSi = Vim.ServiceInstance("ServiceInstance", soapStub)
      siContent = vcSi.RetrieveContent()
      osType = siContent.about.osType
      return bool(re.match('^win', osType.lower()))
   except AttributeError:
      log.info("Unable to get the VC platform for VC host %s" % vcHost)
      raise
   except Exception as e:
      log.info("Unable to connect to VC host %s : %s" % (vcHost, str(e)))
      raise