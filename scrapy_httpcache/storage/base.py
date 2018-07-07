import logging
from scrapy.utils.request import request_fingerprint
from scrapy.utils.project import data_path


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
