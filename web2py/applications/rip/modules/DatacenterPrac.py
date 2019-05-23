from pyVmomi import vim
from pyVim.connect import SmartConnect, Disconnect
import atexit
import getpass
import logging
import re
import ssl
import requests

import traceback



def CreateDatacenter (name=None, si=None):
    rootFolder = si.content.rootFolder
    dataCenter = None
    dataCenter = rootFolder.CreateDatacenter(name)
    print(" DataCenter with name : " + name + " created successfully ")
    return dataCenter

def Login(host, user, pwd, port=443):
    context = ssl._create_unverified_context()
    si = SmartConnect(host=host,user=user,pwd=pwd,port=port,sslContext=context)
    atexit.register(Disconnect, si)
    return si

def get_obj(content, vimtype, name):
    obj = None
    container = content.viewManager.CreateContainerView(
        content.rootFolder, vimtype, True)
    for c in container.view:
        if c.name == name:
            obj = c
            break
    return obj

def CreateCluster(datacenter=None, clusterName=None):
    if datacenter == None:
        raise Exception("You have to specify datacenter object")
    elif not (isinstance(datacenter, vim.Datacenter)):
        raise Exception(str(datacenter) + " is not a datacenter object")
    else:
        print("datacenter name: " + datacenter.name)

    if clusterName is None:
        raise ValueError("Missing value for name.")
    if datacenter is None:
        raise ValueError("Missing value for datacenter.")

    if len(clusterName.strip()) == 0:
        raise Exception("Cannot create cluster with empty String name")

    try:
        cluster_spec = vim.cluster.ConfigSpecEx()
        host_folder = datacenter.hostFolder
        cluster = host_folder.CreateClusterEx(name=clusterName, spec=cluster_spec)
        print("Cluster '%s' has been created" % clusterName)
        return cluster
    except vim.fault.DuplicateName:
        print("Cluster '%s' already exists, not creating" % clusterName)
    except Exception, e:
        print("Unable to create a Cluster by Name : " + clusterName)
        raise

    print("Cluster '%s' has been created" % clusterName)

def GetDatacenter(name=None, si=None):
    try:
        content = si.RetrieveContent()
        dcObj=get_obj(content, [vim.Datacenter], name)

    except Exception, e:
        print(e)
        raise
    return dcObj

def GetAllDatacenter(datacenter=None,si=None):
    pass

def GetCluster(datacenter=None, clusterName=None, si=None):
    #Get Cluster Objects
    hostFolder = datacenter.hostFolder
    foundCr = None
    clusterListObj = GetAllClusters(datacenter)
    for cr in clusterListObj:
        if cr.name == clusterName:
            foundCr = cr
            print("\nCluster " + str(cr) + "(" + clusterName +") is found ")
            break
    if foundCr == None:
        print("Cluster [" + clusterName + "] not found in " + datacenter.GetName() + "!!!")
    return foundCr

def GetClusters(datacenter, clusterNames = []):
    """
    Return list of cluster objects from given cluster name.

    @param datacenter: datacenter object
    @type datacenter: Vim.Datacenter
    @param clusterNames: cluster name list
    @type clusterNames: string[]
    """
    foundCr = []
    clusterListObj = GetAllClusters(datacenter)
    print("'%s' has %d clusters." %(datacenter.name, len(clusterListObj)))
    if len(clusterNames) == 0:
        # equivalent to GetAllClusters()
        if len(clusterListObj) == 0:
            print("No Cluster found in %s" % (datacenter.name))
            return []
        else:
            return clusterListObj
    else:
        foundCr = [c for c in clusterListObj if c.name in clusterNames]

    if len(foundCr) == 0:
        print("Cluster '%s' not found in '%s'" % (
            str(clusterNames), datacenter.name))

    return foundCr

def GetAllClusters(datacenter):
    if datacenter == None:
        print("You have to specify datacenter object")
        return []
    elif not (isinstance(datacenter, vim.Datacenter)):
        print(str(datacenter) + " is not a datacenter object")
        return []
    else:
        print("datacenter name: " + datacenter.name)

    hostFolder = datacenter.hostFolder
    allClusterObjList = []
    crs = hostFolder.childEntity
    print("crs: " + str(crs))

    def WalkFolder(folder, allClusterObjList):
        childEntities = folder.childEntity
        for i in range(len(childEntities)):
            WalkManagedEntity(childEntities[i], allClusterObjList)

    def WalkManagedEntity(entity, allClusterObjList):
        if isinstance(entity, vim.Folder):
            WalkFolder(entity, allClusterObjList)
        elif isinstance(entity, vim.ClusterComputeResource):
            allClusterObjList.append(entity)
    if crs == None:
        return []
    for cr in crs:
        WalkManagedEntity(cr, allClusterObjList)

    return allClusterObjList


def GetAllClusterNames(datacenter):
    nameList = []
    print("datacenter: " + str(datacenter))
    clusters = GetAllClusters(datacenter)
    print("clusters: " + str(clusters))
    for entity in clusters:
        nameList.append(entity.name)

    print("nameList: " + str(nameList))
    return nameList

