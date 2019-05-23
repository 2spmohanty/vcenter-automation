__author__ = 'smrutim'

from pyVmomi import vim
#from logging import error, warning, info, debug
from DatacenterPrac import GetAllClusters,GetClusters,GetCluster
from VDSprac import wait_for_task
import time
import re
import simpleTimer
#import logging
#from threadPool import ThreadPool
import DatacenterPrac


def GetHostsInCluster(datacenter, clusterName=None, connectionState=None):
    """
    Return list of host objects from given cluster name.

    @param datacenter: datacenter object
    @type datacenter: Vim.Datacenter
    @param clusterName: cluster name
    @type clusterName: string
    @param connectionState: host connection state ("connected", "disconnected", "notResponding"), None means all states.
    @typr connectionState: string
    """

    if clusterName != None:
        return GetHostsInClusters(datacenter, [clusterName], connectionState)
    else:
        print("clusterName is NoneType")
        return
############# Added for Register VM #####################################

def GetRunningHostsInCluster(datacenter, clusterName=None, connectionState=None):
    """
    Return list of host objects from given cluster name.

    @param datacenter: datacenter object
    @type datacenter: Vim.Datacenter
    @param clusterName: cluster name
    @type clusterName: string
    @param connectionState: host connection state ("connected", "disconnected", "notResponding"), None means all states.
    @typr connectionState: string
    """

    if clusterName != None:
        return GetRunningHostsInClusters(datacenter, [clusterName], connectionState)
    else:
        print("clusterName is NoneType")
        return

def GetRunningHostsInClusters(datacenter, clusterNames=[], connectionState=None):
    """
    Return list of host objects from given cluster names.

    @param datacenter: datacenter object
    @type datacenter: Vim.Datacenter
    @param clusterNames: cluster name list
    @type clusterNames: ClusterObjectMor[]
    @param connectionState: host connection state ("connected", "disconnected", "notResponding"), None means all states.
    @typr connectionState: string
    """

    if len(clusterNames) == 0:
        clusterObjs = GetAllClusters(datacenter)
    else:
        clusterObjs = clusterNames

    hostObjs = []
    if connectionState == None:
        hostObjs = [h for cl in clusterObjs for h in cl.host]
    else:
        hostObjs = [h for cl in clusterObjs for h in cl.host if h.runtime.connectionState == connectionState and not h.runtime.inMaintenanceMode]

    return hostObjs

def GetHostsInClusters(datacenter, clusterNames=[], connectionState=None):
    """
    Return list of host objects from given cluster names.

    @param datacenter: datacenter object
    @type datacenter: Vim.Datacenter
    @param clusterNames: cluster name list
    @type clusterNames: string[]
    @param connectionState: host connection state ("connected", "disconnected", "notResponding"), None means all states.
    @typr connectionState: string
    """

    if len(clusterNames) == 0:
        clusterObjs = GetAllClusters(datacenter)
    else:
        clusterObjs = GetClusters(datacenter, clusterNames)

    hostObjs = []
    if connectionState == None:
        hostObjs = [h for cl in clusterObjs for h in cl.host]
    else:
        hostObjs = [h for cl in clusterObjs for h in cl.host if h.runtime.connectionState == connectionState]

    return hostObjs

def GetVmFolders(si):
    content = si.RetrieveContent()
    datacenter = content.rootFolder.childEntity[0]
    vmFolder = datacenter.vmFolder
    vmFolderList = vmFolder.childEntity
    return vmFolderList



