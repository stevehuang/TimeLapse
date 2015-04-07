import common.config as Conf
import common.log as logging

import predict_NN

CONF = Conf.Config
logger = logging.getLogger()


def import_module_object (use_name):
    mod_name, func = use_name.split(':') if ':' in use_name else (use_name, None)
    module = __import__(mod_name)

    for part in mod_name.split('.')[1:] + (func.split('.') if func else []):
        module = getattr(module, part)
    return module

def call_use_function (use_name, conf_vars):
    function_call = import_module_object(use_name)
    return function_call(conf_vars)

class PredictionManager (object):
    def __init__ (self):
        self.predicters = dict()
        self.trainers=dict()

    def setup (self):
        # get list of predicters
        predictor_names= CONF.importOpt(module='time_lapse_manager', name='classifier', group='app')
        for predicter_name in predictor_names:
            groupName = 'classifier.' + predicter_name
            use = CONF.importOpt(module='classifier', name='use', group=groupName)
            name_list = CONF.get_opt_list(groupName)
            conf_vars = dict()
            for name in name_list:
                conf_vars[name]= CONF.importOpt(module='classifier', name=name, group=groupName)
            self.predicters[predicter_name] = call_use_function(use, conf_vars)

        # get list of trainers
        trainer_names= CONF.importOpt(module='time_lapse_manager', name='trainer', group='app')
        for trainer_name in trainer_names:
            groupName = 'trainer.' + trainer_name
            use = CONF.importOpt(module='classifier', name='use', group=groupName)
            name_list = CONF.get_opt_list(groupName)
            conf_vars = dict()
            for name in name_list:
                conf_vars[name]= CONF.importOpt(module='classifier', name=name, group=groupName)
            logger.info("Call trainer and init the class")
            self.trainers[trainer_name] = call_use_function(use, conf_vars)

    def get (self, name):
        if name in self.predicters:
            return self.predicters[name]
        if name in self.trainers:
            return self.trainers[name]

