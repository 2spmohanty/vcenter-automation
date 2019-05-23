from customSSH import RunCmdOverSSH

import re
import multiprocessing
from multiprocessing.dummy import Pool as ThreadPool
import lxml
from lxml import html


servicesList = ['vsphere-client', 'vsphere-ui','vmware-certificatemanagement',
                'vmware-content-library','vmware-vapi-endpoint','vmware-eam',
                'vmware-vpxd-svcs','vmware-cis-license','vmware-sps']
solutionUserDict = {'vsphere-client':'vsphere-client','vsphere-ui':'vsphere-ui','vmware-certificatemanagement':'root',
                    'vmware-content-library':'content-library','vmware-vapi-endpoint':'vapiEndpoint','vmware-eam':'eam',
                    'vmware-vpxd-svcs':'root','vmware-cis-license':'root','vmware-sps':'root',  }

#Synchronized Object to Hold Results
synchObj=multiprocessing.Manager()
final_result_dict=synchObj.dict()

def _CreateAnalysisDirectory(dumpDir,serviceName,host, username, password):
    try:
        remdDirCmd = "rm -rf " + dumpDir + serviceName
        ###print("THREAD - %s - Removing Analysis Directory." % (serviceName))
        (ret, stdout, stderr) = RunCmdOverSSH(remdDirCmd, host, username, password)
        ###print("THREAD - %s - Creating Analysis Directory return code %s." % (serviceName, ret))
        createDirCmd = "mkdir -p "+ dumpDir + serviceName
        ###print("THREAD - %s - Creating Analysis Directory." % (serviceName))
        (ret, stdout, stderr) = RunCmdOverSSH(createDirCmd, host, username, password)
        ###print("THREAD - %s - Creating Analysis Directory return code %s." % (serviceName,ret))
        changePermissionDir = "chmod 777 " + dumpDir + serviceName
        ###print("THREAD - %s - Giving permission to Analysis Directory." % (serviceName))
        (ret, stdout, stderr) = RunCmdOverSSH(changePermissionDir, host, username, password)
        ###print("THREAD - %s - Giving permission to Analysis Directory return code %s." % (serviceName, ret))
    except Exception, e:
        raise Exception("Problem while Creation of Analysis Directory: %s"%str(e))





def _PushMemoryJar(dumpDir,host, username, password):
    remJar = "rm -rf "+ dumpDir + "/mat " + dumpDir + "/Mem*"
    ##print ("Removing existing JAR if any if exits.")
    (ret, stdout, stderr) = RunCmdOverSSH(remJar, host, username, password)
    getmemJarPath = "wget https://10.172.46.209/rip/static/Corefiles/MemoryAnalyzer_Linux.zip --no-check-certificate -P" + dumpDir
    (ret, stdout, stderr) = RunCmdOverSSH(getmemJarPath, host, username, password)
    if ret == 0:
        ##print("THREAD - MAIN - Memory Jar import successful.")
        ##print("THREAD - MAIN - Unzip Memory jars.")
        try:
            unizpMemJar = "unzip " + dumpDir + "MemoryAnalyzer_Linux.zip -d " + dumpDir
            ###print("THREAD - MAIN - Unzip Memory jars command %s"%unizpMemJar)
            (ret, stdout, stderr) = RunCmdOverSSH(unizpMemJar, host, username, password)
            if ret == 0:
                jarPath = dumpDir + "mat/"
                ###print("THREAD - MAIN - The memory jar path is %s"%jarPath)
                return jarPath
        except Exception, e:
            ###print("THREAD - MAIN - Unzip Memory jars failed.")
            raise Exception(str(e))
    else:
        raise Exception("Failure while getting utility for Memory analysis from remote server. %s" % (stderr))

def _TakeHeapDump(serviceName,host, username, password, jmapPath,dumpDir ):
    try:
        solutionUser = solutionUserDict[serviceName]
        hprofFile = dumpDir + serviceName+"/"+serviceName+".hprof"
        dumpCmd = "sudo -u "+ solutionUser + " " + jmapPath +"jmap -dump:format=b,file="+ \
                  hprofFile +"  `pidof "+ serviceName +".launcher`"
        ###print("THREAD - %s - Issuing dump command. %s"%(serviceName,dumpCmd))

        (ret, stdout, stderr) = RunCmdOverSSH(dumpCmd, host, username, password,timeout=72000)
        ###print("THREAD - %s - Issuing dump command return code. %s" % (serviceName, str(ret)))
        if ret == 0:
            ##print("THREAD - %s - Heap dump successful."%(serviceName))
            return hprofFile
        else:
            raise Exception(str(stderr))
    except Exception,e:
        raise Exception(str(e))


