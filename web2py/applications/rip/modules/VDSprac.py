__author__ = 'smrutim'
import time
from pyVmomi import vim
from pyVim.connect import SmartConnect, Disconnect
import atexit
import getpass
import logging
import re
import ssl
import DatacenterPrac

def wait_for_task(task):
    """ wait for a vCenter task to finish """
    task_done = False
    while not task_done:
        if task.info.state == 'success':
            return task.info.result

        if task.info.state == 'error':
            print "there was an error"
            task_done = True

def Login(host, user, pwd, port=443):
    context = ssl._create_unverified_context()
    si = SmartConnect(host=host,user=user,pwd=pwd,port=port,sslContext=context)
    atexit.register(Disconnect, si)
    return si

class Vds:
   obj = None
   name = None
   dvpgs = {}

   def create(self,name,dc,spec=None):
      # check if vds object is already set
      if self.obj != None:
         raise Exception("Object(%s) is already set" % self.obj)

      if spec == None:
         spec = vim.DistributedVirtualSwitch.CreateSpec()
         cspec = vim.DistributedVirtualSwitch.ConfigSpec()
         cspec.name = name
         spec.configSpec = cspec

      try:
         t = dc.networkFolder.CreateDistributedVirtualSwitch(spec)
         wait_for_task(t)
         self.obj = t.info.result
         self.name = name
         return t
      except vim.Fault.AlreadyExists:
         print("Failed to create vDS '%s': AlreadyExist" %name)
      except vim.Fault.InvalidName:
         print("Failed to create vDS '%s': InvalidName" %name)
      except Exception,e:
         raise Exception("Failed to create vDS(%s). Exception:%s" % (name,e))

   def find(self,name,node):
      if isinstance(node,vim.dvs.VmwareDistributedVirtualSwitch):
         if node.name == name:
            return node
         return None

      elif isinstance(node,vim.Folder):
         vds = None
         for childNode in node.childEntity:
            vds = self.find(name,childNode)
            if vds != None:
               break
         return vds

      else:
         return None

   def set(self,name,dc):
      self.obj = self.find(name,dc.networkFolder)
      if self.obj != None:
         self.name = name
      else:
         raise Exception("VDS(%s) not found" % name)

   def remove(self):
      if self.obj == None:
         return None

      try:
         t = self.obj.Destroy()
         wait_for_task(t)
         return t
      except Exception,e:
         print e
         return None

   def addPortgroup(self,name,num_ports=128,binding='earlyBinding',
                    vlan_id=None):
      if self.obj == None:
         raise Exception("Object is not set")

      spec = vim.dvs.DistributedVirtualPortgroup.ConfigSpec()
      spec.name = name
      spec.type = binding
      spec.numPorts = int(num_ports)

      pconf = vim.dvs.VmwareDistributedVirtualSwitch.VmwarePortConfigPolicy()
      if vlan_id != None:
         pconf.vlan = vim.dvs.VmwareDistributedVirtualSwitch.VlanIdSpec()
         pconf.vlan.vlanId = int(vlan_id)
         pconf.vlan.inherited = False
      spec.defaultPortConfig = pconf

      dvpg = self.DvPortgroup(self)
      return dvpg.create(name,spec)

   def setPortgroup(self,name):
      if self.obj == None:
         raise Exception("Object is not set")

      dvpg = self.DvPortgroup(self)
      return dvpg.set(name)

   def addMultiPortgroups(self,name=None,num_ports=1,vlan_id_start=0,
                          vlan_id_step=1,num_dvpg=1,spec=None):
      if self.obj == None:
         raise Exception("Object is not set")

      specs = []
      curr_vlan_id = int(vlan_id_start)

      for i in range(int(num_dvpg)):
         if spec == None:
            curr_spec = vim.dvs.DistributedVirtualPortgroup.ConfigSpec()
            curr_spec.type = 'earlyBinding'
         else:
            curr_spec = spec

         curr_spec.name = '%s-%s' % (name,i)
         curr_spec.numPorts = int(num_ports)

         pconf = vim.dvs.VmwareDistributedVirtualSwitch.VmwarePortConfigPolicy()
         if curr_vlan_id != 0:
            pconf.vlan = vim.dvs.VmwareDistributedVirtualSwitch.VlanIdSpec()
            pconf.vlan.vlanId = curr_vlan_id
            pconf.vlan.inherited = False
         curr_spec.defaultPortConfig = pconf

         specs.append(curr_spec)
         curr_vlan_id += int(vlan_id_step)

      try:
         t = self.obj.AddPortgroups(specs)
         return t
      except Exception,e:
         print(e)
         return None

   def removePortgroup(self,name):
      if self.obj == None:
         raise Exception("Object is not set")

      if not name in self.dvpgs:
         return None

      return self.dvpgs[name].remove()

   def configureNicTeaming(self,dvpg_name,
                           lb_policy=None,
                           beacon=None,
                           notify=None,
                           failback=None):
      if self.obj == None:
         raise Exception("Object is not set")

      if not dvpg_name in self.dvpgs:
         raise Exception("DvPortgroup(%s) is not set" % (dvpg_name))

      if lb_policy == beacon == notify == failback == None:
         return True

      dvpg = self.dvpgs[dvpg_name]

      # copy existing settings
      spec = vim.dvs.DistributedVirtualPortgroup.ConfigSpec()
      spec.configVersion = dvpg.obj.config.configVersion
      spec.defaultPortConfig = vim.dvs.VmwareDistributedVirtualSwitch\
                               .VmwarePortConfigPolicy()
      spec.defaultPortConfig.uplinkTeamingPolicy = dvpg.obj.config\
                                                   .defaultPortConfig\
                                                   .uplinkTeamingPolicy


      # apply new settings
      spec.defaultPortConfig.uplinkTeamingPolicy.inherited = 0

      # load balancing
      if lb_policy != None:
         spec.defaultPortConfig.uplinkTeamingPolicy.policy.inherited = 0
         spec.defaultPortConfig.uplinkTeamingPolicy.policy.value = lb_policy

      # beacon probing
      if beacon != None:
         spec.defaultPortConfig.uplinkTeamingPolicy.failureCriteria\
         .inherited = 0
         spec.defaultPortConfig.uplinkTeamingPolicy.failureCriteria.checkBeacon\
         .inherited = 0
         spec.defaultPortConfig.uplinkTeamingPolicy.failureCriteria.checkBeacon\
         .value = beacon

      # notify swithces
      if notify != None:
         spec.defaultPortConfig.uplinkTeamingPolicy.notifySwitches.inherited = 0
         spec.defaultPortConfig.uplinkTeamingPolicy.notifySwitches\
         .value = notify

      # failback
      if failback != None:
         spec.defaultPortConfig.uplinkTeamingPolicy.rollingOrder.inherited = 0
         spec.defaultPortConfig.uplinkTeamingPolicy.rollingOrder\
         .value = not(failback)

      return dvpg.reconfigure(spec)

   def addHost(self,hostsystem,nics=[],maxproxyswitchports=256):
      if self.obj == None:
         raise Exception("Object is not set")

      spec = vim.DistributedVirtualSwitch.ConfigSpec()
      spec.configVersion = self.obj.config.configVersion

      hSpec = vim.dvs.HostMember.ConfigSpec()
      hSpec.host = hostsystem
      hSpec.operation = vim.ConfigSpecOperation.add
      hSpec.maxProxySwitchPorts = int(maxproxyswitchports)
      hSpec.backing = vim.dvs.HostMember.PnicBacking()

      for nic in nics:
         pnicSpec = vim.dvs.HostMember.PnicSpec()
         pnicSpec.pnicDevice = nic
         hSpec.backing.pnicSpec.append(pnicSpec)

      spec.host.append(hSpec)

      try:
         t = self.obj.Reconfigure(spec)
         wait_for_task(t)
         return t
      except Exception,e:
         raise Exception("Failed to add host(%s) to vDS(%s). Exception:%s" \
                         % (hostsystem.name,self.name,e))

   def enableNetIORM(self):
      if self.obj == None:
         return None

      try:
         self.obj.EnableNetworkResourceManagement(True)
         return 0
      except Exception,e:
         print(e)
         return None

   def disableNetIORM(self):
      if self.obj == None:
         return None

      try:
         self.obj.EnableNetworkResourceManagement(False)
         return 0
      except Exception,e:
         print(e)
         return None

   class DvPortgroup:
      obj = None
      name = None
      vds = None

      def __init__(self,vds):
         self.vds = vds

      def find(self,name):
         for dvpg in self.vds.obj.portgroup:
            if dvpg.name == name:
               return dvpg
         return None

      def set(self,name):
         self.obj = self.find(name)
         if self.obj != None:
            self.name = name
            self.vds.dvpgs[self.name] = self
            return self.obj
         else:
            raise Exception("DvPortgroup(%s) not found" % name)

      def create(self,name,spec):
         try:
            t = self.vds.obj.AddPortgroups([spec])
            wait_for_task(t)
            self.obj = self.find(name)
            self.name = name
            self.vds.dvpgs[self.name] = self
            return t
         except vim.Fault.DuplicateName:
            #raise Exception("Failed to create dvPortgroup '%s': Duplicate name" \
            #                % (name))
            print("Failed to create dvPortgroup '%s': Duplicate name" % (name))
         except vim.Fault.DvsFault:
            raise Exception("Failed to create dvPortgroup '%s': DVS Fault" \
                            % (name))
         except Exception,e:
            raise Exception("Failed to create dvPortgroup '%s'. Exception:%s" \
                            % (name,e))



      def remove(self):
         if self.obj == None:
            return None

         try:
            t = self.obj.Destroy()
            wait_for_task(t)
            del self.vds.dvpgs[self.name]
            return t
         except Exception,e:
            print(e)
            return None

      def reconfigure(self,spec):
         if self.obj == None:
            raise Exception("Object is not set")

         try:
            t = self.obj.Reconfigure(spec)
            wait_for_task(t)
            return t
         except Exception,e:
            raise Exception("Failed to reconfigure dvPortgroup " + \
                            "(%s). Exception:%s" % (self.name,e))



