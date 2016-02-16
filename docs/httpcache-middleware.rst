
HttpCacheMiddleware
-------------------

.. module:: scrapy.downloadermiddlewares.httpcache
   :synopsis: HTTP Cache downloader middleware

.. class:: HttpCacheMiddleware

    This middleware provides low-level cache to all HTTP requests and responses.
    It has to be combined with a cache storage backend as well as a cache policy.

    Scrapy ships with three HTTP cache storage backends:

        * :ref:`httpcache-storage-fs`
        * :ref:`httpcache-storage-dbm`
        * :ref:`httpcache-storage-leveldb`

    You can change the HTTP cache storage backend with the :setting:`HTTPCACHE_STORAGE`
    setting. Or you can also implement your own storage backend.

    Scrapy ships with two HTTP cache policies:

        * :ref:`httpcache-policy-rfc2616`
        * :ref:`httpcache-policy-dummy`

    You can change the HTTP cache policy with the :setting:`HTTPCACHE_POLICY`
    setting. Or you can also implement your own policy.

    .. reqmeta:: dont_cache

    You can also avoid caching a response on every policy using :reqmeta:`dont_cache` meta key equals `True`.

.. _httpcache-policy-dummy:

Dummy policy (default)
~~~~~~~~~~~~~~~~~~~~~~

This policy has no awareness of any HTTP Cache-Control directives.
Every request and its corresponding response are cached.  When the same
request is seen again, the response is returned without transferring
anything from the Internet.

The Dummy policy is useful for testing spiders faster (without having
to wait for downloads every time) and for trying your spider offline,
when an Internet connection is not available. The goal is to be able to
"replay" a spider run *exactly as it ran before*.

In order to use this policy, set:

* :setting:`HTTPCACHE_POLICY` to ``scrapy_httpcache.policy.DummyPolicy``


.. _httpcache-policy-rfc2616:

RFC2616 policy
~~~~~~~~~~~~~~

This policy provides a RFC2616 compliant HTTP cache, i.e. with HTTP
Cache-Control awareness, aimed at production and used in continuous
runs to avoid downloading unmodified data (to save bandwidth and speed up crawls).

what is implemented:

* Do not attempt to store responses/requests with `no-store` cache-control directive set
* Do not serve responses from cache if `no-cache` cache-control directive is set even for fresh responses
* Compute freshness lifetime from `max-age` cache-control directive
* Compute freshness lifetime from `Expires` response header
* Compute freshness lifetime from `Last-Modified` response header (heuristic used by Firefox)
* Compute current age from `Age` response header
* Compute current age from `Date` header
* Revalidate stale responses based on `Last-Modified` response header
* Revalidate stale responses based on `ETag` response header
* Set `Date` header for any received response missing it
* Support `max-stale` cache-control directive in requests

  This allows spiders to be configured with the full RFC2616 cache policy,
  but avoid revalidation on a request-by-request basis, while remaining
  conformant with the HTTP spec.

  Example:

  Add `Cache-Control: max-stale=600` to Request headers to accept responses that
  have exceeded their expiration time by no more than 600 seconds.

  See also: RFC2616, 14.9.3

what is missing:

* `Pragma: no-cache` support https://www.w3.org/Protocols/rfc2616/rfc2616-sec14.html#sec14.9.1
* `Vary` header support https://www.w3.org/Protocols/rfc2616/rfc2616-sec13.html#sec13.6
* Invalidation after updates or deletes https://www.w3.org/Protocols/rfc2616/rfc2616-sec13.html#sec13.10
* ... probably others ..

In order to use this policy, set:

* :setting:`HTTPCACHE_POLICY` to ``scrapy_httpcache.policy.RFC2616Policy``


.. _httpcache-storage-fs:

Filesystem storage backend (default)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

File system storage backend is available for the HTTP cache middleware.

In order to use this storage backend, set:

* :setting:`HTTPCACHE_STORAGE` to ``scrapy_httpcache.storage.FilesystemCacheStorage``

Each request/response pair is stored in a different directory containing
the following files:

 * ``request_body`` - the plain request body
 * ``request_headers`` - the request headers (in raw HTTP format)
 * ``response_body`` - the plain response body
 * ``response_headers`` - the request headers (in raw HTTP format)
 * ``meta`` - some metadata of this cache resource in Python ``repr()`` format
   (grep-friendly format)
 * ``pickled_meta`` - the same metadata in ``meta`` but pickled for more
   efficient deserialization

The directory name is made from the request fingerprint (see
``scrapy.utils.request.fingerprint``), and one level of subdirectories is
used to avoid creating too many files into the same directory (which is
inefficient in many file systems). An example directory could be::

   /path/to/cache/dir/example.com/72/72811f648e718090f041317756c03adb0ada46c7

.. _httpcache-storage-dbm:

DBM storage backend
~~~~~~~~~~~~~~~~~~~

A DBM_ storage backend is also available for the HTTP cache middleware.

By default, it uses the anydbm_ module, but you can change it with the
:setting:`HTTPCACHE_DBM_MODULE` setting.

In order to use this storage backend, set:

* :setting:`HTTPCACHE_STORAGE` to ``scrapy_httpcache.storage.DbmCacheStorage``

.. _httpcache-storage-leveldb:

LevelDB storage backend
~~~~~~~~~~~~~~~~~~~~~~~

A LevelDB_ storage backend is also available for the HTTP cache middleware.

This backend is not recommended for development because only one process can
access LevelDB databases at the same time, so you can't run a crawl and open
the scrapy shell in parallel for the same spider.

