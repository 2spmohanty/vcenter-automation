import sys
import os
import os.path
import multiprocessing
from six.moves import queue
from errno import ENOENT
from misc import IsWindows, GetTcRoot, IsMacOsX
import tvpxglobals
import time
import StringIO
import socket


# Import paramiko and pycrypto for SSH calls. paramiko-1.7.6 only works with
# pycrypto <= 2.0.x.

# TODO: 64-bit paramiko or pycrypto is broken. The build team likely needs
# to rebuild paramiko and/or pycrypto. This can be verified by compiling or
# installing paramiko and pycrypto locally, and then running test-vpx.py.

applianceshHistory = dict()

tcRoot = GetTcRoot()
ecdsaPath = os.path.join(tcRoot, 'noarch', 'ecdsa-0.11', 'lib',
                            'python2.6', 'site-packages')
paramikoPath = os.path.join(tcRoot, 'noarch', 'paramiko-1.16.0', 'lib',
                            'python2.7', 'site-packages')
pycryptoPath = os.path.join(tcRoot, 'lin32', 'pycrypto-2.6', 'lib',
                               'python2.7', 'site-packages')


sys.path.insert(0, ecdsaPath)
sys.path.insert(0, paramikoPath)
sys.path.insert(0, pycryptoPath)

import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
import paramiko


class SSHProcess(multiprocessing.Process):
   '''Process object that connects to a host and runs a command over ssh.'''

   def __init__(self, cmd, host=None, user=None,
                pwd=None, timeout=None, queue=None, errQueue=None,
                xterm=False):
      multiprocessing.Process.__init__(self)
      self.cmd = cmd
      self.host = host
      self.user = user
      self.pwd = pwd
      self.sshTimeout = timeout  # Seconds
      self.queue = queue
      self.errQueue = errQueue
      self.ssh = None  # paramiko.SSHClient
      self.cmd_return_code = multiprocessing.Value("i", -1)
      self.xterm = xterm

   def run(self):
      '''
      Override multiprocessing.Process's run() method with our own that
      executes a command over ssh.
      '''

      try:
         key_file = '/etc/skyscraper/esx.pem'
         self.ssh = paramiko.SSHClient()
         self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
         if tvpxglobals.standaloneMode and os.path.exists(key_file):
            self.ssh.connect(hostname=self.host, username=self.user,
                             password=self.pwd, timeout=self.sshTimeout,
                             key_filename=key_file)
         else:
            self.ssh.connect(hostname=self.host, username=self.user,
                             password=self.pwd, timeout=self.sshTimeout)

         if self.cmd:
            self._send_command()
      except KeyboardInterrupt:
         pass
      except (paramiko.SSHException, paramiko.AuthenticationException) as e:
         if self.errQueue:
            # Workaround paramiko bug (BadAuthenticationType is not
            # serializable)
            if isinstance(e, paramiko.BadAuthenticationType):
               e = paramiko.AuthenticationException(e.__str__())
            self.errQueue.put(e)
      except Exception as e:
         if self.errQueue:
            # Always convert to string in case exception is not serializable
            self.errQueue.put(Exception("%r" % e))
      finally:
         self.ssh.close()
         #Allow the process to join even when items added to queue are not
         #consumed.
         self.queue.cancel_join_thread()
         self.errQueue.cancel_join_thread()

   def _send_command(self):
      '''Send the command to the remote host.'''

      if IsWindows() and self.xterm:
         # Required when the output from ssh session is > 1000 bytes
         chan = self.ssh._transport.open_session()
         chan.get_pty('xterm')
         chan.settimeout(self.sshTimeout)
         chan.exec_command(self.cmd)
         stdin = chan.makefile('wb', -1)
         stdout = chan.makefile('rb', -1)
         stderr = chan.makefile_stderr('rb', -1)
      else:
        (stdin, stdout, stderr) = self.ssh.exec_command(self.cmd)
      stdoutText = stdout.read().strip()
      stderrText = stderr.read().strip()
      self.cmd_return_code.value = stdout.channel.recv_exit_status()

      if self.queue:
         self.queue.put(stdoutText)
      if self.errQueue:
         self.errQueue.put(stderrText)