def GetAllClusterSummary(datacenter):
    cpuDetail = []
    clusters = GetAllClusters(datacenter)

    for entity in clusters:
        cpuDetail.append(entity.name + ":"+ str(entity.summary.numCpuCores) + ":" + str(entity.summary.numHosts) + ":" + str(entity.summary.totalCpu) + ":"+str(entity.summary.overallStatus))


    return cpuDetail


def CreateHostFolder(datacenter, hostFolderName):
    """
    Create hostfolder.

    @param datacenter: datacenter object
    @type datacenter: Vim.Datacenter
    @param hostFolderName: hostFolder name
    @type hostFolderName: string
    """
    if datacenter == None:
        raise Exception("You have to specify datacenter object")
    elif not (isinstance(datacenter, vim.Datacenter)):
        raise Exception(str(datacenter) + " is not a datacenter object")
    else:
        print("datacenter name: " + datacenter.name)

    if hostFolderName == None:
        raise Exception("Cannot create hostFolder with empty String name")

    try:
        folder = datacenter.hostFolder.CreateFolder(hostFolderName)
    except vim.fault.DuplicateName:
        print("HostFolder '%s' already exists, not creating" % hostFolderName)
    except Exception, e:
        print("Unable to create a HostFolder by Name : " + hostFolderName)
        raise
    else:
        print("HostFolder '%s' (%s) has been created" \
           % (hostFolderName, str(folder)))


def GetHostFolder(datacenter, hostFolderName = None):
    """
    Get hostfolder object by given names

    @param datacenter: datacenter object
    @type datacenter: Vim.Datacenter
    @param hostFolderName: hostFolder name
    @type hostFolderName: string
    """
    if datacenter == None:
        raise Exception("You have to specify datacenter object")
    elif not (isinstance(datacenter, vim.Datacenter)):
        raise Exception(str(datacenter) + " is not a datacenter object")
    if hostFolderName == None:
        print("You need to specify hostfolder name")
        return None

    hf = GetHostFolders(datacenter, [hostFolderName])
    if len(hf) == 0:
        return None
    else:
        return hf[0]

def GetHostFolders(datacenter, hostFolderNames = []):
    """
    Get hostfolder object list by given names

    @param datacenter: datacenter object
    @type datacenter: Vim.Datacenter
    @param hostFolderNames: hostFolder name list
    @type hostFolderNames: string[]
    """
    if datacenter == None:
        raise Exception("You have to specify datacenter object")
    elif not (isinstance(datacenter, vim.Datacenter)):
        raise Exception(str(datacenter) + " is not a datacenter object")

    hfs = GetAllHostFolders(datacenter)
    foundHf = []
    if len(hostFolderNames) == 0:
        if len(hfs) == 0:
            print("No hostFolders found in datacenter %s" % datacenter.GetName())
            return []
        else:
            return hfs
    else:
        for hfName in hostFolderNames:
            for hf in hfs:
               if hf.name == hfName:
                   foundHf.append(hf)
                   print("HostFolder %s(%s) is found " %(str(hf), hfName))

    if len(foundHf) == 0:
        print("HostFolder [%s] not found in %s" % (str(hostFolderNames), datacenter.GetName()))

    return foundHf

def GetAllHostFolders(datacenter):
    """
    Get all hostfolder object list by given datacenter

    @param datacenter: datacenter object
    @type datacenter: Vim.Datacenter
    """
    if datacenter == None:
        raise Exception("You have to specify datacenter object")
    elif not (isinstance(datacenter, vim.Datacenter)):
        raise Exception(str(datacenter) + " is not a datacenter object")

    hostFolder = datacenter.hostFolder

    allfolderObjList = []
    hfs = hostFolder.childEntity
    print("hfs: " + str(hfs))

    def WalkFolder(folder, allClusterObjList):
        childEntities = folder.childEntity
        for i in range(len(childEntities)):
            WalkManagedEntity(childEntities[i], allClusterObjList)

    def WalkManagedEntity(entity, allClusterObjList):
        if isinstance(entity, vim.Folder):
            allfolderObjList.append(entity)
            WalkFolder(entity, allClusterObjList)

    if hfs == None:
        return []

    for hf in hfs:
        WalkManagedEntity(hf, allfolderObjList)

    return allfolderObjList

def GetAllHosts(datacenter):
    """
    This includes all standalone ESX and ESX under Clusters/hostFolders.


    """
    hosts = []
    allCRObjs=[]

    def WalkFolder(folder, allCRObjs):
        childEntities = folder.childEntity
        for i in range(len(childEntities)):
            WalkManagedEntity(childEntities[i], allCRObjs)


    def WalkManagedEntity(entity, allCRObjs):
        if isinstance(entity, vim.Folder):
            WalkFolder(entity, allCRObjs)
        elif isinstance(entity, vim.ClusterComputeResource) or isinstance(entity, vim.ComputeResource):
            allCRObjs.append(entity)

    for cr in datacenter.hostFolder.childEntity:
        WalkManagedEntity(cr, allCRObjs)

    for entity in allCRObjs:
        hosts = hosts + entity.host

    return hosts