"""
def _AnalyzeHeapDump_wrapper(args):

    #Wrapping around mem_analysis_handler

    return _AnalyzeHeapDump(*args)
"""


def _AnalyzeHeapDump(serviceName,jarPath,dumpDir,hprofFile,host, username, password):
    # Logic tp parse the hprof output.
    resultDict = {}
    pattern1 = """
        .*?(One | [\d,]+)\s+instance[s]{,1}.*?of	#Find the Number of Instance
        .*?\"(.*?)\"                              	#Find the instance name
        .*?\"(.*?)\"                                #Who invoked the class
        .*?([,\d]+)                                 #Bytes occupied
        """

    pattern2 = """
        .*?The\s+class\s+\"(.*?)\"	#The instance Name
        .*?\"(.*?)\"				#Who invoked the class
        .*?(\d+.*)?\(				#Bytes occupied
        .*?(\w+)\s+(?=instance).* 	#Number of Instance
        """


    scriptPath = jarPath + "ParseHeapDump.sh"
    #Adding -vmargs -Xmx4g -XX:-UseGCOverheadLimit it seems vsphere-ui analysis is hitting the JVM overlimit
    generateAnalysis = scriptPath + " " + hprofFile
    if serviceName == "vsphere-ui" :
        generateAnalysis = generateAnalysis + " -vmargs -Xmx4g -XX:-UseGCOverheadLimit"

    ###print("THREAD - %s - Generating Required Files for Heap Analysis." % (serviceName))

    try:
        ## SSH Code for Files
        (ret, stdout, stderr) = RunCmdOverSSH(generateAnalysis, host, username, password,timeout=72000)
        if ret == 0:
            #Only in case of Return code Go Further to Generate Leak uspect
            try:
                leakSuspectCmd = scriptPath + " " + hprofFile + " " + "org.eclipse.mat.api:suspects"
                #print("THREAD - %s - Finding Leak Suspects in the Heap." % (serviceName))
                ## SSH Code for Leak Suspects
                (ret, stdout, stderr) = RunCmdOverSSH(leakSuspectCmd, host, username, password,timeout=72000)
                if ret == 0:
                    try:

                        unzipSupects = "unzip " + dumpDir + serviceName + "/" + serviceName + \
                                       "_Leak_Suspects.zip -d " + dumpDir + serviceName + "/"
                        ## SSH Code for Unzipping Leak Suspects
                        #print("THREAD - %s - Unzip command. %s" % (serviceName,unzipSupects))
                        (ret, stdout, stderr) = RunCmdOverSSH(unzipSupects, host, username, password,timeout=72000)
                        if ret == 0:
                            stdout = None
                            ret = None
                            stderr = None
                            try:
                                readIndexFile = "cat " + dumpDir + serviceName + "/index.html"
                                #print("THREAD - %s - Reading Leak Suspects in the Heap Analyzer output." % (serviceName))
                                # SSH Code to read the Leak Suspects
                                (ret, stdout, stderr) = RunCmdOverSSH(readIndexFile, host, username, password,timeout=72000)
                                if ret == 0:
                                    ###print("THREAD - %s - Parsing leak analyzer output." % (serviceName))
                                    # resultDict[serviceName] = serviceName

                                    tree = lxml.html.fromstring(stdout)
                                    problem_statement_box = tree.find_class('important')
                                    suspectCount = 0

                                    if not problem_statement_box:
                                        leakSuspect = "Leak Suspect " + str(suspectCount)
                                        resultDict[leakSuspect] = "No Leaks observed"
                                    else:
                                        for a_problem in problem_statement_box:
                                            data = a_problem.text_content()
                                            dataToWork = data.encode('ascii', 'ignore').decode('ascii')
                                            match1 = re.match(pattern1, dataToWork, re.X)
                                            match2 = re.match(pattern2, dataToWork, re.X)

                                            if match1:
                                                suspectCount = suspectCount + 1
                                                leakSuspect = "Leak Suspect " + str(suspectCount)

                                                resultDict[leakSuspect] = {'Number of Instance': match1.group(1),
                                                                           'Instance Name': match1.group(2),
                                                                           'Loaded By': match1.group(3),
                                                                           'Bytes': match1.group(4)}
                                            elif match2:
                                                suspectCount = suspectCount + 1
                                                leakSuspect = "Leak Suspect " + str(suspectCount)
                                                resultDict[leakSuspect] = {'Number of Instance': match2.group(4),
                                                                           'Instance Name': match2.group(1),
                                                                           'Loaded By': match2.group(2),
                                                                           'Bytes': match2.group(3)}
                                            else:
                                                leakSuspect = "Leak Suspect " + str(suspectCount)
                                                resultDict[leakSuspect] = "No Leaks observed"
                                else:
                                    #print("Failure while reading leak analyzer output. %s" % str(stderr) + serviceName)
                                    resultDict["Error"] = resultDict.get("Error"," ") + "Failure while reading leak analyzer output. %s" % str(stderr)

                            except Exception, e: #Exception while parsing Leak Suspects
                                #print("Failure while reading leak analyzer output. %s" % str(stderr) + serviceName)
                                resultDict["Error"] = resultDict.get(serviceName," ") + " Failure while reading leak analyzer output. %s" % str(e)
                        else: #Do not Proceed if there failure while unzipping Leak Suspects
                            #print("Failure while Unzipping Leak Suspect. %s" % str(stderr) + serviceName)
                            resultDict["Error"] = resultDict.get(serviceName," ") + "Failure while Unzipping Leak Suspect . %s" % str(stderr)

                    except Exception, e: #Exception while Unzipping the Leak Suspects
                        resultDict["Error"] = resultDict.get("Error"," ") + "Failure while Unzipping Leak Suspect . %s" % str(e)




                else: #Do not Proceed if there failure while getting Leak Suspects
                    resultDict["Error"] = resultDict.get("Error"," ") + "Failure while running Leak Suspect API. %s" % str(stderr)


            except Exception, e: # Execption while Getting Leak Suspects
                resultDict["Error"] = resultDict.get("Error"," ") + "Failure while running Leak Suspect API. %s" % str(e)

        else: # Return code not Zero for Generating Leak for generating Required file for heap Analysis
            resultDict["Error"] = "Failure while generating required Files for Heap Analysis. %s"%str(stderr)

    except Exception,e: # Generating HPROF Analysis Failed Catch Block
        resultDict["Error"] = final_result_dict.get(serviceName, " ") + "Failure while generating required Files for Heap Analysis. %s" % str(e)


    final_result_dict[serviceName] = resultDict



