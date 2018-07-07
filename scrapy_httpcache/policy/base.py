from email.utils import mktime_tz, parsedate_tz
from scrapy.utils.python import to_unicode, to_bytes


def parse_cachecontrol(header):
    """Parse Cache-Control header

    https://www.w3.org/Protocols/rfc2616/rfc2616-sec14.html#sec14.9

    >>> parse_cachecontrol(b'public, max-age=3600') == {b'public': None,
    ...                                                 b'max-age': b'3600'}
    True
    >>> parse_cachecontrol(b'') == {}
    True

    """
    directives = {}
    for directive in header.split(b','):
        key, sep, val = directive.strip().partition(b'=')
        if key:
            directives[key.lower()] = val if sep else None
    return directives


def rfc1123_to_epoch(date_str):
    try:
        date_str = to_unicode(date_str, encoding='ascii')
        return mktime_tz(parsedate_tz(date_str))
    except Exception:
        return None


class CachePolicy(object):

    def __init__(self, settings):
        self.ignore_schemes = settings.getlist('HTTPCACHE_IGNORE_SCHEMES')
        self.ignore_http_codes = [int(x) for x in settings.getlist('HTTPCACHE_IGNORE_HTTP_CODES')]
        # currently only used by RFC2616Policy (but defined here fore reuseability):
        self.always_store = settings.getbool('HTTPCACHE_ALWAYS_STORE')
        self.ignore_response_cache_controls = [to_bytes(cc) for cc in
            settings.getlist('HTTPCACHE_IGNORE_RESPONSE_CACHE_CONTROLS')]

    def should_cache_request(self, request):
        raise NotImplementedError

    def should_cache_response(self, response, request):
        raise NotImplementedError

    def is_cached_response_fresh(self, cachedresponse, request):
        raise NotImplementedError

    def is_cached_response_valid(self, cachedresponse, response, request):
        raise NotImplementedError