In order to use this storage backend:

* set :setting:`HTTPCACHE_STORAGE` to ``scrapy_httpcache.storage.LeveldbCacheStorage``
* install `LevelDB python bindings`_ like ``pip install leveldb``
* or use the `Plyvel bindings`_ like ``pip install plyvel``

.. _LevelDB: https://github.com/google/leveldb
.. _leveldb python bindings: https://pypi.python.org/pypi/leveldb
.. _plyvel bindings: https://plyvel.readthedocs.io/

DeltaLevelDB storage backend
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A Delta encoding storage backend is also available for the HTTP cache middleware.

This backend is based on the LevelDB storage backend, but uses BSDiff4's
delta encoding to gain additional performance in terms of storage space. The
algorithm works best when crawling domains that have self-similar pages because
it is storing a diff of most 'target' pages off of a 'source' page.

In order to use this storage backend:

* set :setting:`HTTPCACHE_STORAGE` to ``scrapy_httpcache.storage.DeltaLeveldbCacheStorage``
* install `LevelDB python bindings`_ like ``pip install leveldb``
* install `BSDiff4`_ like ``pip install bsdiff4``

.. _LevelDB: http://code.google.com/p/leveldb/
.. _leveldb python bindings: https://pypi.python.org/pypi/leveldb
.. _BSDiff4: https://github.com/ilanschnell/bsdiff4
.. _bsdiff4 python bindings: https://pypi.python.org/pypi/bsdiff4/1.1.4

HTTPCache middleware settings
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The :class:`HttpCacheMiddleware` can be configured through the following
settings:

.. setting:: HTTPCACHE_ENABLED

HTTPCACHE_ENABLED
^^^^^^^^^^^^^^^^^

Default: ``False``

Whether the HTTP cache will be enabled.

.. setting:: HTTPCACHE_EXPIRATION_SECS

HTTPCACHE_EXPIRATION_SECS
^^^^^^^^^^^^^^^^^^^^^^^^^

Default: ``0``

Expiration time for cached requests, in seconds.

Cached requests older than this time will be re-downloaded. If zero, cached
requests will never expire.

.. setting:: HTTPCACHE_DIR

HTTPCACHE_DIR
^^^^^^^^^^^^^

Default: ``'httpcache'``

The directory to use for storing the (low-level) HTTP cache. If empty, the HTTP
cache will be disabled. If a relative path is given, is taken relative to the
project data dir. For more info see: :ref:`topics-project-structure`.

.. setting:: HTTPCACHE_IGNORE_HTTP_CODES

HTTPCACHE_IGNORE_HTTP_CODES
^^^^^^^^^^^^^^^^^^^^^^^^^^^

Default: ``[]``

Don't cache response with these HTTP codes.

.. setting:: HTTPCACHE_IGNORE_MISSING

HTTPCACHE_IGNORE_MISSING
^^^^^^^^^^^^^^^^^^^^^^^^

Default: ``False``

If enabled, requests not found in the cache will be ignored instead of downloaded.

.. setting:: HTTPCACHE_IGNORE_SCHEMES

HTTPCACHE_IGNORE_SCHEMES
^^^^^^^^^^^^^^^^^^^^^^^^

Default: ``['file']``

Don't cache responses with these URI schemes.

.. setting:: HTTPCACHE_STORAGE

HTTPCACHE_STORAGE
^^^^^^^^^^^^^^^^^

Default: ``'scrapy_httpcache.storage.FilesystemCacheStorage'``

The class which implements the cache storage backend.

.. setting:: HTTPCACHE_DBM_MODULE

HTTPCACHE_DBM_MODULE
^^^^^^^^^^^^^^^^^^^^

Default: ``'anydbm'``

The database module to use in the :ref:`DBM storage backend
<httpcache-storage-dbm>`. This setting is specific to the DBM backend.

.. setting:: HTTPCACHE_POLICY

HTTPCACHE_POLICY
^^^^^^^^^^^^^^^^

Default: ``'scrapy_httpcache.policy.DummyPolicy'``

The class which implements the cache policy.

.. setting:: HTTPCACHE_GZIP

HTTPCACHE_GZIP
^^^^^^^^^^^^^^

Default: ``False``

If enabled, will compress all cached data with gzip.
This setting is specific to the Filesystem backend.

.. setting:: HTTPCACHE_ALWAYS_STORE

HTTPCACHE_ALWAYS_STORE
^^^^^^^^^^^^^^^^^^^^^^

Default: ``False``

If enabled, will cache pages unconditionally.

A spider may wish to have all responses available in the cache, for
future use with `Cache-Control: max-stale`, for instance. The
DummyPolicy caches all responses but never revalidates them, and
sometimes a more nuanced policy is desirable.

This setting still respects `Cache-Control: no-store` directives in responses.
If you don't want that, filter `no-store` out of the Cache-Control headers in
responses you feedto the cache middleware.

.. setting:: HTTPCACHE_IGNORE_RESPONSE_CACHE_CONTROLS

HTTPCACHE_IGNORE_RESPONSE_CACHE_CONTROLS
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Default: ``[]``

List of Cache-Control directives in responses to be ignored.

Sites often set "no-store", "no-cache", "must-revalidate", etc., but get
upset at the traffic a spider can generate if it respects those
directives. This allows to selectively ignore Cache-Control directives
that are known to be unimportant for the sites being crawled.

We assume that the spider will not issue Cache-Control directives
in requests unless it actually needs them, so directives in requests are
not filtered.

