import common.log as logging
import common.config as Conf
import camera
from os import listdir
from os.path import isdir, isfile, join
from random import shuffle
from sys import _getframe

Options = [
    Conf.StrOpt(name    = 'use',
                group   = 'camera.fakecam',
                default = 'camera.fakecam:FakeCam.factory',
                help    = 'point to the fake camera python module',
                sub_group = 'fakecam'),
    Conf.DirOpt(name     = 'path',
                 group   = 'camera.fakecam',
                 default = '$HOME/.garageeye/camera',
                 help    = 'full path to webcam files',
                 sub_group = 'fakecam')
]

logger = logging.getLogger()
CONF = Conf.Config
CONF.registerOpt(Options)

class FakeCam (camera.Camera):
    ''' FakeCam -
    '''
    def __init__(self, path):
        super(FakeCam, self).__init__()
        self.filenames=[]
        self.filenum = 0
        # get the list of images from the directory path
        self.path = CONF.importOpt(module='camera', name='path', group='camera.fakecam')
        if (isdir(self.path)):
          self.filenames = [name for name in listdir(self.path) if isfile(join(self.path,name))]
        # randomly sort into a list
        if (len(self.filenames) > 0):
          shuffle(self.filenames)
          #logger.info('filenames' + str(self.filenames))

    def capture(self, filename):
        logger.debug(_getframe().f_code.co_name + ' called')
        if len(self.filenames) > 0:
          rval = join(self.path, self.filenames[self.filenum])
          self.filenum = (self.filenum + 1) % len(self.filenames)
          return rval
        return None
        
    @staticmethod
    def factory (conf_vars):
        return FakeCam(path = '')
