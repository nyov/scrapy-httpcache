""" MongoDB Cache Storage

A MongoDB Cache Storage backend which stores responses using GridFS.
"""
import logging
from time import time
import warnings

from scrapy.responsetypes import responsetypes
from scrapy.exceptions import NotConfigured
from scrapy.http import Headers

from .base import CacheStorage

try:
    from pymongo import MongoClient, MongoReplicaSetClient
    from pymongo.errors import ConfigurationError
    from pymongo import version_tuple as mongo_version
    from gridfs import GridFS, errors
except ImportError:
    MongoClient = None


logger = logging.getLogger(__name__)


def get_database(settings):
    """ Return Mongo database based on the given settings.

    HOST may be a 'mongodb://' URI string, in which case it will override any
    set PORT and DATABASE parameters.

    If user and password parameters are specified and also passed in a
    mongodb URI, the call to authenticate() later (probably) overrides the URI
    string's earlier login.

    Specifying an auth 'mechanism' or 'source' (Mongo 2.5+) currently only
    works by using a host URI string (we don't pass these to authenticate()),
    any kwargs will be passed on to the MongoClient call (e.g. for ssl setup).
    """

    # Deprecate any non-prefixed options, as they might conflict with
    # settings for a MongoDB ItemPipeline, or other use-case.
    if any(s in settings for s in
            ('MONGO_HOST', 'MONGO_PORT', 'MONGO_DATABASE', 'MONGO_USERNAME', 'MONGO_PASSWORD')
        ):
        warnings.warn('MONGO_* setting variables are deprecated in '
                'MongodbCacheStorage, use HTTPCACHE_MONGO_* instead.',
                DeprecationWarning, stacklevel=2)
    conf = {
        'host': settings['HTTPCACHE_MONGO_HOST'] \
                or settings['MONGO_HOST'] \
                or 'localhost',
        'port': settings.getint('HTTPCACHE_MONGO_PORT') \
                or settings.getint('MONGO_PORT') \
                or 27017,
        'db': settings['HTTPCACHE_MONGO_DATABASE'] \
                or settings['MONGO_DATABASE'] \
                or settings['BOT_NAME'],
        'user': settings['HTTPCACHE_MONGO_USERNAME'] \
                or settings['MONGO_USERNAME'],
        'password': settings['HTTPCACHE_MONGO_PASSWORD'] \
                or settings['MONGO_PASSWORD'],
    }
    # Support passing any other options to MongoClient;
    # options passed as "positional arguments" take precedence
    kwargs = settings.getdict('HTTPCACHE_MONGO_CONFIG', None) \
                or settings.getdict('MONGO_CONFIG')
    conf.update(kwargs)
    return conf


class MongodbCacheStorage(CacheStorage):
    """ Storage backend for Scrapy HTTP cache, which stores responses in
    MongoDB GridFS.

    If HTTPCACHE_SHARDED is True, a different collection will be used for
    each spider, similar to FilesystemCacheStorage using folders per spider.
    """

    def __init__(self, settings, **kw):
        if MongoClient is None:
            raise NotConfigured('%s is missing pymongo or gridfs module.' %
                                self.__class__.__name__)
        if mongo_version < (2, 6, 0):
            version = '.'.join('%s'% v for v in mongo_version)
            raise NotConfigured('%s requires pymongo version >= 2.6 but got %s' %
                    (self.__class__.__name__, version))
        super(MongodbCacheStorage, self).__init__(settings)
        self.sharded = settings.getbool('HTTPCACHE_SHARDED', False)
        kwargs = get_database(settings)
        kwargs.update(kw)
        db = kwargs.pop('db')
        user = kwargs.pop('user', None)
        password = kwargs.pop('password', None)
        if 'replicaSet' in kwargs:
            client = MongoReplicaSetClient(**kwargs)
        else:
            client = MongoClient(**kwargs)

        try:
            # try to use a database passed as a 'mongodb://' URI string
            if hasattr(client, 'get_database'): # pymongo 3.5+ rename
                self.db = client.get_database()
            else:
                self.db = client.get_default_database()
        except ConfigurationError:
            # fall back to passed 'HTTPCACHE_MONGO_*' options
            self.db = client[db]

        if user is not None and password is not None:
            self.db.authenticate(user, password)
        logger.debug("Backend %(storage)s connected to %(host)s:%(port)s, using database '%(db)s'" %
            {'storage': self.__class__.__name__, 'host': client.host, 'port': client.port, 'db': db})
        self.fs = {}

    def open_spider(self, spider):
        _shard = 'httpcache'
        if self.sharded:
            _shard = 'httpcache.%s' % spider.name
        self.fs[spider] = GridFS(self.db, _shard)

    def close_spider(self, spider):
        del self.fs[spider]

    def __del__(self):
        if hasattr(self, 'db'):
            self.db.connection.close()

    def retrieve_response(self, spider, request):
        key = self._request_key(spider, request)
        gf = self._get_file(spider, key)
        if gf is None:
            return # not cached
        url = str(gf.url)
        status = str(gf.status)
        headers = Headers([(x, map(str, y)) for x, y in gf.headers.iteritems()])
        body = gf.read()
        respcls = responsetypes.from_args(headers=headers, url=url)
        response = respcls(url=url, headers=headers, status=status, body=body)
        return response

    def store_response(self, spider, request, response):
        key = self._request_key(spider, request)
        metadata = {
            '_id': key,
            'time': time(),
            'status': response.status,
            'url': response.url,
            'headers': dict(response.headers),
        }
        try:
            self.fs[spider].put(response.body, **metadata)
        except errors.FileExists:
            self.fs[spider].delete(key)
            self.fs[spider].put(response.body, **metadata)

    def _get_file(self, spider, key):
        try:
            gf = self.fs[spider].get(key)
        except errors.NoFile:
            return # not found
        if self._is_expired(gf.time):
            return
        return gf

    def _request_key(self, spider, request):
        rfp = self._request_key(request)
        # We could disable the namespacing in sharded mode (old behaviour),
        # but keeping it allows us to merge collections later without
        # worrying about key conflicts.
        #if self.sharded:
        #    return rfp
        return '%s/%s' % (spider.name, rfp)
