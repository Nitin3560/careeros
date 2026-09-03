import os

from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
DEFAULT_QUEUE = "careeros"


def get_redis_connection():
    from redis import Redis

    return Redis.from_url(REDIS_URL)


def get_queue(name: str = DEFAULT_QUEUE):
    from rq import Queue

    return Queue(name, connection=get_redis_connection())
