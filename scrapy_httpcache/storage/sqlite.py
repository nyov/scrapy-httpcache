from __future__ import absolute_import

import os
from six.moves import cPickle as pickle
from importlib import import_module
from time import time
from scrapy.http import Headers
from scrapy.responsetypes import responsetypes

from .base import CacheStorage


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


class SqliteCacheStorage(CacheStorage):
    """ Cache Storage backend for storing data in SQLite3 databases.
    """

    def __init__(self, settings):
        super(SqliteCacheStorage, self).__init__(settings)
        self.dbmodule = import_module('sqlite3')
        self.db = None

    def open_spider(self, spider):
        super(SqliteCacheStorage, self).open_spider(spider)
        create = False
        dbpath = os.path.join(self.cachedir, '%s.db' % spider.name)
        if not os.path.isfile(dbpath):
            create = True
        self.db = self.dbmodule.connect(dbpath)
        self.db.row_factory = dict_factory
        if create:
            c = self.db.cursor()
            c.execute('''CREATE TABLE httpcache (request_fingerprint TEXT, timestamp TEXT, data BLOB)''')

    def close_spider(self, spider):
        self.db.commit()
        self.db.close()
        super(SqliteCacheStorage, self).close_spider(spider)

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
        pdata = pickle.dumps(data, protocol=2)

        c = self.db.cursor()
        c.execute('INSERT INTO httpcache (request_fingerprint, timestamp, data) VALUES (?, ?, ?)', (key, str(time()), pdata))

        self.db.commit()

    def _read_data(self, spider, request):
        key = self._request_key(request)
        c = self.db.cursor()
        c.execute('SELECT * FROM httpcache WHERE request_fingerprint=?', (key,))
        row = c.fetchone()
        if not row:
            return  # not found

        ts = row["timestamp"]
        if self._is_expired(ts):
            return

        return pickle.loads(row['data'])
