from __future__ import absolute_import

import os
from six.moves import cPickle as pickle
from importlib import import_module
from time import time
from scrapy.http import Headers
from scrapy.responsetypes import responsetypes
from scrapy.utils.python import garbage_collect, to_bytes
from scrapy.exceptions import NotConfigured

from .base import CacheStorage


class LeveldbCacheStorage(CacheStorage):

    def __init__(self, settings):
        super(LeveldbCacheStorage, self).__init__(settings)
        self.dbdriver = settings.get('HTTPCACHE_DB_MODULE', None)
        if not self.dbdriver:
            try:
                self.dbmodule = import_module('plyvel')
            except ImportError:
                self.dbmodule = import_module('leveldb')
        else:
            self.dbmodule = import_module(settings['HTTPCACHE_DB_MODULE'])
        self.dbdriver = self.dbmodule.__name__
        self.db = None

    def open_spider(self, spider):
        super(LeveldbCacheStorage, self).open_spider(spider)
        dbpath = os.path.join(self.cachedir, '%s.leveldb' % spider.name)
        if self.dbdriver == 'plyvel':
            self.db = self.dbmodule.DB(dbpath, create_if_missing=True)
        elif self.dbdriver == 'leveldb':
            self.db = self.dbmodule.LevelDB(dbpath)

    def close_spider(self, spider):
        # Do compactation each time to save space and also recreate files to
        # avoid them being removed in storages with timestamp-based autoremoval.
        if self.dbdriver == 'plyvel':
            self.db.compact_range()
        elif self.dbdriver == 'leveldb':
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
        if self.dbdriver == 'plyvel':
            with self.db.write_batch() as batch:
                batch.put(key + b'_data', pickle.dumps(data, protocol=2))
                batch.put(key + b'_time', to_bytes(str(time())))
        elif self.dbdriver == 'leveldb':
            batch = self.dbmodule.WriteBatch()
            batch.Put(key + b'_data', pickle.dumps(data, protocol=2))
            batch.Put(key + b'_time', to_bytes(str(time())))
            self.db.Write(batch)

    def _read_data(self, spider, request):
        key = to_bytes(self._request_key(request))
        try:
            if self.dbdriver == 'plyvel':
                ts = self.db.get(key + b'_time')
                if ts is None:
                    raise KeyError
            elif self.dbdriver == 'leveldb':
                ts = self.db.Get(key + b'_time')
        except KeyError:
            return  # not found or invalid entry

        if 0 < self.expiration_secs < time() - float(ts):
            return  # expired

        try:
            if self.dbdriver == 'plyvel':
                data = self.db.get(key + b'_data')
                if data is None:
                    raise KeyError
            elif self.dbdriver == 'leveldb':
                data = self.db.Get(key + b'_data')
        except KeyError:
            return  # invalid entry
        else:
            return pickle.loads(data)
