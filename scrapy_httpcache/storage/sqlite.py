from __future__ import absolute_import

import os
import time
from six.moves import cPickle as pickle
from importlib import import_module
from datetime import datetime
from scrapy.http import Headers
from scrapy.responsetypes import responsetypes

from .base import CacheStorage


CREATE_QUERY = """CREATE TABLE httpcache (
                       request_fingerprint TEXT PRIMARY KEY,
                       timestamp TIMESTAMP,
                       data BLOB
                   )
               """
SELECT_QUERY = """SELECT request_fingerprint,
                         timestamp as "timestamp [timestamp]",
                         data
                  FROM httpcache
                      WHERE request_fingerprint=:request_fingerprint
               """
UPSERT_QUERY = """INSERT INTO httpcache (request_fingerprint, timestamp, data)
                      VALUES (:request_fingerprint, :timestamp, :data)
                  ON CONFLICT(request_fingerprint)
                      DO UPDATE SET timestamp=:timestamp, data=:data
               """
INSERT_QUERY = """INSERT INTO httpcache (request_fingerprint, timestamp, data)
                      VALUES (:request_fingerprint, :timestamp, :data)
               """
UPDATE_QUERY = """UPDATE httpcache
                      SET timestamp=:timestamp, data=:data
                      WHERE request_fingerprint=:request_fingerprint
               """
DELETE_QUERY = """DELETE FROM httpcache
                      WHERE request_fingerprint=:request_fingerprint
               """


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
        self.db = self.dbmodule.connect(dbpath, detect_types=self.dbmodule.PARSE_DECLTYPES|self.dbmodule.PARSE_COLNAMES)
        self.db.text_factory = bytes
        self.db.row_factory = self.dbmodule.Row
        if create:
            with self.db:
                self.db.execute(CREATE_QUERY)

    def close_spider(self, spider):
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

        dbdata = {
            'request_fingerprint': key,
            'timestamp': datetime.now(),
            'data': pickle.dumps(data, protocol=2),
        }
        self._store_data(dbdata)

    def _store_data(self, dbdata):
        if self.dbmodule.sqlite_version_info >= (3, 24, 0):  # upsert available
            with self.db:
                self.db.execute(UPSERT_QUERY, dbdata)
        else:
            try:
                with self.db:
                    self.db.execute(INSERT_QUERY, dbdata)
            except self.dbmodule.IntegrityError:  # assume the error is an existing entry
                with self.db:
                    self.db.execute(UPDATE_QUERY, dbdata)

    def _read_data(self, spider, request):
        key = self._request_key(request)
        for row in self.db.execute(SELECT_QUERY, {'request_fingerprint': key}):
            #ts = row["timestamp"].timestamp()  # Python3 only, Py2 compat. below:
            ts = time.mktime(row["timestamp"].timetuple()) + row["timestamp"].microsecond/1000000.0
            if self._is_expired(ts):
                # cleanup is not currently performed by any backend
                # and potentially unwelcome (e.g. for dummy policy cache replays)
                #self.db.execute(DELETE_QUERY, {'request_fingerprint': key})
                return

            return pickle.loads(row['data'])
        return  # not found (implicit)
