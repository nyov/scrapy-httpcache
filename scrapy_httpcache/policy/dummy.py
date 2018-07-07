from scrapy.utils.httpobj import urlparse_cached

from .base import CachePolicy


class DummyPolicy(CachePolicy):

    def __init__(self, settings):
        super(DummyPolicy, self).__init__(settings)
        self.always_store = True # implicit behaviour of this policy
        self.ignore_response_cache_controls = []

    def should_cache_request(self, request):
        return urlparse_cached(request).scheme not in self.ignore_schemes

    def should_cache_response(self, response, request):
        return response.status not in self.ignore_http_codes

    def is_cached_response_fresh(self, cachedresponse, request):
        return True

    def is_cached_response_valid(self, cachedresponse, response, request):
        return True
