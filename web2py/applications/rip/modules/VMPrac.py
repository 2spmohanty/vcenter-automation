import pyVmomi
from pyVmomi import vim, vmodl

def find_obj(si, name, vimtype, threaded=False):
    """
    Find an object in vSphere by it's name and return it
    """

    content = si.content
    obj_view = content.viewManager.CreateContainerView(content.rootFolder, vimtype, True)
    obj_list = obj_view.view

    for obj in obj_list:
        if threaded:
            print('THREAD %s - Checking Object "%s"' % (name, obj.name))
        else:
            print('Checking object "%s"' % obj.name)
        if obj.name == name:
            if threaded:
                print('THREAD %s - Found object %s' % (name, obj.name))
            else:
                print('Found object %s' % obj.name)
            return obj
    return None

def get_container_view(service_instance, obj_type, container=None):
    """
    Get a vSphere Container View reference to all objects of type 'obj_type'
    It is up to the caller to take care of destroying the View when no longer
    needed.
    Args:
        obj_type (list): A list of managed object types
    Returns:
        A container view ref to the discovered managed objects
    """
    if not container:
        container = service_instance.content.rootFolder

    view_ref = service_instance.content.viewManager.CreateContainerView(
        container=container,
        type=obj_type,
        recursive=True
    )
    return view_ref

def collect_properties(service_instance, view_ref, obj_type, path_set=None,
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
                if desired_vm in prop.val :
                    properties[prop.val] = obj.obj
                else:
                    pass
        return properties
    except Exception, e:
        print "The exception inside collector_properties " + str(e)
    return properties

