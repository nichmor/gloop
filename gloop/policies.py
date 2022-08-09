from asyncio.events import BaseDefaultEventLoopPolicy

from gloop.loop import Gloop


def new_event_loop() -> Gloop:
    return Gloop()

class GloopPolicy(BaseDefaultEventLoopPolicy):

    def _loop_factory(self) -> Gloop:
        return new_event_loop()