class SFTPManager():
   '''Manages remote file operations over ssh.'''

   def __init__(self, host='nimbus-gateway.eng.vmware.com', user='eng_vpx_glob_1',
                pwd='e!uBaqYSa!e^u@eBAWa', timeout=900, queue=None, errQueue=None):
      self.host = host
      self.user = user
      self.pwd = pwd
      self.sshTimeout = timeout  # Seconds
      self.queue = queue
      self.errQueue = errQueue
      self.ssh = None  # paramiko.SSHClient
      self.sftp = None # paramiko.SFTPClient

   def InitiateSFTPSession(self):
      '''
      Initiates SSH session with host and opens up a SFTP client for use
      with file operations
      '''

      try:
         self.ssh = paramiko.SSHClient()
         self.ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
         self.ssh.connect(hostname=self.host, username=self.user,
                          password=self.pwd, timeout=self.sshTimeout)
         self.sftp = self.ssh.open_sftp()
      except KeyboardInterrupt:
         pass
      except (paramiko.SSHException, paramiko.AuthenticationException) as e:
         if self.errQueue:
            self.errQueue.put(e)

   def MakeRemoteDir(self, path):
      '''Makes directory in the remote host'''

      if self.sftp:
         self.sftp.mkdir(path)

   def ListRemoteDir(self, path):
      '''Lists the contents of remote directory'''

      remoteFileList = []
      if self.sftp:
         remoteFileList = self.sftp.listdir(path)

      return remoteFileList

   def RemoveRemoteDir(self, path):
      '''Removes the remote directory'''

      if self.sftp:
         self.sftp.rmdir(path)

   def GetRemoteFile(self, remotePath, localPath):
      '''Gets the remote file in the localPath specified'''

      try:
         if self.sftp:
            self.sftp.get(remotePath,localPath)
      except Exception as e:
         if self.errQueue:
            self.errQueue.put(e)

   def PutToRemoteFile(self, localPath, remotePath):
      '''Copies a local file to the remotePath specified'''

      try:
         if self.sftp:
            self.sftp.put(localPath, remotePath)
      except Exception as e:
         if self.errQueue:
            self.errQueue.put(e)

   def ChangeFileMode(self, filePath, mode):
      '''Change the mode (permissions) of a file '''

      try:
         if self.sftp:
            self.sftp.chmod(filePath, mode)
      except Exception as e:
         if self.errQueue:
            self.errQueue.put(e)

   def RemoveRemoteFile(self, remotePath):
      '''Removes a remote file'''

      try:
         if self.sftp:
            self.sftp.remove(remotePath)
      except IOError:
         pass

   def CheckFileExists (self, remotePath):
      try:
         if self.sftp:
            self.sftp.stat(remotePath)
      except IOError as e:
         if e.errno == ENOENT:
            #error code if file doesn't exist
            return False
      except Exception as e:
         if self.errQueue:
            self.errQueue.put(e)
         return False
      return True

   def TerminateSFTPSession(self):
      '''Closes the SFTP session and the associated SSH session'''
      if self.sftp is not None:
         self.sftp.close()
      if self.ssh is not None:
         self.ssh.close()
      self.sftp = None
      self.ssh = None

def RunCmdOverSSH(cmd, host, user,pwd, timeout=3600, xterm=False):
   '''Wrapper for SSHProcess() to run a single command.'''
   global applianceshHistory

   prefix = 'pi shell '
   inHistory = host in applianceshHistory
   if inHistory and applianceshHistory[host]:
      cmd = prefix + cmd

   stdout, stderr = '', ''
   stdoutQueue = multiprocessing.Queue()
   errQueue = multiprocessing.Queue()
   process = SSHProcess(cmd, host=host, user=user, pwd=pwd, timeout=timeout,
                        queue=stdoutQueue, errQueue=errQueue, xterm=xterm)
   try:
      process.start()

      try:
         err = errQueue.get(True, timeout)
         if isinstance(err, Exception):
            raise err
         else:
            stderr = err
      except queue.Empty:
         stderr = None

      try:
         stdout = stdoutQueue.get(True, timeout)

      except queue.Empty:
         stdout = None

      # The join(...) MUST BE called after all queues are consumed check this
      # from multiprocessing python 2.x documentation:
      #
      # If a child process has put items on a queue (and it has not used JoinableQueue.cancel_join_thread()),
      # then that process will not terminate until all buffered items have been flushed to the pipe.
      #
      # This means that if you try joining that process you may get a deadlock unless you are sure that all
      # items which have been put on the queue have been consumed.
      #
      # I hit this deadlock when the ssh command dumps a lot of info in stdout.
      process.join(timeout)
   finally:
      if process.is_alive():

         process.terminate()

   if not inHistory and stdout is not None:
      #The output on Vcenter6.5 for applicance shell starts with
      #'Unknown command:'
      if ((stdout.startswith('appliancesh: ') and \
            stdout.endswith(': invalid command')) or
         (stdout.startswith('Unknown command:'))):
         applianceshHistory[host] = True
         return RunCmdOverSSH(cmd, host, user, pwd, timeout)
      else:
         applianceshHistory[host] = False

   rc = process.cmd_return_code.value
   if process.exitcode:
      rc |= process.exitcode
   return rc, stdout, stderr


def CustomRunSsh(cmd,vc,user,passw,timeout=120):
   exit_status = None
   stdout0 = None
   stderr0 = None
   try:
      ssh = paramiko.SSHClient()
      ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
      ssh.connect(vc, username=user, password=passw)
      chan = ssh.get_transport().open_session()
      chan.settimeout(3600)
      try:
         #print ("Debug: The Command to be Run is "+cmd)
         chan.exec_command(cmd)
         contents = StringIO.StringIO()
         error = StringIO.StringIO()
         while not chan.exit_status_ready():
            if chan.recv_ready():
               data = chan.recv(1024)
               # print "Indside stdout"
               while data:
                  contents.write(data)
                  data = chan.recv(1024)

            if chan.recv_stderr_ready():
               error_buff = chan.recv_stderr(1024)
               while error_buff:
                  error.write(error_buff)
                  error_buff = chan.recv_stderr(1024)

         exit_status = chan.recv_exit_status()
      except socket.timeout:
         raise socket.timeout

      stdout0 = contents.getvalue()
      stderr0 = error.getvalue()
   except Exception, e4:
      print("Error while connecting to remote session: %s" % str(e4))
   finally:
      return exit_status,stdout0,stderr0

