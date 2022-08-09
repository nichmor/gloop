from asyncio import AbstractEventLoop, tasks
from asyncio import events
from asyncio import futures
import threading
from typing import Callable
from asyncio.futures import isfuture

class Gloop(AbstractEventLoop):

    def __init__(self):
        self._thread_id = None
        self._closed = False
        self._ready = []
        self._scheduled = []
        self._debug = False

    def create_future(self):
        return futures.Future(loop=self)
        

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
        return self._thread_id is not None
    
    def get_debug(self):
        return self._debug 
    