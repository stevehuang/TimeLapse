import common.log as logging
#from camera.camera import WebCam
#from camera.camera import CameraException
import camera.camera_manager as cameraManager
import classifier.prediction_manager as predictionManager
import ConfigParser
import common.config as Conf
import classifier.train_NN as trainNN
import os
import re

Options = [
    Conf.DirOpt(name='working_directory',
                short='w',
                group='app',
                default="$HOME/.garageeye/",
                help = 'folder for application data'),
    Conf.FileOpt(name='photo_file',
                short   = 'p',
                group   = 'app',
                default = "$HOME/.garageeye/snapshot.jpg",
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
                 help    = 'log file to output data to'),
    Conf.ListOpt(name    = 'classifier',
                 group   = 'app',
                 default = ['Predict_NN'],
                 help    = 'name of the predicter to use'),
    Conf.ListOpt(name    = 'trainer',
                 group   = 'app',
                 default = ['Train_NN'],
                 help    = 'name of the training obj to use'),
]

logger = logging.getLogger()
CONF = Conf.Config
CONF.registerOpt(Options)

class GarageEyeManager (object):

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
        self.prediction_manager = predictionManager.PredictionManager()
        self.photo_file = CONF.importOpt(module='garage_eye_manager', name='photo_file', group='app')

    def pre_hook (self):
        self.camera_manager.setup()
        camera_name= CONF.importOpt(module='garage_eye_manager', name='camera', group='app')
        self.camera = self.camera_manager.get_camera(camera_name[0])

        self.prediction_manager.setup()
        predictor_name= CONF.importOpt(module='garage_eye_manager', name='classifier', group='app')
        self.predicter = self.prediction_manager.get(predictor_name[0])


        self.prediction_manager.setup()
        trainer_name = CONF.importOpt(module='garage_eye_manager', name='trainer', group='app')
        self.trainer = self.prediction_manager.get(trainer_name[0])

    # look at trainer.Train_NN.path + TrainingSet/day/openned directory and closed directory
    # construct a training set from these files
    def train_set (self):
        img_path = CONF.importOpt(module='classifier.train_NN', name='path', group='trainer.Train_NN')
        opened_path = os.path.join(img_path, "TrainingSet/day/opened")
        closed_path = os.path.join(img_path, "TrainingSet/day/closed")

        files_list = list()
        results_list = list()
        # get each file in path. Add jpg to the list
        for file in os.listdir(closed_path) :
            if re.search(r"(.+)\.jpg", file) is not None:
                files_list.append(os.path.join(closed_path,file))
                results_list.append(1)
        for file in os.listdir(opened_path) :
            if re.search(r"(.+)\.jpg", file) is not None:
                files_list.append(os.path.join(opened_path,file))
                results_list.append(0)
        self.trainer.train(files_list, results_list)

# main run loop for the garage eye application
#
# - take a snap shot
# - check if the garage is opened / closed
# - if opened more then timeout_level1, send notification
# - if opened more then timeout_level2 and timeout_level1 occurred, send notification
# - post picture to cloud if enabled
    def run (self):
        if (self.camera is not None):
            try:
                filename = self.camera.capture(self.photo_file)
                if filename is not None:
                    self.predicter.predict(filename)
            except CameraException as ex:
                logger.info(ex.reason)
