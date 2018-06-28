================
scrapy-httpcache
================

scrapy-httpcache is a Scrapy `Downloader Middleware <https://doc.scrapy.org/en/latest/topics/downloader-middleware.html#downloader-middleware>`_
to cache HTTP Requests and Responses locally.

This plugin provides the Scrapy HttpCache downloader-middleware, which
provides low-level cache to all HTTP requests and responses.
To do this, the system combines the idea of a `cache storage` (where things are
cached) with a `cache policy` (what things are cached).
This spin-off works as a drop-in replacement to the HttpCache shipped with Scrapy.


Requirements
============

scrapy_ 1.0.0 or newer.

.. _scrapy: https://pypi.python.org/pypi/scrapy


Installation
============

Install scrapy-httpcache using ``pip``::

    $ pip install scrapy-httpcache


Configuration
=============

1. Add HttpCache middleware by including it in ``DOWNLOADER_MIDDLEWARES``
   in your ``settings.py`` file::

      DOWNLOADER_MIDDLEWARES = {
          'scrapy_httpcache.HttpCacheMiddleware': 900,
      }

   It should usually be the last downloader middleware in the priority list,
   where priority ``900`` is the standard and does not usually need changing.

   As this Middleware replaces Scrapy's default HttpCache, that one needs to
   be disabled; so the config becomes this::

      DOWNLOADER_MIDDLEWARES = {
          # ...
          'scrapy.downloadermiddlewares.httpcache.HttpCacheMiddleware': None,
          'scrapy_httpcache.HttpCacheMiddleware': 900,
      }

2. Configure the middleware using the ``HTTPCACHE_*`` settings.

3. Enable the middleware using ``HTTPCACHE_ENABLED`` in your ``setting.py``::

      HTTPCACHE_ENABLED = True

4. Example config::

      # Enable and configure HTTP caching
      # See https://doc.scrapy.org/en/1.5/topics/downloader-middleware.html#httpcache-middleware-settings
      HTTPCACHE_ENABLED = True
      HTTPCACHE_EXPIRATION_SECS = 0
      HTTPCACHE_DIR = 'httpcache'
      HTTPCACHE_IGNORE_HTTP_CODES = []
      HTTPCACHE_POLICY = 'scrapy_httpcache.policy.DummyPolicy'
      HTTPCACHE_STORAGE = 'scrapy_httpcache.storage.FilesystemCacheStorage'

  A config with default settings can be imported from
  ``scrapy_httpcache.default_settings``.


Usage
=====

The HttpCache middleware has various settings which control basic behavior,
as well as backend-specific configuration (e.g. database login settings).
The full list can be found in the documentation or from the source code.

Base plugin settings
--------------------

* ``HTTPCACHE_ENABLED`` — to enable (or disable) this extension
* ``HTTPCACHE_STORAGE`` — storage backend to use with httpcache
* ``HTTPCACHE_POLICY``  — ruleset according to which files are cached and for how long

These usually go in your Scrapy project's ``settings.py``.


Supported Scrapy request meta keys
----------------------------------

* ``dont_cache`` — forcibly disable caching for this request's response,
  independent of the HTTPCACHE_POLICY in action.


Documentation
=============

Documentation can be found in the docs/ directory.