def CreateVDS(datacenter=None,vdsName=None,vdsVersion='5.0.0',vdsVendor='VMware'):

    """
    Create new Virtual Distributed Switch. Return vds object if success, return
    None if failed.

    @param datacenter: datacenter object
    @type datacenter: Vim.Datacenter
    @param vdsName: VDS name
    @type vdsName: string
    @param vdsVersion: VDS version (4.0.0, 4.1.0, 5.0.0)
    @type vdsVersion: string
    @param vdsVendor: VDS vendor name (VMware, Cisco?)
    @type vdsVendor: string
    """

    if datacenter == None:
        raise Exception("You have to specify datacenter object")
    elif not (isinstance(datacenter, vim.Datacenter)):
        raise Exception(str(datacenter) + " is not a datacenter object")
    else:
        print("datacenter name: " + datacenter.name)

    if vdsName == None:
        raise Exception("You must specify VDS name to create it")

    v = GetVDS(datacenter, vdsName)
    if v != None:
        print("%s is existed in VC" %vdsName)
        return v

    try:
        vds = Vds()
        spec = vim.DistributedVirtualSwitch.CreateSpec()
        configspec = vim.DistributedVirtualSwitch.ConfigSpec()
        productspec = vim.dvs.ProductSpec(vendor=vdsVendor, version = vdsVersion)
        configspec.name = vdsName.strip()
        spec.configSpec = configspec
        spec.productInfo = productspec
        print("Creating a dvSwitch by name : " + vdsName + " version " + vdsVersion)
        vds.create(vdsName, datacenter, spec)
    except Exception, e:
        print(e)
        raise

    print("Create VDS success")
    return vds.obj

