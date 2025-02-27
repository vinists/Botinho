import time
import functools
import asyncio
import random
import string


def get_epoch_filename(ext):
    return f"temp/{str(time.time()).split('.')[0]}.{ext}"


async def run_async(blocking_func, *args, **kwargs):
    loop = asyncio.get_event_loop()
    pfunc = functools.partial(blocking_func, *args, **kwargs)
    return await loop.run_in_executor(None, pfunc)


def generate_token(length=4):
    chars = string.ascii_letters
    return (''.join(random.choice(chars) for _ in range(length))).upper()
