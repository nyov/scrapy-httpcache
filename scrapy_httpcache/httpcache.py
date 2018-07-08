# Imports for "backwards compatibility" with Scrapy
#
# These allow replacing `scrapy.downloadermiddlewares.httpcache`
# (or `scrapy.contrib.downloadermiddleware.httpcache`) lines
# directly with `scrapy_httpcache.httpcache` for easy sed-migration.
#
# Migrating to the form of `scrapy_httpcache.policy.*` and
# `scrapy_httpcache.storage.*` is preferred however.

from .policy.dummy import DummyPolicy
from .policy.rfc2616 import RFC2616Policy

from .storage.filesystem import FilesystemCacheStorage
from .storage.dbm import DbmCacheStorage
from .storage.leveldb import LeveldbCacheStorage
from .storage.mongodb import MongodbCacheStorage
