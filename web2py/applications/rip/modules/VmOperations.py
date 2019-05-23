import pyVmomi
from pyVmomi import vim, vmodl
from DatacenterPrac import Login,GetCluster,GetDatacenter,get_obj,GetClusters
from clusterPrac import GetHostsInClusters
import status
from VMPrac import find_obj,get_container_view,collect_properties
import multiprocessing
from multiprocessing.dummy import Pool as ThreadPool
import time



def vm_ops_handler(vm_name, vm_object, operation,final_result_dict,maxwait = 5):


    vm = vm_object
    if vm and operation.lower() == "off":

        power_off_task = vm.PowerOff()

        run_loop = True
        while run_loop:
            info = power_off_task.info
            if info.state == vim.TaskInfo.State.success:
                run_loop = False
                final_result_dict[vm_name] = "Power off success."
                break
            elif info.state == vim.TaskInfo.State.error:
                if info.error:
                    final_result_dict[vm_name] = "Power off has quit with error: %s"%info.error

                else:
                    final_result_dict[vm_name] = "Power off has quit with cancelation"

                run_loop = False
                break
            time.sleep(maxwait)

    elif vm and operation.lower() == "on":

        power_off_task = vm.PowerOn()

        run_loop = True
        while run_loop:
            info = power_off_task.info
            if info.state == vim.TaskInfo.State.success:
                run_loop = False
                final_result_dict[vm_name] = "Power on success."
                time.sleep(maxwait)
                break
            elif info.state == vim.TaskInfo.State.error:
                if info.error:
                    final_result_dict[vm_name] = "Power on has quit with error: %s" % (info.error)

                else:
                    final_result_dict[vm_name] = "Power on has quit with cancelation"

                run_loop = False
                break
            time.sleep(maxwait)

    elif operation != "on" or operation != "off":
        final_result_dict[vm_name] = "Operation %s not implemented."%operation




def vm_ops_handler_wrapper(args):
    """
    Wrapping arround vm_ops_handler
    """
    return vm_ops_handler(*args)



def executePowerOps(vcIp, vcUser, vcPassword,dcName,clusterName,operation,pattern_array,vm_array,maxwait):
    # Synchronized Object to Hold Results

    final_result_dict = {}

    try:
        si = Login(vcIp, vcUser, vcPassword)
    except Exception, e:
        resp = str(e)
        return dict(stat=resp, status=status.HTTP_403_FORBIDDEN)
    try:
        dcMor = find_obj(si, dcName, [vim.Datacenter], False)
        clusterMor = GetCluster(dcMor, clusterName, si)
        for pattern in pattern_array:
            vm_properties = ["name"]
            view = get_container_view(si, obj_type=[vim.VirtualMachine], container=clusterMor)
            vm_data = collect_properties(si, view_ref=view, obj_type=vim.VirtualMachine, path_set=vm_properties,include_mors=True, desired_vm=pattern)

            if any(vm_data):
                pass
            else:
                resp = 'Finding VM matching pattern %s failed .' % pattern
                return dict(stat=resp,status = status.HTTP_412_PRECONDITION_FAILED)

            vm_specs = []
            pool = ThreadPool(10)
            for vm_name, vm_object in vm_data.iteritems():
                vm_specs.append((vm_name, vm_object, operation, final_result_dict, maxwait))

            pool.map(vm_ops_handler_wrapper, vm_specs)
            pool.close()
            pool.join()
    except Exception,e:
        return "Power operation failed due to %s."%(e)



    return dict(final_result_dict)



############################### Cloning Operation #####################

synchObj=multiprocessing.Manager()
vm_result_list=synchObj.list()


def vm_clone_operation(si,template_vm,datacenter,clones,specdict):
    global vm_result_list
    cls = specdict["cluster"]
    content = si.RetrieveContent()
    cluster = get_obj(content, [vim.ClusterComputeResource], cls)
    resource_pool = cluster.resourcePool
    folder = datacenter.vmFolder
    datastoresMors = datacenter.datastore
    dsname = specdict["datastore"]
    dsmor = None
    for datastore in datastoresMors:
        if datastore.info.name == dsname:
            dsmor = datastore
            break
    hostMors = GetHostsInClusters(datacenter, [cls], 'connected')
    hostname = specdict.get("host", None)
    hostmor = None
    if hostname:
        for hostitem in hostMors:
            if hostitem.name == hostname:
                hostmor = hostitem
                break

    relocate_spec = vim.vm.RelocateSpec()
    relocate_spec.pool = resource_pool
    relocate_spec.datastore = dsmor
    if hostmor:
        relocate_spec.host = hostmor

    power = False

    if  specdict["power"] == "on":
        power = True



    vmresult = {}
    basename = specdict["basename"]
    for i in range(clones):
        vm_name = basename + "-" + str(i)
        try:
            clone_spec = vim.vm.CloneSpec(powerOn=power, template=False, location=relocate_spec)
            task = template_vm.Clone(name=vm_name, folder=folder, spec=clone_spec)
            run_loop = True
            while run_loop:
                info = task.info

                if info.state == vim.TaskInfo.State.success:
                    vm = info.result
                    run_loop = False
                    vmresult[vm_name] = "Created"
                elif info.state == vim.TaskInfo.State.running:
                    pass
                elif info.state == vim.TaskInfo.State.queued:
                    pass
                elif info.state == vim.TaskInfo.State.error:
                    errormsg=None
                    try:
                        errormsg = info.error
                    except Exception, e:
                        vmresult[vm_name] = str(e)

                    if errormsg:
                        vmresult[vm_name] = errormsg

                    else:
                        vmresult[vm_name] = "Cancelled"
                    run_loop = False
                    break

                time.sleep(10)
        except Exception, e:
            vmresult = ["Failure while initiating cloning %s"%str(e)]

    vm_result_list.append(vmresult)

