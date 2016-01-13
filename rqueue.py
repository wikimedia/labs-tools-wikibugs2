#!/usr/bin/env python

import json
import redis
import time


class RedisQueue(object):
    def __init__(self, name, host='localhost'):
        self.redis = redis.StrictRedis(host=host, port=6379, db=0)
        self.key = name
        self.last_pushed = 0

    def put(self, item):
        """Put item into the queue."""
        delaytime = 2
        diff = time.time() - self.last_pushed
        if diff < delaytime:
            time.sleep(delaytime - diff)
        self.redis.rpush(self.key, json.dumps(item))
        self.last_pushed = time.time()

    def get(self):
        """Remove and return an item from the queue.

        Will block until an item is available"""
        item = self.redis.blpop(self.key)
        if item:
            return json.loads(item[1].decode())
        return item
