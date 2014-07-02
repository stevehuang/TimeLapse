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

  TBD
"""
import errno
import os
import signal
import sys
from io import UnsupportedOperation
import eventlet
from eventlet import event
import threadgroup
from service import Launcher
from time import sleep
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
# SIGINT  - terminal interrupt signal
#  SIGHUP is "hangup"
def _set_signals_handler(handler):
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, handler)
    if hasattr(signal, 'SIGINT'):
        signal.signal(signal.SIGINT, handler)
    # check if the signal object has the attribute SIGHUP
    if _sighup_supported:
        signal.signal(signal.SIGHUP, handler)

class ServiceInfo:
    def __init__(self, service, workers):
        self.service = service
        self.workers = workers
        self.children = set() # list of worker pids that belong to the service
        
""" 
Exception object that indicates a termination SIG_* was found
"""
class SignalExit(SystemExit):
    def __init__(self, signo, exccode=1):
        super(SignalExit, self).__init__(exccode)
        self.signo = signo
          
class ProcessLauncher(object):
    def __init__(self):
      self.running = True
      self.sigcaught = None
      self.children = {}  # contain the list of ServiceInfo for each pid
      self.workers = 1
      rfd, self.writepipe = os.pipe()
      self.readpipe = eventlet.greenio.GreenPipe(rfd, 'r')
      self.handle_signal()

    def handle_signal(self):
        _set_signals_handler(self._handle_signal)

    def _handle_signal(self, signo, frame):
        self.sigcaught = signo
        self.running = False # turn off ProcessLauncher, which in turn shuts down processes
         
    # SIGTERM - termination signal
    # SIGINT  - terminal interrupt signal
    # SIGHUP is "hangup"
    def _child_process_handle_signal(self):
        # Setup child signal handlers differently
        def _sigterm(*args):
            signal.signal(signal.SIGTERM, signal.SIG_DFL)
            raise SignalExit(signal.SIGTERM)

        def _sighup(*args):
            signal.signal(signal.SIGHUP, signal.SIG_DFL)
            raise SignalExit(signal.SIGHUP)

        signal.signal(signal.SIGTERM, _sigterm)
        if _sighup_supported():
            signal.signal(signal.SIGHUP, _sighup)
        # Block SIGINT and let the parent send us a SIGTERM
        signal.signal(signal.SIGINT, signal.SIG_IGN)

    def _pipe_watcher(self):
        # This will block until the write end is closed when the parent
        # dies unexpectedly
        self.readpipe.read()
        logger.info('ProcessLauncher: Parent process has died unexpectedly, exiting')
        sys.exit(1)
        
    # spawn a process
    def _child_process(self, serviceInfo):
        self._child_process_handle_signal()

        # Reopen the eventlet hub to make sure we don't share an epoll
        # fd with parent and/or siblings, which would be bad
        eventlet.hubs.use_hub()

        # Close write to ensure only parent has it open
        os.close(self.writepipe)
        # Create greenthread to watch for parent to close pipe
        eventlet.spawn_n(self._pipe_watcher)

        launcher = Launcher()
        launcher.launch_service(serviceInfo.service)
        return launcher
      
    # throw a fork out which spawns a service running off of child process   
    def _start_child(self, serviceInfo):
        pid = os.fork()   # fork the process which will just wait for a kill signal
        if pid == 0:
            launcher = self._child_process(serviceInfo)
            while True:
                self._child_process_handle_signal()
                status, signo = self._child_wait_for_exit_or_signal(launcher)
                if not _is_sighup_and_daemon(signo):
                    break
                launcher.restart()

            os._exit(status)
          # end forked process

        logger.info('ProcessLauncher: Started child %d',pid)
        self.children[pid] = serviceInfo
        serviceInfo.children.add(pid)
        return pid
      
    def _child_wait_for_exit_or_signal(self, launcher):
        status = 0
        signo = 0

        # NOTE(johannes): All exceptions are caught to ensure this
        # doesn't fallback into the loop spawning children. It would
        # be bad for a child to spawn more children.
        try:
            launcher.wait()
        except SignalExit as exc:
            signame = _signo_to_signame(exc.signo)
            logger.info('ProcessLauncher: Caught %s, exiting', signame)
            status = exc.code
            signo = exc.signo
        except SystemExit as exc:
            status = exc.code
        except BaseException:
            logger.info('ProcessLauncher: Unhandled exception')
            status = 2
        finally:
            launcher.stop()

        return status, signo
            
    def launch_service(self, service, workers=1):
        logger.info('ProcessLauncher: launch_service() starting %d workers', workers)
        serviceInfo = ServiceInfo(service, workers)
        while self.running and len(serviceInfo.children) < workers:
            self._start_child(serviceInfo)
            sleep(1) # take a sec between launches.
            
    def _wait_child(self):
        try:
            # Don't block if no child processes have exited
            pid, status = os.waitpid(0, os.WNOHANG)
            if not pid:
                return None
        except OSError as exc:
            if exc.errno not in (errno.EINTR, errno.ECHILD):
                raise
            return None

        if os.WIFSIGNALED(status):
            sig = os.WTERMSIG(status)
            logger.info('ProcessLauncher: Child %(pid)d killed by signal %(sig)d' , dict(pid=pid, sig=sig))
        else:
            code = os.WEXITSTATUS(status)
            logger.info('ProcessLauncher: Child %(pid)s exited with status %(code)d' , dict(pid=pid, code=code))

        if pid not in self.children:
            logger.info('ProcessLauncher: pid %d not in child list', pid)
            return None

        serviceInfo = self.children.pop(pid)
        serviceInfo.children.remove(pid)
        return serviceInfo

    def _respawn_children(self):
        while self.running:
            serviceInfo = self._wait_child()
            if not serviceInfo:
                # Yield to other threads if no children have exited
                # Sleep for a short time to avoid excessive CPU usage
                eventlet.greenthread.sleep(0.01)
                continue
            while self.running and len(serviceInfo.children) < serviceInfo.workers:
                self._start_child(serviceInfo)
                sleep(1)
            
    def wait(self):
        """Loop waiting on children to die and respawning as necessary."""
        try:
            while True:
                self.handle_signal()
                self._respawn_children()
                if self.sigcaught:
                    signame = _signo_to_signame(self.sigcaught)
                    logger.info('ProcessLauncher: Caught %s, stopping children', signame)
                if not _is_sighup_and_daemon(self.sigcaught):
                    break

                for pid in self.children:
                    os.kill(pid, signal.SIGHUP)
                self.running = True
                self.sigcaught = None
        except eventlet.greenlet.GreenletExit:
            logger.info("ProcessLauncher: Wait called after thread killed.  Cleaning up.")

        for pid in self.children:
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError as exc:
                if exc.errno != errno.ESRCH:
                    raise

        # Wait for children to die
        if self.children:
            logger.info('Waiting on %d children to exit', len(self.children))
            while self.children:
                self._wait_child()
