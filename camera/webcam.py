import camera
import common.log as logging
import subprocess
import re
import common.config as Conf
from types import *

Options = [
    Conf.StrOpt(name    = 'use',
                group   = 'camera.fswebcam',
                default = 'camera.camera:WebCam.factory',
                help    = 'point to the camera python module'),
    Conf.FileOpt(name    = 'config_file',
                 group   = 'camera.fswebcam',
                 default = '$HOME/.garageeye/fswebcam.conf',
                 help    = 'full path to webcam configuration file',
                 sub_group = 'fswebcam'),
    Conf.DirOpt(name     = 'path',
                 group   = 'camera.fswebcam',
                 default = '$HOME/.garageeye/camera',
                 help    = 'full path to webcam files',
                 sub_group = 'fswebcam')
]

logger = logging.getLogger()
CONF = Conf.Config
CONF.registerOpt(Options)

class WebCam (camera.Camera):
    def __init__(self, path="", conf_file="fswebcam.conf"):
        super(WebCam, self).__init__()
        self.confFile = conf_file
        self.path = path
        if type(conf_file)==FileType:
            filename = conf_file.name
        else:
            filename = conf_file
        self.command = 'fswebcam -c '+ filename
#        self.command = 'fswebcam --save ' + self.path

    def capture(self, filename=None):
        ''' captures images based on data from the conf_file <path>/fswebcam.conf
        outputs data to folder <path>/filename '''
        success = 0
        output=None
        errOut=None
        logger.info('capture')
        command = self.command + ' --save ' + filename
        logger.debug('command: ' + command)

        try:
            proc = subprocess.Popen(command.split(), shell=False, \
                                    stdin=subprocess.PIPE,\
                                    stdout=subprocess.PIPE,\
                                    stderr=subprocess.STDOUT)
            (output, errOut) = proc.communicate()
        except Exception as ex:
            logger.info(ex)
            raise CameraException("Pipe error")
        logger.debug('fswebcam output: ' + output)

        if output is not None:
            match = re.search('Writing JPEG image', output)
            if match is not None:
                success=1
        if success==0:
            raise CameraException("fswebcam failed.")
        logger.debug('capture ended ('+str(success) + ')')
        return filename

    @staticmethod
    def factory (conf_vars):
        return WebCam(conf_vars['path'], conf_vars['config_file'])
