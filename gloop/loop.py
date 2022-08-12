from asyncio import AbstractEventLoop, Future, Handle, TimerHandle, tasks
from asyncio import events
from asyncio import futures
from lib2to3.pytree import Base
from re import S
import selectors
import threading
import time
import traceback
from typing import Callable, final

MAXIMUM_SELECT_TIMEOUT = 24 * 3600
_MIN_SCHEDULED_TIMER_HANDLES = 100
_MIN_CANCELLED_TIMER_HANDLES_FRACTION = 0.5



def _run_until_complete_cb(fut: Future): #pragma: no cover
    if not fut.cancelled():
        exc = fut.exception()
        if isinstance(exc, (SystemExit, KeyboardInterrupt)):
            return

    futures._get_loop(fut).stop()

class Gloop(AbstractEventLoop):

    def __init__(self):
        self._thread_id = None
        self._closed = False
        self._ready: list[Handle] = []
        self._scheduled: list[TimerHandle] = []
        self._debug = False
        self._timer_cancelled_count = 0
        self._stopping = False
        self._selector = selectors.SelectSelector()
        self._clock_resolution = time.get_clock_info('monotonic').resolution
        self._exception_handler = None
        self._current_handle = None

    def create_future(self):
        return futures.Future(loop=self)
    
    def create_task(self, coro, *, name=None, context=None):
        self._check_closed()
        task = tasks.Task(coro, loop=self)

        return task
    
    def call_soon(self, callback, *args, context=None):
        self._check_closed()

        handle = self._call_soon(callback, args, context)
        return handle

    def _call_soon(self, callback, args, context):
        handle = Handle(callback, args, self, context)
        self._ready.append(handle)
        return handle
    
    def call_later(self, delay: float, callback, *args, context=None):

        timer = self.call_at(self.time() + delay, callback, *args, context=context)
        return timer

    def call_at(self, when, callback, *args, context=None):
        self._check_closed()
        timer = TimerHandle(when, callback, args, self, context)
        timer._scheduled = True
        self._scheduled.append(timer)
        self._scheduled.sort(key= lambda handler: handler.when()) # TODO: special bottleneck
        
        return timer

    def close(self):
        if self.is_running():
            raise RuntimeError('Cannot close a running event loop')
        if self._closed:
            return
        self._closed = True
        self._ready.clear()
        self._scheduled.clear()

    def is_closed(self):
        return self._closed

    def is_running(self):
        return (self._thread_id is not None)
    
    def get_debug(self):
        return self._debug 
    
    def _check_closed(self):
        if self._closed:
            raise RuntimeError('Event loop is closed')
    
    def _check_running(self):
        if self.is_running():
            raise RuntimeError('This event loop is already running')
        if events._get_running_loop() is not None: #pragma: no cover
            raise RuntimeError('Cannot run the event loop with another event loop')
    
    def time(self):
        return time.monotonic()
    
    def _timer_handle_cancelled(self, handle: TimerHandle):
        if handle._scheduled:
            self._timer_cancelled_count += 1

    def _run_once(self):
        sched_count = len(self._scheduled)
        if (sched_count > _MIN_SCHEDULED_TIMER_HANDLES and 
            self._timer_cancelled_count / sched_count > 
                _MIN_CANCELLED_TIMER_HANDLES_FRACTION):

            new_scheduled = []
            for handle in self._scheduled:
                if handle._cancelled:
                    handle._scheduled = False
                else:
                    new_scheduled.append(handle)
        
            self._scheduled = new_scheduled
            self._timer_cancelled_count = 0
        
        else:
            while self._scheduled and self._scheduled[0]._cancelled:
                self._timer_cancelled_count -= 1
                handle = self._scheduled.pop(0)
                handle._scheduled = False


        timeout = None
        if self._ready or self._stopping:
            timeout = 0
        elif self._scheduled: #pragma: no cover
            when = self._scheduled[0]._when
            timeout = min(max(0, when-self.time()), MAXIMUM_SELECT_TIMEOUT)
        
        event_list = self._selector.select(timeout)
        self._process_events(event_list)

        end_time = self.time() + self._clock_resolution
        while self._scheduled:
            handle = self._scheduled[0]
            if handle._when >= end_time:
                break
            handle = self._scheduled.pop(0)
            handle._scheduled = False
            self._ready.append(handle)

        ntodo = len(self._ready)
        for i in range(ntodo):
            handle = self._ready.pop(0)
            if handle._cancelled:
                continue
            handle._run()
        
        handle = None

    def _process_events(self, event_list):
        pass

    def run_until_complete(self, future):
        self._check_closed()
        self._check_running()

        new_task = not futures.isfuture(future)
        future: Future = tasks.ensure_future(future, loop=self)
        if new_task:
            future._log_destroy_pending = False

        future.add_done_callback(_run_until_complete_cb)
        try:
            self.run_forever()
        except Exception as e:
            if new_task and future.done() and not future.cancelled():
                future.exception() #pragma: nocover
            raise
        finally:
            future.remove_done_callback(_run_until_complete_cb)
        if not future.done():
            raise RuntimeError('Event loop stopped before Future completed.')
        
        return future.result()
    
    def run_forever(self) -> None:
        self._check_closed()
        self._check_running()
        self._thread_id = threading.get_ident()

        try:
            events._set_running_loop(self)
            while True:
                self._run_once()
                if self._stopping:
                    break
        finally:
            self._stopping = False
            self._thread_id = None
            events._set_running_loop(None)
            #TODO: add asyncgen hooks
    
    def call_exception_handler(self, context): # pragma: no cover
        """Call the current event loop's exception handler.

        The context argument is a dict containing the following keys:

        - 'message': Error message;
        - 'exception' (optional): Exception object;
        - 'future' (optional): Future instance;
        - 'task' (optional): Task instance;
        - 'handle' (optional): Handle instance;
        - 'protocol' (optional): Protocol instance;
        - 'transport' (optional): Transport instance;
        - 'socket' (optional): Socket instance;
        - 'asyncgen' (optional): Asynchronous generator that caused
                                 the exception.

        New keys maybe introduced in the future.

        Note: do not overload this method in an event loop subclass.
        For custom exception handling, use the
        `set_exception_handler()` method.
        """
        if self._exception_handler is None:
            try:
                self.default_exception_handler(context)
            except (SystemExit, KeyboardInterrupt):
                raise
            except BaseException as e:
                # Second protection layer for unexpected errors
                # in the default implementation, as well as for subclassed
                # event loops with overloaded "default_exception_handler".
                print('Exception in default exception handler')
                print(e)
        else:
            try:
                self._exception_handler(self, context)
            except (SystemExit, KeyboardInterrupt):
                raise
            except BaseException as exc:
                # Exception in the user set custom exception handler.
                try:
                    # Let's try default handler.
                    self.default_exception_handler({
                        'message': 'Unhandled error in exception handler',
                        'exception': exc,
                        'context': context,
                    })
                except (SystemExit, KeyboardInterrupt):
                    raise
                except BaseException:
                    # Guard 'default_exception_handler' in case it is
                    # overloaded.
                    print('Exception in default exception handler '
                                 'while handling an unexpected error '
                                 'in custom exception handler')

    def default_exception_handler(self, context): # pragma: no cover
        """Default exception handler.

        This is called when an exception occurs and no exception
        handler is set, and can be called by a custom exception
        handler that wants to defer to the default behavior.

        This default handler logs the error message and other
        context-dependent information.  In debug mode, a truncated
        stack trace is also appended showing where the given object
        (e.g. a handle or future or task) was created, if any.

        The context parameter has the same meaning as in
        `call_exception_handler()`.
        """
        message = context.get('message')
        if not message:
            message = 'Unhandled exception in event loop'

        exception = context.get('exception')
        if exception is not None:
            exc_info = (type(exception), exception, exception.__traceback__)
        else:
            exc_info = False

        if ('source_traceback' not in context and
                self._current_handle is not None and
                self._current_handle._source_traceback):
            context['handle_traceback'] = \
                self._current_handle._source_traceback

        log_lines = [message]
        for key in sorted(context):
            if key in {'message', 'exception'}:
                continue
            value = context[key]
            if key == 'source_traceback':
                tb = ''.join(traceback.format_list(value))
                value = 'Object created at (most recent call last):\n'
                value += tb.rstrip()
            elif key == 'handle_traceback':
                tb = ''.join(traceback.format_list(value))
                value = 'Handle created at (most recent call last):\n'
                value += tb.rstrip()
            else:
                value = repr(value)
            log_lines.append(f'{key}: {value}')

        print('\n'.join(log_lines))
        print(exc_info)
    
    def stop(self):
        self._stopping = True