def GetVms(datacenter, clusterNames=[], matchStr=''):
    """
    Return list of VM objects from given cluster names. Using this has performance impact
    if trying to scan whole inventory.

    @param datacenter: datacenter object
    @type datacenter: Vim.Datacenter
    @param clusterNames: cluster name list
    @type clusterNames: string[]
    @param matchStr: matched string for VM which followed regex pattern of re.findall()
    @type matchStr: string
    """

    if len(clusterNames) == 0:
        print("clusterNames list has 0 items, get all VMs from datacenter '%s'" \
              % datacenter.name)

    def findVmsInResPool(vms, parent, filter):
        if isinstance(parent, vim.VirtualApp) or isinstance(parent, vim.ResourcePool):
            vms.extend(parent.vm)
            for rp in parent.resourcePool:
                findVmsInResPool(vms, rp, filter)

    def findVmsInFolders(vms, parent, filter):
        for e in parent.childEntity:
            if isinstance(e, vim.VirtualMachine):
                vms.append(e)
            elif isinstance(e, vim.Folder):
                findVmsInFolders(vms, e, filter)
            elif isinstance(e, vim.VirtualApp) or isinstance(e, vim.ResourcePool):
                findVmsInResPool(vms, e, filter)

    vmobjs = []
    t = simpleTimer.Timer()
    if matchStr == '':
        if len(clusterNames) == 0:
            # retrieve all VM
            with t:
                findVmsInFolders(vmobjs, datacenter.vmFolder, "")
            print("Get all (%d) vms took %f sec" %(len(vmobjs), t.interval))
        else:
            # retrieve VM for specified Clusters
            with t:
                vmobjs = [v for cl in GetClusters(datacenter, clusterNames) for h in cl.host for v in h.vm]
            print("Get all (%d) vms took %f sec" %(len(vmobjs), t.interval))
    else:
        if len(clusterNames) == 0:
            with t:
                vmobjs = [v for v in findVmsInFolders(vmobjs, datacenter.vmFolder, "") if len(re.findall(matchStr, v.name)) > 0]
            print("Get all (%d) vms took %f sec" %(len(vmobjs), t.interval))
        else:
            with t:
                vmobjs = [v for cl in GetClusters(datacenter, clusterNames) for h in cl.host
                        for v in h.vm if len(re.findall(matchStr, v.GetName())) > 0]
            print("Get all (%d) vms took %f sec" %(len(vmobjs), t.interval))

    if len(vmobjs) == 0:
        print("No VM registered for cluster %s" %str(clusterNames))

    return vmobjs

def ReconfigureDRSHA(datacenter, clusterNames, drs = False, ha = False, sleepTime = 120):
    """
    Reconfigure HA or DRS for given cluster names.

    @param datacenter: datacenter object
    @type datacenter: Vim.Datacenter
    @param clusterNames: cluster name list
    @type clusterNames: string[]
    @param drs:  drs flag
    @type drs: bool
    @param ha:  drs flag
    @type ha: bool
    @param sleepTime: configuration buffer time between each cluster, if configure
                     drs only, it can be shortened.
    @type sleepTime: int
    """
    clusterObjs = GetClusters(datacenter, clusterNames)
    timer = simpleTimer.Timer()


    for cl in clusterObjs:
        cspec = vim.cluster.ConfigSpecEx()
        adjustedSleepTime = sleepTime
        _reconfig = False
        if cl.configuration.drsConfig.enabled != drs:
            print("Reconfigure DRS for %s to %s" %(cl.name, str(drs)))
            cspec.drsConfig = vim.cluster.DrsConfigInfo(enabled = drs)
            _reconfig = True
            # enable DRS task is quick, we can use less time to do config,
            # but it will restore to the specified time if HA is enabled.
            adjustedSleepTime = 15
        else:
            print("No Need to reconfigure DRS for %s" %cl.name)

        if cl.configuration.dasConfig.enabled != ha:
            print("Reconfigure HA for %s to %s" %(cl.name, str(ha)))
            cspec.dasConfig = vim.cluster.DasConfigInfo( enabled = ha)
            _reconfig = True
            # restore sleep to given time
            adjustedSleepTime = sleepTime
        else:
            print("No Need to reconfigure HA for %s" %cl.name)

        if not _reconfig:
            continue

        with timer:
            try:
                task = cl.ReconfigureEx(cspec, True)
                wait_for_task(task)
            except Exception, e:
                print(e)

        print("[%s] Configure HA/DRS takes %.3f sec" %(cl.name, timer.interval))

