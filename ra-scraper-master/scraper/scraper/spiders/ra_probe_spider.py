import json
import scrapy

_GRAPHQL_URL = "https://ra.co/graphql"


def _type_query(type_name):
    return json.dumps({
        "query": f"""
        {{
          __type(name: "{type_name}") {{
            kind
            enumValues {{ name }}
            fields {{
              name
              args {{ name type {{ name kind ofType {{ name kind }} }} }}
              type {{ name kind ofType {{ name kind }} }}
            }}
          }}
        }}
        """
    }).encode()


class RaProbeSpider(scrapy.Spider):
    name = "ra_probe"
    allowed_domains = ["ra.co"]
    start_urls = []

    custom_settings = {
        "HTTPERROR_ALLOW_ALL": True,
        "HTTPCACHE_ENABLED": False,
    }

    async def start(self):
        for type_name in ["EventQueryType", "Artist", "Query"]:
            yield scrapy.Request(
                _GRAPHQL_URL,
                method="POST",
                body=_type_query(type_name),
                headers={
                    "Content-Type": "application/json",
                    "Referer": "https://ra.co",
                },
                callback=self.handle,
                meta={"playwright": True, "type_name": type_name},
                dont_filter=True,
            )

    def handle(self, response):
        type_name = response.meta["type_name"]
        pre = response.css("pre ::text").get()
        text = pre if pre else response.text
        try:
            data = json.loads(text)
            t = (data.get("data") or {}).get("__type") or {}
            self.logger.info("=== TYPE: %s ===\n%s", type_name, json.dumps(t, indent=2))
        except Exception as e:
            self.logger.error("Failed to parse response for %s: %s", type_name, e)
            self.logger.info("Raw (first 3000): %s", text[:3000])
