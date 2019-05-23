# -*- coding: utf-8 -*-

#  This is an app-specific example router
#
#  This simple router is used for setting languages from app/languages directory
#  as a part of the application path:  app/<lang>/controller/function
#  Language from default.py or 'en' (if the file is not found) is used as
#  a default_language
#
# See <web2py-root-dir>/examples/routes.parametric.example.py for parameter's detail
#-------------------------------------------------------------------------------------
# To enable this route file you must do the steps:
#
# 1. rename <web2py-root-dir>/examples/routes.parametric.example.py to routes.py
# 2. rename this APP/routes.py to APP/routes.py
#    (where APP - is your application directory)
# 3. restart web2py (or reload routes in web2py admin interfase)
#
# YOU CAN COPY THIS FILE TO ANY APPLICATION'S ROOT DIRECTORY WITHOUT CHANGES!

"""

from fileutils import abspath
from languages import read_possible_languages

possible_languages = read_possible_languages(abspath('applications', app))
#NOTE! app - is an application based router's parameter with name of an
#            application. E.g.'welcome'

routers = {
    app: dict(
        default_language = possible_languages['default'][0],
        languages = [lang for lang in possible_languages
                           if lang != 'default']
    )
}
"""
#NOTE! To change language in your application using these rules add this line
#in one of your models files:
#   if request.uri_language: T.force(request.uri_language)


routes_in=(
    ('/','/rip/Home/index'),
    ('/Home', '/rip/Home/index'),
    ('/opStatus/opstats','/rip/opStatus/opstats'),
    ('/vmOperation/vmApi','/rip/vmOperation/vmApi'),
    ('/vmOperation/vmPowerOps','/rip/vmOperation/vmPowerOps'),
    ('/vmOperation/vmClone','/rip/vmOperation/vmClone'),
    ('/vcOperation/vcApi','/rip/vcOperation/vcApi'),
    ('/vcOperation/vcHeapAnalysis','/rip/vcOperation/vcHeapAnalysis'),
    ('/dcOperation/dcApi','/rip/dcOperation/dcApi'),
    ('/vcOperation/vcMemGrowth','/rip/vcOperation/vcMemGrowth'),
    ('/vcOperation/vpxdMemLeak','/rip/vcOperation/vpxdMemLeak')
)
routes_out=(
    ('/rip/Home/index','/'),
    ('/rip/Home/index','/Home'),
    ('/rip/opStatus/opstats','/opStatus/opstats'),
    ('/rip/vmOperation/vmApi','/vmOperation/vmApi'),
    ('/rip/vmOperation/vmPowerOps','/vmOperation/vmPowerOps'),
    ('/rip/vmOperation/vmClone','/vmOperation/vmClone'),
    ('/rip/vcOperation/vcApi','/vcOperation/vcApi'),
    ('/rip/vcOperation/vcHeapAnalysis','/vcOperation/vcHeapAnalysis'),
    ('/rip/dcOperation/dcApi','/dcOperation/dcApi'),
    ('/rip/vcOperation/vcMemGrowth','/vcOperation/vcMemGrowth'),
    ('/rip/vcOperation/vpxdMemLeak','/vcOperation/vpxdMemLeak')
)