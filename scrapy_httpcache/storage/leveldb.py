from __future__ import absolute_import

import os
import zlib
from io import BytesIO
from six.moves import cPickle as pickle
from importlib import import_module
from time import time
from collections import OrderedDict
from scrapy.http import Headers
from scrapy.responsetypes import responsetypes
from scrapy.utils.python import garbage_collect, to_bytes
from scrapy.utils.httpobj import urlparse_cached
from scrapy.utils.gz import gunzip, is_gzipped
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

        if self._is_expired(ts):
            return

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


class DeltaLeveldbCacheStorage(LeveldbCacheStorage):

    def __init__(self, settings):
        super(DeltaLeveldbCacheStorage, self).__init__(settings)
        import bsdiff4
        self.diffmodule = bsdiff4
        self.response_to_cache = ['status', 'url', 'headers', 'body']

    def retrieve_response(self, spider, request):
        domain = self._parse_domain_from_url(spider, request)
        sources = self._read_data(key_to_use=domain)
        delta_response = None
        serial_response = None
        data = None
        delta_response = self._read_data(request_to_use=request)
        if sources and delta_response:
            sources = pickle.loads(sources)
            target_key = to_bytes(self._request_key(request))
            if target_key in sources:
                serial_response = delta_response
            else:
                for source in sources.keys():
                    if target_key in sources[source]:
                        serial_source = self._read_data(key_to_use=source)
                        serial_response = self._decode_response(delta_response, serial_source)
        if not serial_response:
            return
        data = self._deserialize(serial_response)
        response = self._reconstruct_response(data)
        response = self._recompress(response)
        return response

    def store_response(self, spider, request, response):
        target_key = to_bytes(self._request_key(request))
        response = self._decompress(response)
        target_response = self._serialize(response)
        original_length = None
        domain = self._parse_domain_from_url(spider, request)
        sources = self._read_data(key_to_use=domain, ignore_time=True)
        if sources:
            sources = pickle.loads(sources)
            if target_key in sources:
                source_response = self._read_data(key_to_use=target_key, ignore_time=True)
                self._recompute_deltas(target_response, source_response, sources[target_key])
            else:
                source_key = self._select_source(target_response, sources)
                source_response = self._read_data(key_to_use=source_key, ignore_time=True)
                target_response = self._encode_response(target_response, source_response)
                sources[source_key].add(target_key)
        else:
            sources = {target_key: set()}
        if self.dbdriver == 'plyvel':
            with self.db.write_batch() as batch:
                batch.put(target_key + b'_data', target_response)
                batch.put(target_key + b'_time', to_bytes(str(time())))
                batch.put(domain + b'_data', pickle.dumps(sources, protocol=2))
                batch.put(domain + b'_time', to_bytes(str(time())))
        elif self.dbdriver == 'leveldb':
            batch = self.dbmodule.WriteBatch()
            batch.Put(target_key + b'_data', target_response)
            batch.Put(target_key + b'_time', to_bytes(str(time())))
            batch.Put(domain + b'_data', pickle.dumps(sources, protocol=2))
            batch.Put(domain + b'_time', to_bytes(str(time())))
            self.db.Write(batch)

    def _parse_domain_from_url(self, spider, request):
        return to_bytes( urlparse_cached(request).hostname or spider.name )

    def _select_source(self, target, sources):
        return sources.keys()[0]

    def _recompute_deltas(self, new_source, old_source, target_set):
        for target_key in target_set:
            old_response = self._read_data(key_to_use=target_key, ignore_time=True)
            target_response = self._decode_response(old_response, old_source)
            new_delta = self._encode_response(target_response, new_source)
            batch = self.dbmodule.WriteBatch()
            batch.Put(target_key + b'_data', new_delta)
            self.db.Write(batch)

    def _reconstruct_response(self, data):
        url = data['url']
        status = data['status']
        headers = Headers(data['headers'])
        body = data['body']
        respcls = responsetypes.from_args(headers=headers, url=url)
        response = respcls(url=url, headers=headers, status=status, body=body)
        return response

    def _encode_response(self, target, source):
        delta_contents = self.diffmodule.diff(source, target)
        return delta_contents

    def _decode_response(self, delta, source):
        restored_contents = self.diffmodule.patch(source, delta)
        return restored_contents

    def _serialize(self, response):
        dict_response = OrderedDict()
        for k in self.response_to_cache:
            dict_response[k] = getattr(response, k)
        return pickle.dumps(dict_response, 2)

    def _deserialize(self, serial_response):
        return pickle.loads(serial_response)

    def _recompress(self, response):
        content_encoding = response.headers.getlist('Content-Encoding')
        if content_encoding and not is_gzipped(response):
            encoding = content_encoding[-1].lower()
            if encoding == b'gzip' or encoding == b'x-gzip':
                buffer = BytesIO()
                with gzip.GzipFile(mode='wb', fileobj=buffer) as f:
                    f.write(response.body)
                    f.close()
                encoded_body = buffer.getvalue()
            if encoding == b'deflate':
                encoded_body = zlib.compress(response.body)
            response = response.replace(**{'body': encoded_body})
        return response

    def _decompress(self, response):
        content_encoding = response.headers.getlist('Content-Encoding')
        if content_encoding and not is_gzipped(response):
            encoding = content_encoding[-1].lower()
            if encoding == b'gzip' or encoding == b'x-gzip':
                decoded_body = gunzip(response.body)
            if encoding == b'deflate':
                try:
                    decoded_body = zlib.decompress(response.body)
                except zlib.error:
                    decoded_body = zlib.decompress(response.body, -15)
            response = response.replace(**{'body': decoded_body})
        return response

    def _read_data(self, request_to_use=None, key_to_use=None, ignore_time=False):
        if key_to_use:
            key = to_bytes(key_to_use)
        else:
            key = to_bytes(self._request_key(request_to_use))
        if not ignore_time:
            try:
                if self.dbdriver == 'plyvel':
                    ts = self.db.get(key + b'_time')
                    if ts is None:
                        raise KeyError
                elif self.dbdriver == 'leveldb':
                    ts = self.db.Get(key + b'_time')
            except KeyError:
                return  # not found or invalid entry

            if self._is_expired(ts):
                return

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
            return data
