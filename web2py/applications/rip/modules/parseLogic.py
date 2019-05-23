import re

analysis_array = {'hvc': '151: 0x10b8 (4,280) ',
        'applmgmt': '76: 0x7a0 (1,952) ', 'statsmonitor': '0: 0x0 (0) ', 'analytics': '643: 0x5cb8 (23,736) ',
        'rhttpproxy': '0: 0x0 (0) ', 'vapi-endpoint': '912: 0x6d60 (28,000) ', 'vsm': '202: 0x1d90 (7,568) ',
        'vmonapi': '71: 0x6a8 (1,704) ', 'vcha': '9: 0x138 (312) ', 'updatemgr': '1: 0x48 (72) ',
        'vsan-health': '75: 0x708 (1,800) ', 'vmware-vpostgres': '68: 0x10c0 (4,288) ',
        'eam': '376: 0x2fb0 (12,208) ', 'cis-license': '470: 0x2f50 (12,112) ', 'certificatemanagement': '131: 0xef8 (3,832) ',
        'sca': '420: 0x3140 (12,608) ', 'pschealth': '0: 0x0 (0) ', 'perfcharts': '470: 0x3af0 (15,088) ',
        'content-library': '957: 0x8778 (34,680) ', 'lookupsvc': '363: 0x27c8 (10,184) ',
        'trustmanagement': '153: 0x1108 (4,360) ', 'vpxd-svcs': '880: 0x5690 (22,160) '}

output=str1.split('\n')

for service_analyzed in service_list:
    # main_logger.debug("THREAD - %s - Result %s"%(service_analyzed,final_result_array[service_analyzed]))
    analysis_array = str(final_result_array[service_analyzed]).split(':')
    chunks_leaked = analysis_array[0]
    mem_leaks = analysis_array[1]
    final_output += '{:^25}{:^25}{:^30}'.format(service_analyzed, chunks_leaked, mem_leaks) + "\n"