def collect_vm_properties(service_instance, view_ref, obj_type, path_set=None,
                       include_mors=False,desired_vm=None):
    """
    Collect properties for managed objects from a view ref
    Returns:
        A list of properties for the managed objects
    """

    collector = service_instance.content.propertyCollector

    # Create object specification to define the starting point of
    # inventory navigation
    obj_spec = pyVmomi.vmodl.query.PropertyCollector.ObjectSpec()
    obj_spec.obj = view_ref
    obj_spec.skip = True

    # Create a traversal specification to identify the path for collection
    traversal_spec = pyVmomi.vmodl.query.PropertyCollector.TraversalSpec()
    traversal_spec.name = 'traverseEntities'
    traversal_spec.path = 'view'
    traversal_spec.skip = False
    traversal_spec.type = view_ref.__class__
    obj_spec.selectSet = [traversal_spec]

    # Identify the properties to the retrieved
    property_spec = pyVmomi.vmodl.query.PropertyCollector.PropertySpec()
    property_spec.type = obj_type

    if not path_set:
        property_spec.all = True

    property_spec.pathSet = path_set

    # Add the object and property specification to the
    # property filter specification
    filter_spec = pyVmomi.vmodl.query.PropertyCollector.FilterSpec()
    filter_spec.objectSet = [obj_spec]
    filter_spec.propSet = [property_spec]

    # Retrieve properties
    props = collector.RetrieveContents([filter_spec])

    properties = {}
    try:
        for obj in props:
            for prop in obj.propSet:

                if prop.val == desired_vm:
                    properties['name'] = prop.val
                    properties['obj'] = obj.obj
                    return properties
                else:
                    pass
    except Exception, e:
        print "The exception inside collector_properties " + str(e)
    return properties



def vm_clone_handler_wrapper(args):
    return vm_clone_operation(*args)

def VMFullClones(vcitem):
    cloneresult = {}



    vcname = vcitem["vcname"]
    user = vcitem["username"]
    passw = vcitem["password"]
    dcarray = vcitem["dc"]
    for dcitem in dcarray:
        dcname = dcitem["dcname"]
        templatearray = dcitem["templates"]
        pool = ThreadPool(4)
        vm_specs = []

        for templateitem in templatearray:
            templatename = templateitem["template"]
            container = templateitem["container"]
            clones = templateitem["clones"]
            specdict = templateitem["clonespecs"]

            #print templatename + " will be cloned to " + str(clones) + " with Base name " +  basename+ "-" + " with specs " + "VC " + vcname + " " + str(specdict)
            si = Login(vcname,user, passw)
            content = si.RetrieveContent()
            dcMor = GetDatacenter(name=dcname, si=si)

            clusterMorList = GetClusters(dcMor, [container])
            desiredClusterMor = None

            for item in clusterMorList:
                desiredClusterMor = item

            template_vm = None

            if templatename and desiredClusterMor:
                vm_properties = ["name"]
                view = get_container_view(si, obj_type=[vim.VirtualMachine], container=desiredClusterMor)
                try:

                    vm_data = collect_vm_properties(si, view_ref=view,
                                                 obj_type=vim.VirtualMachine,
                                                 path_set=vm_properties,
                                                 include_mors=True, desired_vm=templatename)
                    if vm_data['name'] == templatename:
                        template_vm = vm_data['obj']
                except Exception,e:
                    cloneresult[templatename] = "Template Not Found due to error %s"%str(e)


            if template_vm is None:
                template_vm = get_obj(content, [vim.VirtualMachine], templatename)

            if template_vm is None:
                cloneresult[templatename] = "Template Not Found"
                continue




            vm_specs.append([si,template_vm,dcMor,clones,specdict])


        pool.map(vm_clone_handler_wrapper, vm_specs)

        pool.close()
        pool.join()

    cloneresult["result"] = list(vm_result_list)

    return cloneresult


















