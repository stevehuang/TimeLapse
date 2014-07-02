# Copyright 2010 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# Copyright 2011 Justin Santa Barbara
# Copyright 2014 Steve Huang
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
"""
Author: Steve Huang (huangwSteve@hotmail.com)
Initial Date: July 2014
Module Description:
    This file was modified from the openstack implementation of /openstack/common/service.py.

    Objects: SignalExit, Launcher, Service Launcher, Services, Service

    This module contains objects for launch and managing service. You can thing of a service
    as an independent thread. You have to inherit from the base Service object to implement
    a specific service.

    See each object for details on usage. The general idea is as follows:
      - Launcher manages Services. Mainly a wrapper for Services
      - Services manages list of service. Has it's own thread group (tg).
      - Service manages list of timers, and threads.

    To use this module, write a service that inherits the Service class, override or add methods
    to suit your need.
        - create the service object,
        - create a launcher,
        - run launcher.launch_service(service)
    Try to manage one launcher object in the main code.
"""
import errno
import os
import signal
import sys
from io import UnsupportedOperation
import eventlet
from eventlet import event
import threadgroup
import common.log as logging

logger = logging.getLogger()

def _is_daemon():
    # The process group for a foreground process will match the
    # process group of the controlling terminal. If those values do
    # not match, or ioctl() fails on the stdout file handle, we assume
    # the process is running in the background as a daemon.
    # http://www.gnu.org/software/bash/manual/bashref.html#Job-Control-Basics
    try:
        is_daemon = os.getpgrp() != os.tcgetpgrp(sys.stdout.fileno())
    except OSError as err:
        if err.errno == errno.ENOTTY:
            # Assume we are a daemon because there is no terminal.
            is_daemon = True
        else:
            raise
    except UnsupportedOperation:
        # Could not get the fileno for stdout, so we must be a daemon.
        is_daemon = True
    if is_daemon == True: logger.info("Daemon is set")
    return is_daemon
  
def _sighup_supported():
    return hasattr(signal, 'SIGHUP')

def _is_sighup_and_daemon(signo):
    if not (_sighup_supported() and signo == signal.SIGHUP):
        # Avoid checking if we are a daemon, because the signal isn't
        # SIGHUP.
        return False
    return _is_daemon()
  
def _signo_to_signame(signo):
    signals = {signal.SIGTERM: 'SIGTERM',
               signal.SIGINT: 'SIGINT'}
    if _sighup_supported():
        signals[signal.SIGHUP] = 'SIGHUP'
    return signals[signo]

# SIGTERM - termination signal
# SIGINT  - terminal interupt signal
#  SIGHUP is "hangup"
def _set_signals_handler(handler):
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, handler)
    if hasattr(signal, 'SIGINT'):
        signal.signal(signal.SIGINT, handler)
    # check if the signal object has the attribute SIGHUP
    if _sighup_supported:
        signal.signal(signal.SIGHUP, handler)

class SignalExit(SystemExit):
    """
    Exception object that indicates a termination SIG_* was found
    """
    def __init__(self, signo, exccode=1):
        super(SignalExit, self).__init__(exccode)
        self.signo = signo
                
class Launcher(object):
    """
    Launch one or more services and wait for them to complete.
    Call launcher.wait to wait for the services. Otherwise the code will exit.
    """
    def __init__(self):
        # Initialize the service launcher.
        self.services = Services()  # a list of services for the launcher to manage

    def launch_service(self, service):
        # Load and start the given service
        # param service: The service you would like to start.
        self.services.add(service)

    def stop(self):
        # Stop all services which are currently running.
        self.services.stop()

    def wait(self):
        # Waits until all services have been stopped, and then returns.
        self.services.wait()

    def restart(self):
        # Reload config files and restart service.
        self.services.restart()

