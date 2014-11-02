#!/usr/bin/env python

import json
import redis


class RedisQueue(object):
    def __init__(self, name, host='localhost'):
        self.redis = redis.StrictRedis(host=host, port=6379, db=0)
        self.key = name

    def put(self, item):
        """Put item into the queue."""
        self.redis.rpush(self.key, json.dumps(item))

    def get(self, block=True, timeout=None):
        """Remove and return an item from the queue.

        If optional args block is true and timeout is None (the default), block
        if necessary until an item is available."""
        if block:
            item = self.redis.blpop(self.key, timeout=timeout)
        else:
            item = self.redis.lpop(self.key)
        print item
        if item:
            item = json.loads(item[1])
        return item
