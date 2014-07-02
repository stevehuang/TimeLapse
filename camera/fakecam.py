import common.log as logging
import common.config as Conf
import camera

Options = [
    Conf.StrOpt(name    = 'use',
                group   = 'camera',
                default = 'camera.fakecam:FakeCam.factory',
                help    = 'point to the fake camera python module',
                sub_group = 'fakecam'),
    Conf.DirOpt(name     = 'path',
                 group   = 'camera',
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
        pass

    def capture(self, filename):
        logger.debug('FakeCam capture called')

    @staticmethod
    def factory (conf_vars):
        return FakeCam(path = '')