def MoveClustersToHostFolder(datacenter, hostFolderName = None, clusterNames = []):
    """
    Move given cluster names to specified hostFolder.

    Side effect:
        We may have the same cluster name under different folders. The moved
        cluster may not the one you want to move.

    @param datacenter: datacenter object
    @type datacenter: Vim.Datacenter
    @param clusterNames: cluster name list
    @type clusterNames: string[]
    """
    if hostFolderName == None:
        raise Exception("HostFolderName is None")

    hostfolder = DatacenterPrac.GetHostFolder(datacenter, hostFolderName)
    if hostfolder == None:
        raise Exception("Can not find hostFolder name '%s' in '%s'" \
            % (hostFolderName, datacenter.name))

    clusterObjs = GetClusters(datacenter, clusterNames)
    movedObjs = []
    for cl in clusterObjs:
        if cl.parent == hostfolder:
            print("Cluster '%s' is already in hostFolder '%s', skip moving." \
                 %(cl.name, hostFolderName))
        else:
            # Move Cluster cl to hostfolder
            print("moving cluster %s to %s" %(cl.name, hostFolderName))
            movedObjs.append(cl)

    if len(movedObjs) == 0:
        print("No need to move clusters")
    else:
        try:
            t = hostfolder.MoveIntoFolder_Task(movedObjs)
            wait_for_task(t)
            print("Move clusters to hostFolder '%s' is done." %(hostFolderName))
        except vim.Fault.DuplicateName:
            print("Duplicate name error: %s" %t.info.error.localizedMessage)
        except Exception, e:
            print str(e)

def AddHost(datacenter, host, user="root", pwd="ca$hc0w", clusterName=None):
    """
    Add host to given cluster.

    @param datacenter: : datacenter object
    @type datacenter: Vim.Datacenter
    @param host: host name
    @type host: string
    @param user: user name
    @type user: string
    @param pwd: password
    @type pwd: string
    @param clusterName: cluster name
    @type clusterName: string
    """

    if host != None:
        AddHosts(datacenter, [host], user, pwd, clusterName)
    else:
        raise Exception("Host is NoneType")

def AddHosts(datacenter, hosts, user="root", pwd="ca$hc0w", clusterName=None):
    """
    Add hosts to given cluster. If clusterName is not given, it will add hosts
    to datacenter.

    Side effect:
    Expect *all* hosts have the same userid and password. If they have different
    credentials, use AddHost() to add host one-by-one.

    @param datacenter: : datacenter object
    @type datacenter: Vim.Datacenter
    @param hosts: host name list
    @type hosts: string[]
    @param user: user name
    @type user: string
    @param pwd: password
    @type pwd: string
    @param clusterName: cluster name
    @type clusterName: string
    """

    cluster = None
    if clusterName != None :
        cObj = GetCluster(datacenter, clusterName)
        if cObj == None:
            print("Cluster %s not found, will add hosts to Datacenter" % clusterName)
        else:
            cluster = cObj

    if len(hosts) == 0:
        raise Exception("host objects is not specify")

    for host in hosts:
        ssltp = None
        try:
            datacenter.QueryConnectionInfo(host, 443, user, pwd)
        except vim.fault.NoHost:
            print("Host %s not found." %str(host))
            continue
        except vim.fault.SSLVerifyFault,svf:
            print("AddHost: auto-accepting host %s SSL certificate" %str(host))
            ssltp = svf.thumbprint

        cspec = vim.host.ConnectSpec(force = True,
                                   hostName = host,
                                   userName = user,
                                   password = pwd,
                                   sslThumbprint = ssltp)

        try:
            if cluster != None:
                t = cluster.AddHost(cspec, True, None, None)
            else:
                t = datacenter.hostFolder.AddStandaloneHost(cspec, None, True, None)

            wait_for_task(t)
            print("Add hostSystems is done.")
        except vim.fault.DuplicateName, f:
            print("Host %s already exists." %f.object.name)
        except Exception, e:
            raise





def GetAllResourcePool(datacenter):

    """
    Return list of resourcePool objects from given datacenter.

    @param datacenter: datacenter object
    @type datacenter: Vim.Datacenter
    """

    clusterListObj = GetAllClusters(datacenter)
    respool = []
    for c in clusterListObj:
        respool.append(c.resourcePool)
        """
        for r in c.resourcePool:
            respool.append(r.resourcePool)
        """
    return respool