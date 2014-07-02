import common.log as logging
#from camera.camera import WebCam
#from camera.camera import CameraException
import camera.camera_manager as cameraManager
import ConfigParser
import common.config as Conf

Options = [
    Conf.DirOpt(name='working_directory',
                short='w',
                group='app',
                default="$HOME/.garageeye/",
                help = 'folder for application data'),
    Conf.DirOpt(name='photo_directory',
                short   = 'p',
                group   = 'app',
                default = "$HOME/Pictures/GarageEye/",
                help    = 'folder for pictures taken'),
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

class GarageEyeManager (object):

    MAIN_SECTION="app"
    LOG_LEVEL="log_level"
    APP_DIRECTORY="working_directory"
    PHOTO_DIRECTORY="photo_directory"
    TIMEOUT_1 = "timeout_level1"
    TIMEOUT_2 = "timeout_level2"

    def __init__ (self):
        path = "/home/huanghst/"
        conf_file=".fswebcm.conf"
        self.camera_manager = cameraManager.CameraManager()
        self.camera = None
        self.app_directory = self.APP_DIRECTORY
        self.photo_directory = self.PHOTO_DIRECTORY
        self.timeout_1 = self.TIMEOUT_1
        self.timeout_2 = self.TIMEOUT_2
        self.config = None

    def pre_hook (self):
        self.camera_manager.setup()
        camera_name= CONF.importOpt(module='garage_eye_manager', name='camera', group='app')
        self.camera = self.camera_manager.get_camera(camera_name[0])


    def run (self):
        if (self.camera is not None):
            try:
                self.camera.capture("snapshot.jpg")
            except CameraException as ex:
                logger.info(ex.reason)
