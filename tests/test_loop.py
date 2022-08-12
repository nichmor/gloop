from asyncio import Future, Handle, Task, TimerHandle
import asyncio
import math
import time
import pytest
from unittest import mock
from gloop.loop import Gloop, _MIN_CANCELLED_TIMER_HANDLES_FRACTION, _MIN_SCHEDULED_TIMER_HANDLES

def test_close(gloop: Gloop):
    assert not gloop.is_closed()
    gloop.close()
    assert gloop.is_closed()

    gloop.close()
    gloop.close()

    f = gloop.create_future()
    with pytest.raises(RuntimeError):
        gloop.run_forever()
    
    with pytest.raises(RuntimeError):
        gloop.run_until_complete(f)

def test_call_soon_handle_in_ready(gloop: Gloop):
    def cb():
        pass

    handle: Handle = gloop.call_soon(cb)
    assert handle._callback == cb
    assert isinstance(handle, Handle)
    assert handle in gloop._ready

def test_call_later_negative_when(gloop: Gloop):
    def cb():
        pass

    handle = gloop.call_later(10.0, cb)
    assert isinstance(handle, TimerHandle)
    assert handle in gloop._scheduled
    assert handle not in gloop._ready

    with pytest.raises(TypeError):
        gloop.call_later(None, cb)


def test__run_once(gloop: Gloop):
    timer_handle_1 = TimerHandle(time.monotonic() + 5.0, lambda: True, (), gloop)
    timer_handle_2 = TimerHandle(time.monotonic() + 10.0, lambda: True, (), gloop)

    timer_handle_1.cancel()

    gloop._process_events = mock.Mock()
    gloop._scheduled.append(timer_handle_1)
    gloop._scheduled.append(timer_handle_2)
    gloop._run_once()
    t = gloop._selector.select.call_args[0][0]
    print(t)
    assert 9.5 < t < 10.5
    assert [timer_handle_2] == gloop._scheduled
    assert gloop._process_events.called

def test__run_once_schedule_handle(gloop: Gloop):
    handle = None
    processed = False

    def cb(loop):
        nonlocal processed, handle
        processed = True
        handle = loop.call_soon(lambda: True)

    h = TimerHandle(time.monotonic() -1, cb, (gloop,), gloop, None)

    gloop._process_events = mock.Mock()
    gloop._scheduled.append(h)
    gloop._run_once()

    assert processed
    assert [handle] == gloop._ready

def test__run_once_ready_handle(gloop: Gloop):
    processed = False
    
    def cb(loop):
        nonlocal processed
        processed = True
    
    h = Handle(cb, (gloop,), gloop, None)
    gloop._process_events = mock.Mock()
    gloop._ready.append(h)
    gloop._run_once()
    
    assert processed

def test__run_once_skip_handle_if_cancelled(gloop: Gloop):
    processed_1, processed_2 = False, False
    
    def cb_1(loop):
        nonlocal processed_1
        processed_1 = True
    
    def cb_2(loop):
        nonlocal processed_2
        processed_2 = True

    h1 = Handle(cb_1, (gloop,), gloop, None)
    h2 = Handle(cb_2, (gloop,), gloop, None)
    
    gloop._process_events = mock.Mock()
    gloop._ready.extend([h1, h2])
    h1.cancel()
    gloop._run_once()
    
    assert processed_1 is False
    assert processed_2