def GetVDS(datacenter, vdsName):
    netFolder = datacenter.networkFolder
    vds = None
    children = netFolder.childEntity
    for child in children:
        if  not (isinstance(child, vim.DistributedVirtualSwitch)):
            continue
        if child.name != vdsName:
            continue
        vds = child
        break
    if vds == None:
        print("DVS [" + str(vdsName) + "] not found ")
        return None
    print("found DVS [" + str(vdsName) + "]: " + str(vds))

    return vds

def DeleteVDS(datacenter, vdsName):
    vds = GetVDS(datacenter, vdsName)
    task=vds.Destroy_Task()
    wait_for_task(task)



def GetAllVDS(datacenter=None):
    vdsNetworks = []
    if datacenter == None:
        print("Not specify datacenter object, retrieve all VDS switches from all datacenters")

        si = si = Login("10.146.13.160","administrator@vsphere.local","Admin!23",port=443)
        print("si:" + str(si))
        dcs = DatacenterPrac.GetAllDatacenters(si)
        for dc in dcs:
            children = dc.networkFolder.childEntity
            for child in children:
                print("child entity: " + str(child) + "[" + child.GetName() + "]")
                if  isinstance(child, vim.DistributedVirtualSwitch):
                    vdsNetworks.append(child)
        return vdsNetworks
    else:
        children = datacenter.networkFolder.childEntity
        for child in children:
            print("child entity: " + str(child) + "[" + child.GetName() + "]")
            if  isinstance(child, vim.DistributedVirtualSwitch):
                vdsNetworks.append(child)
        return vdsNetworks

