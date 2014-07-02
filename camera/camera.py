import common.log as logging
import common.config as Conf

logger = logging.getLogger()

'''
-------------
Camera Object
-------------
'''

class CameraException (Exception):
    def __init__(self, reason):
        self.reason = reason  # string with exception information

class Camera (object):
    def __init__(self):
        self.path = ""
        self.filename = ""
        self.fileformat = ""
        self.size = {'width': 0, 'height': 0}

    def capture(self, filename):
        pass
