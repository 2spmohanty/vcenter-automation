__author__ = 'smrutim'
import socket
from gluon.storage import Storage
settings = Storage()

settings.migrate = True
settings.title = 'RIP'
settings.subtitle = 'Rest In Peak'
settings.author = 'Smruti Mohanty'
settings.author_email = 'smrutim@vmware.com'
settings.app_uri = socket.gethostname()
settings.keywords = ''
settings.description = ''
settings.layout_theme = 'Default'
#settings.database_uri = 'postgres://spm:12345678@localhost:5432/mydb'
settings.database_uri = 'sqlite://storage.sqlite'
settings.security_key = 'bb05dd73-42f2-4ad2-a1f7-589476f6a904'
settings.email_server = 'smtp.vmware.com'
settings.email_sender = 'smrutim@vmware.com'
settings.email_login = ''
settings.login_method = ''
settings.login_config = ''
settings.plugins = []
