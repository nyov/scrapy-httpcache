from __future__ import absolute_import

import os
import gzip
import logging
from six.moves import cPickle as pickle
from importlib import import_module
from time import time
from w3lib.http import headers_raw_to_dict, headers_dict_to_raw
from scrapy.http import Headers
from scrapy.responsetypes import responsetypes
from scrapy.utils.request import request_fingerprint
from scrapy.utils.project import data_path
from scrapy.utils.python import garbage_collect, to_bytes


logger = logging.getLogger(__name__)


class CacheStorage(object):

    def __init__(self, settings):
        self.cachedir = data_path(settings['HTTPCACHE_DIR'], createdir=True)
        self.expiration_secs = settings.getint('HTTPCACHE_EXPIRATION_SECS')

    def open_spider(self, spider):
        logger.debug("Opened %(storage)s on %(cachepath)s" %
            {'storage': self.__class__.__name__, 'cachepath': self.cachedir}, extra={'spider': spider})

    def close_spider(self, spider):
        logger.debug("Closed %(storage)s on %(cachepath)s" %
            {'storage': self.__class__.__name__, 'cachepath': self.cachedir}, extra={'spider': spider})

    def retrieve_response(self, spider, request):
        raise NotImplementedError

    def store_response(self, spider, request, response):
        raise NotImplementedError

    def _request_key(self, request):
        return request_fingerprint(request)


class FilesystemCacheStorage(CacheStorage):

    def __init__(self, settings):
        super(FilesystemCacheStorage, self).__init__(settings)
        self.use_gzip = settings.getbool('HTTPCACHE_GZIP')
        self._open = gzip.open if self.use_gzip else open

    def retrieve_response(self, spider, request):
        """Return response if present in cache, or None otherwise."""
        metadata = self._read_meta(spider, request)
        if metadata is None:
            return  # not cached
        rpath = self._get_request_path(spider, request)
        with self._open(os.path.join(rpath, 'response_body'), 'rb') as f:
            body = f.read()
        with self._open(os.path.join(rpath, 'response_headers'), 'rb') as f:
            rawheaders = f.read()
        url = metadata.get('response_url')
        status = metadata['status']
        headers = Headers(headers_raw_to_dict(rawheaders))
        respcls = responsetypes.from_args(headers=headers, url=url)
        response = respcls(url=url, headers=headers, status=status, body=body)
        return response

    def store_response(self, spider, request, response):
        """Store the given response in the cache."""
        rpath = self._get_request_path(spider, request)
        if not os.path.exists(rpath):
            os.makedirs(rpath)
        metadata = {
            'url': request.url,
            'method': request.method,
            'status': response.status,
            'response_url': response.url,
            'timestamp': time(),
        }
        with self._open(os.path.join(rpath, 'meta'), 'wb') as f:
            f.write(to_bytes(repr(metadata)))
        with self._open(os.path.join(rpath, 'pickled_meta'), 'wb') as f:
            pickle.dump(metadata, f, protocol=2)
        with self._open(os.path.join(rpath, 'response_headers'), 'wb') as f:
            f.write(headers_dict_to_raw(response.headers))
        with self._open(os.path.join(rpath, 'response_body'), 'wb') as f:
            f.write(response.body)
        with self._open(os.path.join(rpath, 'request_headers'), 'wb') as f:
            f.write(headers_dict_to_raw(request.headers))
        with self._open(os.path.join(rpath, 'request_body'), 'wb') as f:
            f.write(request.body)

    def _get_request_path(self, spider, request):
        key = self._request_key(request)
        return os.path.join(self.cachedir, spider.name, key[0:2], key)

    def _read_meta(self, spider, request):
        rpath = self._get_request_path(spider, request)
        metapath = os.path.join(rpath, 'pickled_meta')
        if not os.path.exists(metapath):
            return  # not found
        mtime = os.stat(metapath).st_mtime
        if 0 < self.expiration_secs < time() - mtime:
            return  # expired
        with self._open(metapath, 'rb') as f:
            return pickle.load(f)


class DbmCacheStorage(CacheStorage):

    def __init__(self, settings):
        super(DbmCacheStorage, self).__init__(settings)
        self.dbmodule = import_module(settings['HTTPCACHE_DBM_MODULE'])
        self.db = None

    def open_spider(self, spider):
        super(DbmCacheStorage, self).open_spider(spider)
        dbpath = os.path.join(self.cachedir, '%s.db' % spider.name)
        self.db = self.dbmodule.open(dbpath, 'c')

    def close_spider(self, spider):
        self.db.close()
        super(DbmCacheStorage, self).close_spider(spider)

    def retrieve_response(self, spider, request):
        data = self._read_data(spider, request)
        if data is None:
            return  # not cached
        url = data['url']
        status = data['status']
        headers = Headers(data['headers'])
        body = data['body']
        respcls = responsetypes.from_args(headers=headers, url=url)
        response = respcls(url=url, headers=headers, status=status, body=body)
        return response

    def store_response(self, spider, request, response):
        key = self._request_key(request)
        data = {
            'status': response.status,
            'url': response.url,
            'headers': dict(response.headers),
            'body': response.body,
        }
        self.db['%s_data' % key] = pickle.dumps(data, protocol=2)
        self.db['%s_time' % key] = str(time())

    def _read_data(self, spider, request):
        key = self._request_key(request)
        db = self.db
        tkey = '%s_time' % key
        if tkey not in db:
            return  # not found

        ts = db[tkey]
        if 0 < self.expiration_secs < time() - float(ts):
            return  # expired

        return pickle.loads(db['%s_data' % key])


class LeveldbCacheStorage(CacheStorage):

    def __init__(self, settings):
        import leveldb
        self._leveldb = leveldb
        super(LeveldbCacheStorage, self).__init__(settings)
        self.db = None

    def open_spider(self, spider):
        super(LeveldbCacheStorage, self).open_spider(spider)
        dbpath = os.path.join(self.cachedir, '%s.leveldb' % spider.name)
        self.db = self._leveldb.LevelDB(dbpath)

    def close_spider(self, spider):
        # Do compactation each time to save space and also recreate files to
        # avoid them being removed in storages with timestamp-based autoremoval.
        self.db.CompactRange()
        del self.db
        garbage_collect()
        super(LeveldbCacheStorage, self).close_spider(spider)

    def retrieve_response(self, spider, request):
        data = self._read_data(spider, request)
        if data is None:
            return  # not cached
        url = data['url']
        status = data['status']
        headers = Headers(data['headers'])
        body = data['body']
        respcls = responsetypes.from_args(headers=headers, url=url)
        response = respcls(url=url, headers=headers, status=status, body=body)
        return response

    def store_response(self, spider, request, response):
        key = to_bytes(self._request_key(request))
        data = {
            'status': response.status,
            'url': response.url,
            'headers': dict(response.headers),
            'body': response.body,
        }
        batch = self._leveldb.WriteBatch()
        batch.Put(key + b'_data', pickle.dumps(data, protocol=2))
        batch.Put(key + b'_time', to_bytes(str(time())))
        self.db.Write(batch)

    def _read_data(self, spider, request):
        key = to_bytes(self._request_key(request))
        try:
            ts = self.db.Get(key + b'_time')
        except KeyError:
            return  # not found or invalid entry

        if 0 < self.expiration_secs < time() - float(ts):
            return  # expired

        try:
            data = self.db.Get(key + b'_data')
        except KeyError:
            return  # invalid entry
        else:
            return pickle.loads(data)
