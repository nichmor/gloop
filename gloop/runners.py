import enum

class _State(enum.Enum):
    CREATED = "created"
    INITIALIZED = "initialized"
    CLOSED = "closed"


class Runner:

    def __init__(self, *, loop_factory=None):
        self._state = _State.CREATED
        self._loop_factory = loop_factory
        




def run(main):
    pass