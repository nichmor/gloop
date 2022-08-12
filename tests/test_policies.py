

from gloop.loop import Gloop
from gloop.policies import GloopPolicy


def test_policies_return_loop():
    policy = GloopPolicy()
    loop = policy._loop_factory()
    assert isinstance(loop, Gloop)