def heap_analysis_handler_wrapper(args):
    """
    Wrapping around mem_analysis_handler
    """
    return _AnalysisSteps(*args)

def _AnalysisSteps(host,username, password,serviceName,dumpDir,jarPath,jmapPath,heap_analysis_pool,heap_analysis_result_pool,hprofname=None):
    try:
        _CreateAnalysisDirectory(dumpDir,serviceName,host, username, password)

        if hprofname:
            # This Snip triggers if HPROF is specified by User.
            new_location = dumpDir + serviceName

            try:
                # Copy the User Specified HPROF to Analysis Location.
                copyHprof = "cp " + hprofname + " " + new_location
                (ret, stdout, stderr) = RunCmdOverSSH(copyHprof, host, username, password)
                only_hprof = hprofname.split("/")[-1]
                hprofname = new_location + "/" + only_hprof
            except Exception,e:
                errorMsg="Failure working with user specified HPROF %s"%str(e)
                final_result_dict[serviceName] = errorMsg


        else:
            #This Snip triggers if there is no existing HPROF specified by User.
            try:
                hprofname = _TakeHeapDump(serviceName, host, username, password, jmapPath, dumpDir)
            except Exception,e:
                errorMsg = "Failure generating Heap Dump %s" % str(e)
                final_result_dict[serviceName] = errorMsg

        if hprofname is None:
            final_result_dict[serviceName] = "No HPROF found to be analyzed"

        else:
            try:
                heap_analysis_result_pool.append(
                    heap_analysis_pool.apply_async(_AnalyzeHeapDump, (serviceName, jarPath, dumpDir, hprofname, host, username, password)))

            except Exception, e:
                errorMsg = "Error while analyzing Heap Dump %s" % str(e)
                final_result_dict[serviceName] = errorMsg


    except Exception, e:
        errorMsg = "Error while creating Analysis Directory %s" % str(e)
        final_result_dict[serviceName] = errorMsg

