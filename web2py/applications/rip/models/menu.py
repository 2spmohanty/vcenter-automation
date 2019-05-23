response.logo = A(IMG(_src=URL('static','images/logo1.png'),_href=URL('default','index')))
response.title = settings.title
response.subtitle = settings.subtitle
response.app_uri=settings.app_uri
response.meta.author = '%(author)s <%(author_email)s>' % settings
response.meta.keywords = settings.keywords
response.meta.description = settings.description
response.menu = [
(T('Home'),URL('Home','index')==URL(),URL('Home','index'),[]),
(T('VC Operation'),URL('vcOperation','vcApi')==URL(),URL('vcOperation','vcApi'),[]),
(T('VM Operation'),URL('vmOperation','vmApi')==URL(),URL('vmOperation','vmApi'), []),
(T('User Operation Status'),URL('opStatus','opStatusUser')==URL(),URL('opStatus','opStatusUser'),[])]