class ServiceLauncher(Launcher):
    """
    Launches services and manages multiple services. Inherits from Launcher and
    focus on service management
    """

    def _handle_signal(self, signo, frame):
        # Allow the process to be killed again and die from natural causes
        _set_signals_handler(signal.SIG_DFL) # SIG_DFL is the default process to terminate
        raise SignalExit(signo)

    def handle_signal(self):
        _set_signals_handler(self._handle_signal)

    """
    Main wait handling. If ready_callback is set, then call function. Then call
    Services.wait() via super. If an INT is caught, catch it and process it.
    Finally stop services on Exception
    """
    def _wait_for_exit_or_signal(self, ready_callback=None):
        status = None
        signo = 0

        logger.info("ServiceLauncher: _wait_for_exit_or_signal")
        try:
            if ready_callback:
                ready_callback()
            super(ServiceLauncher, self).wait()
        except SignalExit as exc:
            signame = _signo_to_signame(exc.signo)
            logger.info('Caught %s, exiting', signame)
            status = exc.code
            signo = exc.signo
        except SystemExit as exc:
            status = exc.code
        finally:
            logger.info("ServiceLauncher: calling stop")
            # when exception is caught, finally will execute and attempt
            # to stop the sevices that are running (services.stop)
            self.stop()

        logger.info("ServiceLauncher: Exiting...")
        return status, signo

    """
    Launcher's wait. This is called by main() app function. It
    waits for an INT to occur and if it does, it'll return
    to exit. It'll tell all the services to wait (services.wait)
    and basically set in a blocking state.
    """
    def wait(self, ready_callback=None):
        while True:
            self.handle_signal()
            # _wait_for_exit_or_signal won't return unless there is an
            # exception or all the waits are returned from (unblocked)
            status, signo = self._wait_for_exit_or_signal(ready_callback)
            if not _is_sighup_and_daemon(signo):
                return status
            self.restart()

class Services(object):
    """
    Services object. Manages a list of service and coordinates events and actions.
    """
    def __init__(self):
        self.services = [] # list of the service obj
        self.tg = threadgroup.ThreadGroup() # the thread for the service obj

        # signal for services that it is done. run_service() calls this to block
        # the stop() will call done.send to release
        # Note: service has it's own done (called _done)
        self.done = event.Event()

    """
    add service (that istolaunched) to a list
    add to tg which will spawn the gt and call Services.run_service
    """
    def add(self, service):
        self.services.append(service)
        self.tg.add_thread(self.run_service, service, self.done)

    def stop(self):
        # stop, then wait
        # the wait returns only if stop completed
        # ensures graceful shutdown.
        for service in self.services:
            service.stop()
            service.wait()

        # Each service has performed cleanup, now signal that the Services.run_service
        # wrapper threads can now die:
        # ready() return false means wait has not returned (blocking)
        if not self.done.ready():
            self.done.send()

        # kill the threads that run the service
        # please note that this causes the tg.wait to return
        # siliently. The exception is not thrown. The wait just dies.
        logger.debug("Services is stopping its tg's now")
        self.tg.stop()

    """
    Called by the launcher's wait(). Will put all the
    tg's gt into wait. They are unblocked when tg timer and threads are
    stopped
    """
    def wait(self):
        self.tg.wait()

    def restart(self):
        self.stop()
        self.done = event.Event()
        for restart_service in self.services:
            restart_service.reset()
            self.tg.add_thread(self.run_service, restart_service, self.done)

    """
    Services.run_service is passed as a callback to tg.add_thread (which spawns this)
    This function will run the service's start() function.
    """
    @staticmethod
    def run_service(service, done):
        """Service start wrapper."""
        service.start()
        logger.info("Services: run_service wait")
        # done: event to wait on until a shutdown is triggered
        # this is the services.done event
        # Services.stop will sent event here to continue for shutdown
        done.wait() # *SWH

class Service(object):
    """
    Service object. If you are creating an application service,
    create child service that inherits this class. Then
    override the function start()

    For __init__() you can call this obj's function with super
    For stop() you can call this obj's function with super
    """
    def __init__(self, threads=100):
        # a threadGroup (see eventlets documentation for details)
        self.tg = threadgroup.ThreadGroup(threads)

        # signal that the service is done shutting itself down:
        self._done = event.Event()

    def reset(self):
        # NOTE(Fengqian): docs for Event.reset() recommend against using it
        # Above is openstack note
        self._done = event.Event()

    def start(self):
        pass

    """
    Send the tg kill to the threads/timers. The period loops are killed from the service.
    """
    def stop(self):
        print (self)
        self.tg.stop()
        self.tg.wait()
        """
        Signal that service cleanup is done
        _done.wait will continue and then exit.
        which is in service.wait() -see below
        """
        if not self._done.ready():
            # ready returns true if wait will return immediately
            # so if false, then tell _done.wait to return
            self._done.send()

    """
        This will pause the service and cause the next gt to run.
        It is only called by service.Services.stop()
    """
    def wait(self):
        self._done.wait()

"""
launch a service and return the
ServiceLauncher obj
"""
def launch(service, workers=1):
    if workers is None or workers == 1:
        launcher = ServiceLauncher()
        launcher.launch_service(service)
    return launcher