def CreateDVPortgroups(datacenter, vdsName, names, numOfPorts=128, binding='earlyBinding'):
    pass
    """
    if datacenter == None:
        print("Must specify datacenter object")
        raise

    if len(names) == 0:
        print("Cannot create dvPort Group with empty String name")
        raise

    vds = Vds()
    vds.set(vdsName, datacenter)

    for dvpgName in names:
        try:
            vds.addPortgroup(name      = '%s' % dvpgName,
                          num_ports = numOfPorts,
                          binding   = '%s' % binding)

            print("Create dvPortGroup '%s' is done." % (dvpgName))
        except Exception, e:
            print(e)
    """

def GetDVPortgroup(datacenter, dvPortgroupName, vdsName=None):
    if datacenter == None:
        print("specify datacenter object")
        return []
    if dvPortgroupName == None:
        print("specify dvPortgroup name")
        return []

    pg = GetDVPortgroups(datacenter, [dvPortgroupName], vdsName)
    if len(pg) == 0:
        print("Cannot find dvPortgroup '%s'" % dvPortgroupName)
        return None
    else:
        return pg[0]

def GetDVPortgroups(datacenter, dvPortgroupNames, vdsName=None):
    if datacenter == None:
        print("specify datacenter object")
        return []
    if len(dvPortgroupNames) == 0:
        print("specify dvPortgroup name list")
        return []

    if vdsName != None:
        vds = GetVDS(datacenter, vdsName)

    pg = []

    children = datacenter.networkFolder.childEntity

    for child in children:
        if  not (isinstance(child, vim.dvs.DistributedVirtualPortgroup)):
            continue
        if not child.name in dvPortgroupNames:
            continue
        if vdsName != None and vdsName != child.config.distributedVirtualSwitch.name:
            continue
        pg.append(child)
        if len(dvPortgroupNames) == 1:
            break

    if len(pg) == 0:
        if vdsName == None:
            print ("PortGroup [" + str(dvPortgroupNames) + "] not found ")
        else:
            print ("PortGroup [%s] not found in VDS [%s]" %(str(dvPortgroupNames), vdsName))
        return []

    print("found dvportgroup [" + str(dvPortgroupNames) + "]")
    return pg

def DeleteDVPortgroup(datacenter, dvPortgroupName, vdsName=None):
    if datacenter == None:
        raise Exception("specify datacenter object")
    if dvPortgroupName == None:
        raise Exception("specify dvPortgroup name")

    pg = GetDVPortgroup(datacenter, dvPortgroupName, vdsName)
    print("Delete DVPG: %s [%s]"  %(str(pg), dvPortgroupName))
    if pg == None:
        raise Exception("Cannot find dvPortgroup name '%s'" % dvPortgroupName)

    try:
        t = pg.Destroy()
        print("Delete DVPG task: %s" %str(t))
        wait_for_task(t)
        return t
    except Exception,e:
        print(e)

