from pyVim.connect import SmartConnect
from pyVim.connect import Disconnect
from pyVmomi import types, Vmodl, Vim, vim
from pyVim.task import WaitForTask
from pyVim.invt import findFolders, findVms, findHost, startFind
import pyVim.vimApiGraph
import pyVim.connect
import time
import argparse
import atexit
import urllib2
import urlparse
import base64
import ssl
import logging
import datetime
import getpass
from time import sleep
from multiprocessing.dummy import Pool as ThreadPool
import sys

def CompareCounts(moCounts, invtCounts):
   countsMismatch = False
   diffCounts = {}
   for key, invtValue in invtCounts.items():
      moCount = moCounts[key + 'Mo']
      if moCount != invtValue:
         diffCounts[key + 'Mo'] = abs(moCount - invtValue)
         countsMismatch = True
   return (countsMismatch, diffCounts)

def GetMoID(obj):
   moId = "%s" % obj
   if moId is None:
      return moId
   if 'vim' in moId:
      #strip quotes
      moId = moId[1:-1]
      words = moId.split(":");
      return words[1]
   return moId

def MakePropertySpecs(managedObjectSpecs):
   propertySpecs = []
   for managedObjectSpec in managedObjectSpecs:
      moType = managedObjectSpec[0]
      all = managedObjectSpec[1]

      propertySpec = Vmodl.Query.PropertyCollector.PropertySpec()
      propertySpec.SetType(reduce(getattr, moType.split('.'), types))
      propertySpec.SetAll(all)
      propertySpecs.append(propertySpec)
   return propertySpecs

def GetObjectsCountInVCInventory(si, invtObjMap):
   ''' Get Count of Objects in VC Inventory
       keys in invtObjMap all start with Caps '''
   dcRefs = si.content.rootFolder.GetChildEntity()

   content = si.RetrieveContent()
   propColl = content.GetPropertyCollector()

   objectSpec = Vmodl.Query.PropertyCollector.ObjectSpec()
   objectSpec.obj = si
   objectSpec.skip = False
   objectSpec.selectSet = pyVim.vimApiGraph.BuildMoGraphSelectionSpec()

   fetchProp = False
   # Build up a property spec that consists of all managed object types
   classNames = invtObjMap.keys() # Getting the class names
   propertySpecs = map(lambda x: [x, fetchProp], classNames)
   propertySpecs = MakePropertySpecs(propertySpecs)

   objectSpecs = [objectSpec]

   filterSpec = Vmodl.Query.PropertyCollector.FilterSpec()
   filterSpec.propSet = propertySpecs
   filterSpec.objectSet = objectSpecs

   filterSpecs = Vmodl.Query.PropertyCollector.FilterSpec.Array([filterSpec])

   retrieveOpt = Vmodl.Query.PropertyCollector.RetrieveOptions()
   retrieveRes = propColl.RetrievePropertiesEx(filterSpecs, retrieveOpt)
   if retrieveRes:
      ocList = retrieveRes.objects
      token = retrieveRes.token
   else:
      token = None
      ocList = []
   while token:
      retrieveRes = propColl.ContinueRetrievePropertiesEx(token)
      tempOcList = retrieveRes.objects
      token = retrieveRes.token
      ocList.extend(tempOcList)

   # Generating the invtCounts map from ocList
   invtCounts = {}
   moIdList = set()
   for objType, objName in invtObjMap.items():
      invtCounts[objName] = 0

   for objContent in ocList:
      objRef = objContent.obj
      objType = objRef.__class__.__name__
      moIdList.add(GetMoID(objRef))
      if objType in invtObjMap.keys():
         invtCounts[invtObjMap[objType]] += 1
   return (invtCounts, moIdList)