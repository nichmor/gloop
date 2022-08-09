from asyncio import events
import pytest
from gloop.loop import Gloop


def set_event_loop(loop):
    if loop is None:
        raise ValueError('loop is None')
    events.set_event_loop(loop)
    #TODO: add cleanup close loop


@pytest.fixture
def gloop():
    loop = Gloop()
    set_event_loop(loop)
    return loop
