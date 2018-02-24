"""
scrapy_httpcache default settings
"""

DOWNLOADER_MIDDLEWARES = {
    'scrapy_httpcache.HttpCacheMiddleware': 900,
}

HTTPCACHE_ENABLED = False
HTTPCACHE_DIR = 'httpcache'
HTTPCACHE_IGNORE_MISSING = False
HTTPCACHE_STORAGE = 'scrapy_httpcache.httpcache.FilesystemCacheStorage'
HTTPCACHE_EXPIRATION_SECS = 0
HTTPCACHE_ALWAYS_STORE = False
HTTPCACHE_IGNORE_HTTP_CODES = []
HTTPCACHE_IGNORE_SCHEMES = ['file']
HTTPCACHE_IGNORE_RESPONSE_CACHE_CONTROLS = []
HTTPCACHE_DBM_MODULE = 'anydbm' if six.PY2 else 'dbm'
HTTPCACHE_POLICY = 'scrapy_httpcache.httpcache.DummyPolicy'
HTTPCACHE_GZIP = False
