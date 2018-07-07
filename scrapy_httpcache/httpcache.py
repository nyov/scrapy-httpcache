# Imports for "backwards compatibility" with Scrapy
#
# These allow replacing `scrapy.downloadermiddlewares.httpcache`
# (or `scrapy.contrib.downloadermiddleware.httpcache`) lines
# directly with `scrapy_httpcache.httpcache` for easy sed-migration.
#
# Migrating to the form of `scrapy_httpcache.policy.*` and
# `scrapy_httpcache.storage.*` is preferred however.

from .policy import DummyPolicy
from .policy import RFC2616Policy

from .storage import FilesystemCacheStorage
from .storage import DbmCacheStorage
from .storage import LeveldbCacheStorage
