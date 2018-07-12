from __future__ import absolute_import

import os
from six.moves import cPickle as pickle
from importlib import import_module
from time import time
from scrapy.http import Headers
from scrapy.responsetypes import responsetypes

from .base import CacheStorage


class DbmCacheStorage(CacheStorage):
    """ Cache Storage backend for storing data in Unix database (DBM) files.
    """

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
        if self._is_expired(ts):
            return

        return pickle.loads(db['%s_data' % key])