"""

def _InitiateHeapAnalysis(host,username,password,jmapPath,dumpDir,service_name,hprofname=None):
    finalReturnResult = {}
    if dumpDir :
        dumpDir = dumpDir + "rip/"
        remDir = "rm -rf " + dumpDir
        try:
            (ret, stdout, stderr) = RunCmdOverSSH(remDir, host, username, password)
        except Exception, e:
            finalReturnResult["Failure"] = "Removing Master Dump directory failed due to %s"%str(e)
            return finalReturnResult

        dirCreateCmd = "mkdir -p " + dumpDir

        try:
            (ret, stdout, stderr) = RunCmdOverSSH(dirCreateCmd, host, username, password)
        except Exception, e:
            finalReturnResult["Failure"] = "Creating Master Dump Analysis directory failed due to %s" % str(e)
            return finalReturnResult

    else:
        finalReturnResult["Failure"] = "No Master Dump directory specified."
        return finalReturnResult

    if hprofname:

        filelistCmd = "ls -l " + hprofname
        try:
            (ret, stdout, stderr) = RunCmdOverSSH(filelistCmd, host, username, password)
        except Exception, e:
            finalReturnResult["Failure"] = "User specifed HPROF could not be listed. %s."%str(e)
            return finalReturnResult




    if service_name[0] == "all":
        service_name = ['vsphere-client', 'vsphere-ui', 'vmware-certificatemanagement',
                        'vmware-content-library',
                        'vmware-vapi-endpoint', 'vmware-eam', 'vmware-vpxd-svcs', 'vmware-cis-license',
                        'vmware-sps']
    else:
        service_name = service_name

    jarPath = None
    try:
        jarPath = _PushMemoryJar(dumpDir, host, username, password)
    except Exception , e:
        finalReturnResult["Failure"] = "Memory Analysis jar is not available on VC %s " %str(e)


    if jarPath is None:
        #finalReturnResult["Failure"] = "Memory Analysis jar is not available on VC %s . Analysis quitting. Please check manually or file a bug to smrutim@vmaware.com"
        return finalReturnResult

    #Instantiating Threadpool

    threads = 10
    pool = ThreadPool(threads)
    heap_analysis_pool = ThreadPool(threads)
    heap_analysis_result_pool = []
    service_specs = []

    try:
        for service in service_name:
            service_specs.append((host, username, password, service, dumpDir, jarPath,jmapPath,heap_analysis_pool, heap_analysis_result_pool,hprofname))

        pool.map(heap_analysis_handler_wrapper, service_specs)
        pool.close()
        pool.join()
        # main_logger.debug("THREAD - main - Closing the core analysis thread pool.")
        heap_analysis_pool.close()
        heap_analysis_pool.join()

    except Exception, e:
        finalReturnResult["Failure"] = str(e)
        return finalReturnResult

    finalReturnResult["Result"] = dict(final_result_dict)

    return finalReturnResult
"""

def _TriggerHeapAnalysis(host, username, password,jmapPath,dumpDir,jarPath,service_name, hprofname):
    finalReturnResult = {}

    threads = 10
    pool = ThreadPool(threads)
    heap_analysis_pool = ThreadPool(threads)
    heap_analysis_result_pool = []
    service_specs = []

    try:
        for service in service_name:
            service_specs.append((host,username, password,service,dumpDir,jarPath,jmapPath,
                                  heap_analysis_pool,heap_analysis_result_pool,hprofname))

        pool.map(heap_analysis_handler_wrapper, service_specs)
        pool.close()
        pool.join()
        # main_logger.debug("THREAD - main - Closing the core analysis thread pool.")
        heap_analysis_pool.close()
        heap_analysis_pool.join()

    except Exception, e:
        finalReturnResult["Failure"] = str(e)
        return finalReturnResult

    heapModuleResult = dict(final_result_dict)
    finalReturnResult["Result"] = heapModuleResult
    # Get Uptime Days and Hours

    try:
        uptimecmd = "uptime -p"
        (ret, stdout, stderr) = RunCmdOverSSH(uptimecmd, host, username, password,timeout=1800)
        if ret != 0:
            finalReturnResult["Uptime"] = str(stderr)
        else:
            finalReturnResult["Uptime"] = str(stdout)
    except Exception, e:
        finalReturnResult["Uptime"] = "Could not obtain duration of uptime %s." % str(e)

    #Get Build Details

    try:
        uptimecmd = "grep 'BUILDNUMBER' /etc/vmware/.buildInfo | cut -d\":\" -f2"
        (ret, stdout, stderr) = RunCmdOverSSH(uptimecmd, host, username, password,timeout=1800)
        if ret != 0:
            finalReturnResult["Build"] = str(stderr)
        else:
            finalReturnResult["Build"] = str(stdout)
    except Exception, e:
        finalReturnResult["Build"] = "Could not obtain Build %s." % str(e)




    return finalReturnResult
