
import asyncio
from gloop.policies import GloopPolicy

async def main():
    print("hello")
    # import pdb; pdb.set_trace()
    await asyncio.sleep(0.1)
    # import pdb; pdb.set_trace()
    print("world")
    
    # print("world")


asyncio.set_event_loop_policy(GloopPolicy())

asyncio.run(main())


