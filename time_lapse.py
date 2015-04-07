"""
Author: Steve Huang (huangwSteve@hotmail.com)
Initial Date: July 2014
Module Description:

Main module to initiate the application.
  Some key points:
- uses a service to launch a green thread process that runs the main code loop
- you can "daemonize" the process will will unhook the process from the user
- the app uses a .conf file to fill in various parameters. It will not work if the conf file is missing
- GT means green thread
"""
import sys
import garage_eye_service
from service.process import ProcessLauncher
#import classifier.prediction_manager as predictionManager
from classifier.train_NN import Train_NN
import common.log as logging
import common.config as Conf
import os, sys, signal, errno

CONF = Conf.Config
Options = [ Conf.StrOpt(name='group',
                        short='g',
                        default='app',
                        help='the group name'),
            Conf.FileOpt(name='config_file',
                         short='f',
                         default='./garageCam.conf',
                         help='configuration file used by GarageEye program')
          ]
CONF.registerOpt(Options)
CONF.importOpt(module='garage_eye_manager', name='log_level')
CONF.importOpt(module='garage_eye_manager', name='log_file')
logger = logging.getLogger()

"""
Fork a child process, then exit the parent process.
If the fork fails, raise a ``DaemonProcessDetachError``
with ``error_message``.
"""
def fork_then_exit_parent(error_message):
    try:
        pid = os.fork()
        if pid > 0:
            os._exit(0)
    except OSError, exc:
        exc_errno = exc.errno
        exc_strerror = exc.strerror
        error = OSError("%(error_message)s: [%(exc_errno)d] %(exc_strerror)s" % vars())
        raise error
          
#@staticmethod
def daemonize(chdir='/'):
    os.umask(0) # set permissions to be wrx for all
    if chdir:
        os.chdir(chdir)
    else:
        os.chdir('/')
    os.setgid(os.getgid())  # relinquish elevations
    os.setuid(os.getuid())  # relinquish elevations
    
    # Double fork to daemonize
    fork_then_exit_parent("Failed first fork")
    os.setsid()                    # Obtain new process group
    fork_then_exit_parent("Failed second fork")  # child exits, grandchild runs

    # Signal handling
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    # Redirect I/O to /dev/null
    os.dup2(os.open(os.devnull, os.O_RDWR), sys.stdin.fileno())
    os.dup2(os.open(os.devnull, os.O_RDWR), sys.stdout.fileno())
    os.dup2(os.open(os.devnull, os.O_RDWR), sys.stderr.fileno())

'''
Entry point for GarageEye python application
  - parse the arguments (usually it's a pointer to conf file)
  - setup the logging information based on the parsed arguments
  - create a service and launch it.
      - launch a service will create first GT
      - which in turn will launch the periodic calls (second GT)
      - in theory you can launch even more GTs from this
  - wait for exit signal, like SIG_INT
'''
def main():
    CONF.parseArgs(sys.argv[1:])
    logging.setup(name="garage_eye", level=CONF.log_level, conf_file=CONF.log_file)
    launcher = ProcessLauncher()
    # create a service class
    main_service = garage_eye_service.Service.create(True, float(10.0))
    # launch a service (first GT) which in turn will launch the periodic calls
    #garage_eye_service.launch_service(main_service)
    predictor_service = Train_NN.create(True, float(5.0))

    launcher.launch_service(main_service)
    launcher.launch_service(predictor_service)

    #trainer_name = CONF.importOpt(module='garage_eye_manager', name='trainer', group='app')
    #self.trainer = self.prediction_manager.get(trainer_name[0])
    # a green thread wait, which calls ServiceLauncher.wait and waits for exit signal
    #garage_eye_service.wait()
    launcher.wait()


if __name__ == "__main__":
#    daemonize('/home/huanghst/workspace/GarageEye')
    main()

