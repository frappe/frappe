# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import pickle
import re

import redis
from redis.commands.search import Search

import frappe
from frappe.utils import cstr


class RedisearchWrapper(Search):
    """
    This class extends the Search class and provides methods for interacting with a
    Redisearch index.
    """
    def sugadd(self, key, *suggestions, **kwargs):
        return super().sugadd(self.client.make_key(key), *suggestions, **kwargs)

    def suglen(self, key):
        return super().suglen(self.client.make_key(key))

    def sugdel(self, key, string):
        return super().sugdel(self.client.make_key(key), string)

    def sugget(self, key, *args, **kwargs):
        return super().sugget(self.client.make_key(key), *args, **kwargs)


class RedisWrapper(redis.Redis):
    """Redis client that will automatically prefix conf.db_name"""

    def connected(self):
        try:
            self.ping()
            return True
        except redis.exceptions.ConnectionError:
            return False

    def __call__(self):
        """WARNING: Added for backward compatibility to support frappe.cache().method(...)"""
        return self

    def make_key(self, key, user=None, shared=False):
        if shared:
            return key
        if user:
            if user is True:
                user = frappe.session.user

            key = f"user:{user}:{key}"

        return f"{frappe.conf.db_name}|{key}".encode()

    def set_value(self, key, val, user=None, expires_in_sec=None, shared=False):
        """Sets cache value.

		:param key: Cache key
		:param val: Value to be cached
		:param user: Prepends key with User
		:param expires_in_sec: Expire value of this key in X seconds
		"""
        key = self.make_key(key, user, shared)

        if not expires_in_sec:
            frappe.local.cache[key] = val

        try:
            if expires_in_sec:
                self.setex(name=key, time=expires_in_sec, value=pickle.dumps(val))
            else:
                self.set(key, pickle.dumps(val))

        except redis.exceptions.ConnectionError:
            return None

    def get_value(self, key, generator=None, user=None, expires=False, shared=False):
        """Returns cache value. If not found and generator function is
		        given, it will call the generator.

		:param key: Cache key.
		:param generator: Function to be called to generate a value if `None` is returned.
		:param expires: If the key is supposed to be with an expiry, don't store it in frappe.local
		"""
        original_key = key
        key = self.make_key(key, user, shared)

        if key in frappe.local.cache:
            val = frappe.local.cache[key]

        else:
            val = None
            try:
                val = self.get(key)
            except redis.exceptions.ConnectionError:
                pass

            if val is not None:
                val = pickle.loads(val)

            if not expires:
                if val is None and generator:
                    val = generator()
                    self.set_value(original_key, val, user=user)

                else:
                    frappe.local.cache[key] = val

        return val

    def get_all(self, key):
        ret = {}
        for k in self.get_keys(key):
            ret[key] = self.get_value(k)

        return ret

    def get_keys(self, key):
        """Return keys starting with `key`.

        Args:
            key (str): The prefix of the keys to retrieve.

        Returns:
            list: A list of keys that start with the given prefix.
        """
        try:
            key = self.make_key(key + "*")
            return self.keys(key)

        except redis.exceptions.ConnectionError:
            regex = re.compile(cstr(key).replace("|", r"\|").replace("*", r"[\w]*"))
            return [k for k in list(frappe.local.cache) if regex.match(cstr(k))]

    def delete_keys(self, key):
        """Delete keys with wildcard `*`.

        Args:
            key (str): The key pattern to match for deletion.
        """
        self.delete_value(self.get_keys(key), make_keys=False)

    def delete_key(self, *args, **kwargs):
        """Delete a single key or a list of keys.

        Args:
            *args: The keys to delete.
            **kwargs: Additional arguments.
        """
        self.delete_value(*args, **kwargs)

    def delete_value(self, keys, user=None, make_keys=True, shared=False):
        """Delete a value or a list of values.

        Args:
            keys (list or str): The key(s) to delete.
            user (str, optional): The user associated with the key(s).
            make_keys (bool, optional): Whether to create the keys.
            shared (bool, optional): Whether the key(s) are shared.
        """
        if not keys:
            return

        if not isinstance(keys, (list, tuple)):
            keys = (keys,)

        if make_keys:
            keys = [self.make_key(k, shared=shared, user=user) for k in keys]

        for key in keys:
            frappe.local.cache.pop(key, None)

        try:
            self.delete(*keys)
        except redis.exceptions.ConnectionError:
            pass

    def lpush(self, key, value):
        """Push a value to the left of a Redis list.

        Args:
            key (str): The key of the list.
            value: The value to push.
        """
        super().lpush(self.make_key(key), value)

    def rpush(self, key, value):
        """Push a value to the right of a Redis list.

        Args:
            key (str): The key of the list.
            value: The value to push.
        """
        super().rpush(self.make_key(key), value)

    def lpop(self, key):
        """Pop a value from the left of a Redis list.

        Args:
            key (str): The key of the list.

        Returns:
            Any: The popped value.
        """
        return super().lpop(self.make_key(key))

    def rpop(self, key):
        """Pop a value from the right of a Redis list.

        Args:
            key (str): The key of the list.

        Returns:
            Any: The popped value.
        """
        return super().rpop(self.make_key(key))

    def llen(self, key):
        """Return the length of a list stored in the cache.

        Args:
            key (str): The key identifying the list in the cache.

        Returns:
            int: The length of the list.
        """
        return super().llen(self.make_key(key))

    def lrange(self, key, start, stop):
        """Retrieve a range of elements from a list stored in the cache.

        Args:
            key (str): The key identifying the list in the cache.
            start (int): The starting index of the range.
            stop (int): The ending index of the range.

        Returns:
            list: The elements in the specified range.
        """
        return super().lrange(self.make_key(key), start, stop)

    def ltrim(self, key, start, stop):
        """Trim a list stored in the cache to a specified range.

        Args:
            key (str): The key identifying the list in the cache.
            start (int): The starting index of the range to keep.
            stop (int): The ending index of the range to keep.
        """
        return super().ltrim(self.make_key(key), start, stop)

    def hset(
    	self,
    	name: str,
    	key: str,
    	value,
    	shared: bool = False,
    	*args,
    	**kwargs,
    ):
        """Set a value in a Redis hash stored in the cache.

        Args:
            name (str): The name of the hash.
            key (str): The key within the hash.
            value: The value to set.
            shared (bool, optional): Whether the hash is shared. Defaults to False.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.
        """
        if key is None:
            return

        _name = self.make_key(name, shared=shared)

        # set in local
        frappe.local.cache.setdefault(_name, {})[key] = value

        # set in redis
        try:
            super().hset(_name, key, pickle.dumps(value), *args, **kwargs)
        except redis.exceptions.ConnectionError:
            pass

    def hexists(self, name: str, key: str, shared: bool = False) -> bool:
        """Check if a key exists in a Redis hash stored in the cache.

        Args:
            name (str): The name of the hash.
            key (str): The key within the hash.
            shared (bool, optional): Whether the hash is shared. Defaults to False.

        Returns:
            bool: True if the key exists, False otherwise.
        """
        if key is None:
            return False
        _name = self.make_key(name, shared=shared)
        try:
            return super().hexists(_name, key)
        except redis.exceptions.ConnectionError:
            return False

    def exists(self, *names: str, user=None, shared=None) -> int:
        """Check if one or more keys exist in the cache.

        Args:
            *names (str): The keys to check.
            user: The user associated with the keys.
            shared: Whether the keys are shared.

        Returns:
            int: The number of keys that exist.
        """
        names = [self.make_key(n, user=user, shared=shared) for n in names]

        try:
            return super().exists(*names)
        except redis.exceptions.ConnectionError:
            return False

    def hgetall(self, name):
        """Retrieves all key-value pairs from a Redis hash.

        Args:
            name (str): The name of the Redis hash.

        Returns:
            dict: A dictionary with the keys as strings and the corresponding deserialized values.
        """
        value = super().hgetall(self.make_key(name))
        return {key: pickle.loads(value) for key, value in value.items()}

    def hget(self, name, key, generator=None, shared=False):
        """Retrieves the value associated with a specific key from a Redis hash.

        If the key is present in the local cache, the cached value is returned.
        Otherwise, the value is fetched from Redis and stored in the cache.

        Args:
            name (str): The name of the Redis hash.
            key: The key of the value to retrieve.
            generator (function, optional): A function to generate a value if it
                is not present in Redis.
            shared (bool, optional): Whether the Redis hash is shared between multiple instances.

        Returns:
            The value associated with the specified key.
        """
        _name = self.make_key(name, shared=shared)
        if _name not in frappe.local.cache:
            frappe.local.cache[_name] = {}

        if not key:
            return None

        if key in frappe.local.cache[_name]:
            return frappe.local.cache[_name][key]

        value = None
        try:
            value = super().hget(_name, key)
        except redis.exceptions.ConnectionError:
            pass

        if value is not None:
            value = pickle.loads(value)
            frappe.local.cache[_name][key] = value
        elif generator:
            value = generator()
            self.hset(name, key, value, shared=shared)
        return value

    def hdel(self, name, key, shared=False):
        """Deletes a key-value pair from a Redis hash.

        If the key is present in the local cache, it is removed from the cache.
        Then, the key-value pair is deleted from Redis.

        Args:
            name (str): The name of the Redis hash.
            key: The key of the value to delete.
            shared (bool, optional): Whether the Redis hash is shared between multiple instances.
        """
        _name = self.make_key(name, shared=shared)

        if _name in frappe.local.cache:
            if key in frappe.local.cache[_name]:
                del frappe.local.cache[_name][key]
        try:
            super().hdel(_name, key)
        except redis.exceptions.ConnectionError:
            pass

    def hdel_keys(self, name_starts_with, key):
        """Deletes all key-value pairs with a given key from multiple Redis hashes.

        The function iterates over the matching hashes, removes the key from each hash
        in the local cache, and deletes the key-value pair from Redis.

        Args:
            name_starts_with (str): A pattern to match the Redis hash names.
            key: The key of the value to delete.
        """
        for name in self.get_keys(name_starts_with):
            name = name.split("|", 1)[1]
            self.hdel(name, key)

    def hkeys(self, name):
        """Retrieve all keys in a Redis hash."""
        try:
            return super().hkeys(self.make_key(name))
        except redis.exceptions.ConnectionError:
            return []

    def sadd(self, name, *values):
        """Add a member/members to a given set"""
        super().sadd(self.make_key(name), *values)

    def srem(self, name, *values):
        """Remove a specific member/list of members from the set"""
        super().srem(self.make_key(name), *values)

    def sismember(self, name, value):
        """Returns True or False based on if a given value is present in the set"""
        return super().sismember(self.make_key(name), value)

    def spop(self, name):
        """Removes and returns a random member from the set"""
        return super().spop(self.make_key(name))

    def srandmember(self, name, count=None):
        """Returns a random member from the set"""
        return super().srandmember(self.make_key(name))

    def smembers(self, name):
        """Return all members of the set"""
        return super().smembers(self.make_key(name))

    def ft(self, index_name="idx"):
        """Initialize a RedisearchWrapper object."""
        return RedisearchWrapper(client=self, index_name=self.make_key(index_name))