def GetVDSHosts(datacenter, vds):
    if  not (isinstance(vds, vim.DistributedVirtualSwitch)):
        # vds is a plain string.
        print("'%s' is a plain string." %(vds))
        dvs = GetVDS(datacenter, vds)
    else:
        # vds is a Vim.DistributedVirtualSwitch object
        print("'%s' is a VDS." %str(vds))
        dvs = vds
    if dvs == None:
        print("VDS '%s' is not found" %str(vds))
        return None

    try:
        configInfo = dvs.config
        #debug("configInfo: %s" %str(configInfo))
        dvsHostMembers = configInfo.host
    except Exception, e:
        print(e)

    dvsHosts = []

   # create a list of existing hosts in VDS switch
    for dvsHostMember in dvsHostMembers:
        dvsHostConfig = dvsHostMember.config
        host = str(dvsHostConfig.host)
        dvsHosts.append(host)

    return dvsHosts


def AddHostToVDS(datacenter,vdsName,hostList=[],pnics=['vmnic3']):
    dvs = GetVDS(datacenter, vdsName)
    if dvs == None:
        print("VDS '%s' is not found" %vdsName)
        return

    if len(hostList) == 0:
        print("No valid hosts found. skipping addHostToVDS")
        return

    dvsHosts = GetVDSHosts(datacenter, dvs)

    pnicSpecs = []
    pnicSpec = vim.dvs.HostMember.PnicSpec()

    for pnic in pnics:
        pnicSpec.pnicDevice=pnic
        pnicSpecs.append(pnicSpec)

    back = vim.dvs.HostMember.PnicBacking()
    back.pnicSpec=pnicSpecs
    # Assume all hosts have same network backing for VDS
    hostSpecs = []
    print("hostList size: %d" %len(hostList))
    for host in hostList:
        hstr = str(host.name)

        if hstr in dvsHosts:
            print("host %s(%s) already in VDS, SKIP ADDING" %(host.name,hstr))
            continue
        if host.config == None:
            continue

        print(hstr+ " will be added to DVS")
        hostSpec = vim.dvs.HostMember.ConfigSpec()
        hostSpec.operation = vim.ConfigSpecOperation.add
        hostSpec.backing=back
        hostSpec.host=host
        hostSpecs.append(hostSpec)


    if len(hostSpecs) == 0:
        print("#######################################")
        print("No hosts need to be added to VDS switch")
        return
    else:
        print("Adding %d hosts into VDS '%s'" %(len(hostSpecs), vdsName))

    configInfo = dvs.config
    dvsSpec = vim.DistributedVirtualSwitch.ConfigSpec()
    dvsSpec.configVersion=configInfo.configVersion
    dvsSpec.host=hostSpecs

    try:
        task = dvs.ReconfigureDvs_Task(dvsSpec)
        wait_for_task(task)
    except Exception, e:
        raise e


    # Checking procedure
    existingDVSHostNum = len(dvsHosts)
    toBeAddedHostNum = len(hostSpecs)
    newDVSHost = GetVDSHosts(datacenter, dvs)

    if newDVSHost != None:
        newDVSHostNum = len(newDVSHost)
        print("existingDVSHostNum=%d, toBeAddedHostNum=%d, newDVSHostNum=%d"%(existingDVSHostNum, toBeAddedHostNum, newDVSHostNum))
        if newDVSHostNum == (existingDVSHostNum + toBeAddedHostNum) :
            print("Adding %d Hosts to VDS %s is done" %(len(hostSpecs), vdsName))
        else:
            raise Exception("Expecting %d hosts in '%s', but only got %s hosts!"%((existingDVSHostNum + toBeAddedHostNum), dvs.name, newDVSHostNum))
    else:
        raise Exception("No hosts in VDS %s!!!" %vdsName)

    return

