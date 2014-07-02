import common.config as Conf
import webcam
import fakecam
CONF = Conf.Config


def import_module_object (use_name):
    mod_name, func = use_name.split(':') if ':' in use_name else (use_name, None)
    module = __import__(mod_name)

    for part in mod_name.split('.')[1:] + (func.split('.') if func else []):
        module = getattr(module, part)
    return module

def call_use_function (use_name, conf_vars):
    function_call = import_module_object(use_name)
    return function_call(conf_vars)

class CameraManager (object):
    def __init__ (self):
        self.cameras = dict()

    def setup (self):
        # get list of camera names
        camera_names= CONF.importOpt(module='garage_eye_manager', name='camera', group='app')
        # list of camera:names
        for cam_name in camera_names:
            groupName = 'camera.' + cam_name
            use = CONF.importOpt(module='camera', name='use', group=groupName)
            name_list = CONF.get_opt_list(groupName)
            conf_vars = dict()
            for name in name_list:
                conf_vars[name]= CONF.importOpt(module='camera', name=name, group=groupName)
            self.cameras[cam_name] = call_use_function(use, conf_vars)
        print self.cameras


    def get_camera (self, name):
        if name in self.cameras:
            return self.cameras[name]
