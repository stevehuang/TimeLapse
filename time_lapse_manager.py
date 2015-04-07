import common.log as logging
#from camera.camera import WebCam
#from camera.camera import CameraException
import camera.camera_manager as cameraManager
import ConfigParser
import common.config as Conf
import os
import re
import service.process as process
import signal

Options = [
    Conf.DirOpt(name='working_directory',
                short='w',
                group='app',
                default="$HOME/.timelapse/",
                help = 'folder for application data'),
    Conf.FileOpt(name='photo_file',
                short   = 'p',
                group   = 'app',
                default = "$HOME/.timelapse/snapshot.jpg",
                help    = 'output file for the photo taken'),
    Conf.IntOpt(name    = 'timeout_level1',
                group   = 'app',
                default = 10,
                help    = 'time elapsed (in mins) before notifying user a note of concern'),
    Conf.IntOpt(name    = 'timeout_level2',
                group   = 'app',
                default = 20,
                help    = 'time elapsed (in mins) after first alert before notifying user again. Will continue sending notice every timeout_level2'),
    Conf.StrOpt(name    ='log_level',
                group   = 'app',
                default = 'DEBUG',
                help    = 'set the log level. options are: NOTSET, DEBUG, INFO, WARNING, ERROR, CRITICAL'),
    Conf.ListOpt(name    = 'cloud',
                 group   = 'app',
                 default = ['dropbox'],
                 help    = 'name of cloud service to use (options are dropbox)'),
    Conf.ListOpt(name    = 'phone',
                 group   = 'app',
                 default = ['googleVoice'],
                 help    = 'name of phone service to use (options are googleVoice)'),
    Conf.ListOpt(name    = 'camera',
                 group   = 'app',
                 default = ['fswebcam'],
                 help    = 'name of camera to use (options are fswebcam)'),
    Conf.FileOpt(name    = 'log_file',
                 group   = 'app',
                 default = None,
                 help    = 'log file to output data to')
]

logger = logging.getLogger()
CONF = Conf.Config
CONF.registerOpt(Options)

class TimeLapseManager (object):

    MAIN_SECTION="app"
    LOG_LEVEL="log_level"
    APP_DIRECTORY="working_directory"
    TIMEOUT_1 = "timeout_level1"
    TIMEOUT_2 = "timeout_level2"

    def __init__ (self):
        path = "/home/huanghst/"
        conf_file=".fswebcm.conf"
        self.camera_manager = cameraManager.CameraManager()
        self.camera = None
        self.app_directory = self.APP_DIRECTORY
        self.timeout_1 = self.TIMEOUT_1
        self.timeout_2 = self.TIMEOUT_2
        self.config = None
        self.photo_file = CONF.importOpt(module='time_lapse_manager', name='photo_file', group='app')
        self.trainingDone = False

    def pre_hook (self):
        self.camera_manager.setup()
        camera_name= CONF.importOpt(module='time_lapse_manager', name='camera', group='app')
        self.camera = self.camera_manager.get_camera(camera_name[0])

# main run loop for the application
#

    def run (self):
        self.trainingDone = True
        #os.kill(pid, signal.SIGKILL)
                
        if (self.camera is not None):
            try:
                filename = self.camera.capture(self.photo_file)
                if filename is not None:
                    logger.debug("filename = "  + filename + "\n")
            except CameraException as ex:
                logger.info(ex.reason)