def RemoveHostFromVDS(datacenter,vdsName,hostList=[],pnics=['nic4']):
    """
    Remove given hosts from given VDS.

    @param datacenter: datacenter object
    @type datacenter: Vim.Datacenter
    @param vdsName: VDS name
    @type vdsName: string
    @param hostList: host objects list
    @type hostList: Vim.HostSystem[]
    """

    dvs = GetVDS(datacenter, vdsName)
    if dvs == None:
        print("VDS [" + vdsName + "] is not found")
        return

    # create a list of existing hosts in VDS switch
    dvsHosts = GetVDSHosts(datacenter, dvs)

    if len(hostList) == 0:
        #warning("No valid hosts found. skipping removeHostToVDS")
        print("Removing all hosts on %s" %vdsName)
        #return

    # create a list of existing hosts in VDS switch
    dvsHosts = GetVDSHosts(datacenter, dvs)


    # pnicSpec : spec for single pnic
    # pnicSpecs: list of pnic will be used in VDS for single host
    pnicSpecs = []
    pnicSpec = vim.dvs.HostMember.PnicSpec()
    for pnic in pnics:
        pnicSpec.pnicDevice=pnic
        pnicSpecs.append(pnicSpec)

    back = vim.dvs.HostMember.PnicBacking()
    back.pnicSpec=pnicSpecs

    hostSpecs = []
    for host in hostList:
        hstr = str(host)
        if not hstr in dvsHosts:
            print("host %s(%s) is not in VDS, SKIP REMOVING" %(host.GetName(),hstr))
            continue
        if host.config == None:
            continue
        hostSpec = vim.dvs.HostMember.ConfigSpec()
        hostSpec.operation = vim.ConfigSpecOperation.remove
        hostSpec.backing=back
        hostSpec.host=host
        hostSpecs.append(hostSpec)

    if len(hostSpecs) == 0:
        print("#######################################")
        print("No hosts need to be removed from VDS switch")
        return
    else:
        print("Removing %d hosts from VDS '%s'" %(len(hostSpecs), vdsName))

    configInfo = dvs.config
    dvsSpec = vim.DistributedVirtualSwitch.ConfigSpec()
    dvsSpec.configVersion=configInfo.configVersion
    dvsSpec.host=hostSpecs

    try:
        task = dvs.ReconfigureDvs_Task(dvsSpec)
        wait_for_task(task)
    except Exception, e:
        print(e)
        raise

    return

def FindFreePort(datacenter, vdsName, numPorts, dvPortgroup = None):
    """
    Find available ports from given VDS which which can be used for VM.
    return VDS port objects if available.

    @param datacenter: datacenter object
    @type datacenter: Vim.Datacenter
    @param vdsName: VDS name
    @type vdsName: string
    @param numPorts: number of ports will be used for VMs.
    @type numPorts: int
    @param dvPortgroup: dvPortGroup object
    @type dvPortgroup: Vim.Dvs.DistributedVirtualPortgroup
    """

    print("%d ports requested" % (numPorts))

    dvs = GetVDS(datacenter, vdsName)
    if dvs == None:
        print("You must specify VDS name")
        return

    cri = vim.dvs.PortCriteria()
    cri.connected=False
    #cri.SetPortKey(portKeys)
    if dvPortgroup:
        cri.portgroupKey=dvPortgroup.config.key
        cri.inside=True

    portKeys = dvs.FetchDVPortKeys(cri)

    print("Total len of portkeys %d and required %d" % (len(portKeys), numPorts))

    if len(portKeys) < numPorts:
        print("%d ports requested, only %d ports found. Not enough ports to create all VMs"
            % (numPorts, len(portKeys)))
        return []

    cri2 = vim.dvs.PortCriteria()
    cri2.portKey=portKeys[0:numPorts]
    try:
        ports = dvs.FetchDVPorts(cri2)
    except Exception, e:
        print("Problem in retrieving ports: %s" %str(e))
        raise

    return ports