def test__run_once_cancelled_event_cleanup(gloop: Gloop):
    gloop._process_events = mock.Mock()

    assert 0 < _MIN_CANCELLED_TIMER_HANDLES_FRACTION < 1.0

    def cb():
        pass

    not_cancelled_count = 1
    gloop.call_later(3000, cb)

    cancelled_count = 4

    for x in range(2):
        h = gloop.call_later(3600, cb)
        h.cancel()
    
    for x in range(2):
        h = gloop.call_later(100, cb)
        h.cancel()

    assert cancelled_count + not_cancelled_count <= _MIN_SCHEDULED_TIMER_HANDLES

    assert gloop._timer_cancelled_count == cancelled_count

    gloop._run_once()

    cancelled_count -= 2

    assert gloop._timer_cancelled_count == cancelled_count

    assert len(gloop._scheduled) == cancelled_count + not_cancelled_count

    add_cancel_count = int(math.ceil(_MIN_CANCELLED_TIMER_HANDLES_FRACTION * _MIN_SCHEDULED_TIMER_HANDLES)) + 1

    add_not_cancel_count = max(_MIN_SCHEDULED_TIMER_HANDLES - add_cancel_count, 0)

    not_cancelled_count += add_not_cancel_count

    for x in range(add_not_cancel_count):
        gloop.call_later(3600, cb)
    
    cancelled_count += add_cancel_count
    for x in range(add_cancel_count):
        h = gloop.call_later(3600, cb)
        h.cancel()
    
    assert len(gloop._scheduled) == cancelled_count + not_cancelled_count

    gloop._run_once()

    assert len(gloop._scheduled) == not_cancelled_count

    assert all([not x._cancelled for x in gloop._scheduled])




def test_run_until_complete_type_error(gloop: Gloop):
    with pytest.raises(TypeError):
        gloop.run_until_complete('boom_splash')

#TODO: add test_run_until_complete_loop

def test_run_until_complete_raise_exception(gloop: Gloop):

    async def foo():
        await asyncio.sleep(0)
    
    def _run_once():
        raise ValueError('test')
    
    gloop._process_events = mock.Mock()
    gloop._run_once = _run_once

    with pytest.raises(ValueError):
        gloop.run_until_complete(foo())
    

    
def test_run_until_complete_baseexception(gloop: Gloop):
    async def raise_keyboard_interrupt():
        raise KeyboardInterrupt
    
    gloop._process_events = mock.Mock()

    try:
        gloop.run_until_complete(raise_keyboard_interrupt())
    except KeyboardInterrupt:
        pass

    def func():
        gloop.stop()
        func.called = True
    
    func.called = False

    gloop.call_soon(func)
    gloop.run_forever()
    
    assert func.called

def test_run_until_complete_nesting(gloop: Gloop):
    async def coro1():
        await asyncio.sleep(0)
    
    async def coro2():
        assert gloop.is_running()
        gloop.run_until_complete(coro1())
    
    with pytest.raises(RuntimeError):
        gloop.run_until_complete(coro2())

def test_run_until_complete(gloop: Gloop):
    t0 = gloop.time()
    gloop.run_until_complete(asyncio.sleep(0.1))
    t1 = gloop.time()
    assert 0.08 <= t1-t0 <= 0.8

def test_run_until_complete_stopped(gloop: Gloop):
    async def cb():
        gloop.stop()
        await asyncio.sleep(0.1)
    
    with pytest.raises(RuntimeError):
        gloop.run_until_complete(cb())

def test_run_until_complete_then_task(gloop: Gloop):
    results = []
    async def cb(arg):
        results.append(arg)
    gloop.run_until_complete(gloop.create_task(cb('hello')))

    assert ['hello'] == results



def test_call_later(gloop: Gloop):
    results = []

    def callback(arg):
        results.append(arg)
        gloop.stop()

    gloop.call_later(0.1, callback, 'hello world')
    gloop.run_forever()

    assert ['hello world'] == results
    

def test_call_soon(gloop: Gloop):
    results = []
    
    def callback(arg1, arg2):
        results.append((arg1, arg2))
        gloop.stop()

    gloop.call_soon(callback, 'hello', 'world')
    gloop.run_forever()
    assert [('hello', 'world')] == results

def test_close_running_event_loop(gloop: Gloop):
    async def close_loop(loop):
        loop.close()
    
    with pytest.raises(RuntimeError):
        gloop.run_until_complete(close_loop(gloop))

