from asyncio import events
import pytest
from gloop.loop import Gloop

from unittest import mock

def set_event_loop(loop):
    if loop is None:
        raise ValueError('loop is None')
    events.set_event_loop(loop)
    #TODO: add cleanup close loop


@pytest.fixture
def gloop():
    loop = Gloop()
    loop._selector = mock.Mock()
    loop._selector.select.return_value = ()
    set_event_loop(loop)
    return loop
