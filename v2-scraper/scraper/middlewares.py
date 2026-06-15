import time

from scrapy.downloadermiddlewares.retry import RetryMiddleware
from scrapy.utils.response import response_status_message


class TooManyRequestsRetryMiddleware(RetryMiddleware):
    """Pauses the crawler on 429 and retries after the Retry-After header (default 60s)."""

    def __init__(self, crawler):
        super().__init__(crawler.settings)
        self.crawler = crawler

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)

    def process_response(self, request, response, spider):
        if request.meta.get("dont_retry", False):
            return response
        if response.status == 429:
            retry_after = int(response.headers.get("Retry-After", b"60"))
            spider.logger.warning("Rate-limited (429). Pausing %ds.", retry_after)
            self.crawler.engine.pause()
            time.sleep(retry_after)
            self.crawler.engine.unpause()
            return self._retry(request, response_status_message(429), spider) or response
        if response.status in self.retry_http_codes:
            return self._retry(request, response_status_message(response.status), spider) or response
        return response
