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
    This file was modified from the openstack implementation of /openstack/common/threadgroup.py.

    Objects: LoopingCallDone, LoopingCallBase, FixedIntervalLoopingCall, DynamicLoopingCall
             Thread, ThreadGroup

    This module contains objects for greenthreads (gts) and also timer threads. Timer threads are just
    gts that periodically run. For example you can have a timer that calls a callback every 30 seconds

    General usage/development:

      To add timer, inherit from LoopingCallBase, override the start(). Use the framework:

        def start (...):
            def _inner():
              while(1)
                callback()
                sleep(x)
            greenthread.spawn_n(_inner)

      Add to ThreadGroup a add_period_timer()-like function. Then add framework like:
            timer = <Init looping call here>
            timer.start(<arguments here>)
            self.timers.append(timer)

    See each object for details on usage.
"""
import sys
import datetime
from eventlet import greenlet
from eventlet import greenpool
from eventlet import greenthread
from eventlet import event
import common.log as logging

logger = logging.getLogger()

class LoopingCallDone(Exception):
    """Exception to break out and stop a LoopingCall.
    The poll-function passed to LoopingCall can raise this exception to
    break out of the loop normally.

    An optional return-value can be included as the argument to the exception;
    this return-value will be returned by LoopingCall.wait()
    """

    def __init__(self, retvalue=True):
        """:param retvalue: Value that LoopingCall.wait() should return."""
        self.retvalue = retvalue


class LoopingCallBase(object):
    """
    LoopingCallBase object. Different kinds of looping (i.e. periodic, timer)
    based calls can use this class as the parent
    """
    def __init__(self, f=None, *args, **kw):
        self.args = args
        self.kw = kw
        self.f = f
        self._running = False
        # note: this done Event is set by the LoopingCall's start()
        self._done_ = None

    def stop(self):
        # stop the timer. Setting _running to false causes the while loop
        # in start() [in children functions] to break
        self._running = False

    def start(self):
        pass

    def wait(self):
        logger.debug("LoopingCallBase: about to wait...")
        # this wait is returned when the LoopingCall timer is done
        # due to exception or code exiting on purpose
        return self._done_.wait()


class FixedIntervalLoopingCall(LoopingCallBase):
    """A fixed interval looping call.
    The callback is called every <interval> seconds"""

    def start(self, interval, initial_delay=None):
        self._running = True
        #this done will be set to LoopingCallBase's done
        done = event.Event()

        def _inner():
            if initial_delay:
                greenthread.sleep(initial_delay)

            try:
                while self._running:
                    start = datetime.datetime.utcnow()
                    self.f(*self.args, **self.kw) # callback
                    end = datetime.datetime.utcnow()
                    if not self._running:
                        break
                    delay = interval - (end-start).total_seconds()
                    logger.debug('delay was %f sec', delay)
                    if delay <= 0:
                        logger.info('task run outlasted interval by %s sec', -delay)
                    greenthread.sleep(delay if delay > 0 else 0)
            except LoopingCallDone as e:
                self.stop()
                done.send(e.retvalue)
            except Exception as e:
                logger.info('exception taken')
                logger.exception(e)
                done.send_exception(*sys.exc_info())
                return
            else:
                done.send(True)

        self._done_ = done

        greenthread.spawn_n(_inner)
        return self._done_


class DynamicLoopingCall(LoopingCallBase):
    """A looping call which sleeps for idle time. If an event occurs, then
    the exeception will catch it.

    The function called should return how long to sleep for before being
    called again. Try to stay within the window for the interval
    """

    def start(self, initial_delay=None, periodic_interval_max=None):
        self._running = True
        done = event.Event()

        def _inner():
            if initial_delay:
                greenthread.sleep(initial_delay)

            try:
                while self._running:
                    idle = self.f(*self.args, **self.kw) # callback

                    if not self._running:
                        break
                    if periodic_interval_max is not None:
                        idle = min(idle, periodic_interval_max)
                    logger.debug("Dynamic looping call sleeping for %d seconds", idle)
                    greenthread.sleep(idle)
            except LoopingCallDone as e:
                logger.info('DynamicLoopingCall _inner: Exception1')
                self.stop()
                done.send(e.retvalue)
            except Exception as ex:
                logger.info('DynamicLoopingCall _inner: Exception2')
                logger.debug(ex)
                done.send_exception(*sys.exc_info())
                return
            else:
                done.send(True)

        self._done_ = done

        greenthread.spawn(_inner)
        logger.debug('DynamicLoopingCall: Exiting...')
        return self._done_

def _thread_done(gt, *args, **kwargs):
    """Callback function to be passed to GreenThread.link() when we spawn()
    Calls the :class:`ThreadGroup` to notify if.
    """
    kwargs['group'].thread_done(kwargs['thread'])


class Thread(object):
    """Wrapper around a greenthread, that holds a reference to the
    :class:`ThreadGroup`. The Thread will notify the :class:`ThreadGroup` when
    it has done so it can be removed from the threads list.
    """
    def __init__(self, thread, group):
        self.thread = thread
        self.thread.link(_thread_done, group=group, thread=self)

    def stop(self):
        logger.debug("Green Thread killed")
        self.thread.kill()

    def wait(self):
        logger.debug("Green Thread wait")
        return self.thread.wait()

class ThreadGroup(object):
    """The point of the ThreadGroup classis to:

    - keep track of timers and greenthreads (making it easier to stop them
      when need be).
    - provide an easy API (add_timer) to add timers.
    """
    def __init__(self, thread_pool_size=10):
        self.pool = greenpool.GreenPool(thread_pool_size)
        self.timers = []
        self.threads = []

    def add_periodic_timer(self, callback, initial_delay=None,
                          periodic_interval_max=None, *args, **kwargs):
        timer = FixedIntervalLoopingCall(callback, *args, **kwargs)
        timer.start(interval=periodic_interval_max,
                    initial_delay=initial_delay)
        self.timers.append(timer)
        logger.debug("FixedIntervalLoopingCall timer started and appended to list")

    """
    add a gt which will run callback.
    """
    def add_thread(self, callback, *args, **kwargs):
        gt = self.pool.spawn(callback, *args, **kwargs)
        th = Thread(gt, self)
        self.threads.append(th)

    """
    When a thread's gt exits, this function is called as a callback
    It'll remove the thread from the list of active threads
    """
    def thread_done(self, thread):
        self.threads.remove(thread)

    """
    stop the threads and the timers.
    """
    def stop(self):
        current = greenthread.getcurrent()
        for x in self.threads:
            if x is current:
                # don't kill the current thread.
                continue
            try:
                logger.debug("thread stop called: Number of threads = %d" % len(self.threads))
                x.stop() # call thread.stop, which basically calls kill
            except Exception as ex:
                logger.info(ex)

        for x in self.timers:
            try:
                logger.debug("thread stop called: Number of timers = %d" % len(self.timers))
                x.stop() # call LoopingCallBase.stop() or related LoopingCall obj
            except Exception as ex:
                logger.info(ex)
        self.timers = []

    """
    This is called by services.wait(). The services.wait() is called by Launcher.wait()
    which is called by the main app loop. It goes through timer (loopcalls) and then the threads (service)
    until all the waits are returned (unblocked). When they are unblocked, it indicates a stop or exception
    is occurring.

    Note that there is a wait function for ThreadGroup.
    When stop is called, the gt kill causes the wait to exit immediately. No exception is raised
    """
    def wait(self):
        logger.debug('Threadgroup wait() started')
        for x in self.timers:
            try:
                logger.debug('timers.waiting...')
                x.wait()
            except greenlet.GreenletExit:
                pass
            except Exception as ex:
                logger.info(ex)

        current = greenthread.getcurrent()
        for x in self.threads:
            if x is current:
                continue
            try:
                logger.debug('threads.waiting...')
                x.wait()
            # note that if tg.stop was called, then the
            # kill will cause a silent exit. GreenletExit will not be caught
            except greenlet.GreenletExit as ex:
                logger.debug(ex)
            except Exception as ex:
                logger.info(ex)


        logger.debug('Threadgroup wait() ended')
