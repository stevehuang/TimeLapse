"""
Author: Steve Huang (huangwSteve@hotmail.com)
Initial Date: July 2014
Module Description:
    Service module that inherits from service.Service object.
    You can launch a service by calling launch_service() from this module.
"""
from service import service
import common.log as logging
import garage_eye_manager
import ConfigParser

logger = logging.getLogger()

class Service(service.Service):
    """
    Service object tailored for GarageEye application. It parent is in service.Service.
    The service launcher will use this obj as the main service.

    Some notes:
      - the Services obj has it's own tg which is managed by Launcher
      - each service has it's own tg
    """

    def __init__(self, periodic_enable=None, periodic_interval_max=None, *args, **kwargs):
        super(Service, self).__init__()
        self.periodic_enable = periodic_enable
        self.periodic_interval_max = periodic_interval_max
        # use the garageEyeManager obj
        self.manager = garage_eye_manager.GarageEyeManager()

    def start(self):
        """
        service.Services.run_service will call this to start the service.
        This function will add a periodic_timer call to tg (thread groups).
        add_periodic_timer spawns a new gt which will be run at a certain
        time interval
        """
        logger.info("started")

        self.manager.pre_hook()

        if self.periodic_enable:
            self.tg.add_periodic_timer(self.periodic_tasks,
                                     initial_delay=1.0,
                                     periodic_interval_max=self.periodic_interval_max)

    @classmethod
    def create(cls, periodic_enable=None, periodic_interval_max=None):
        """Instantiates class and passes back application object.

        :param periodic_enable: defaults to CONF.periodic_enable
        :param periodic_interval_max: if set, the max time to wait between runs

        """
        service_obj = cls(periodic_enable=periodic_enable,
                          periodic_interval_max=periodic_interval_max
                          )

        return service_obj

    def kill(self):
        # Destroy the service object
        self.stop()

    def stop(self):
        # stop the service object
        logger.info('garage_eye_service: stop()')
        super(Service, self).stop()

    def periodic_tasks(self, raise_on_error=False):
        """
        Tasks to be run at a periodic interval.
        This calls the GarageEye manager obj
        """
        logger.info("periodic_tasks running")
        self.manager.run()

        # return time to sleep for
        return (20.0);

    def basic_config_check(self):
        """Perform basic config checks before starting processing."""
        # Make sure the tempdir exists and is writable
        pass

#global
_launcher = None

"""
  Launch a service (service_tobelaunched). Only one launcher can be defined.
  So this function can be used once. If another service is needed, use the _launcher
  variable (or return val).
  you can do launcher.launch_service(service)
"""
def launch_service(service_tobelaunched, workers=None):
    global _launcher
    if _launcher:
        raise RuntimeError('launch_service() can only be called once')

    _launcher = service.launch(service_tobelaunched, workers=workers)
    return _launcher

def wait():
    # see services.wait () for details
    _launcher.wait()
