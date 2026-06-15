from scraper.items import EventItem, EventLineupItem
from scrapy.exceptions import DropItem
from scrapy.exporters import JsonLinesItemExporter


class DuplicatesPipeline(object):
    """Removes duplicates using the 'id' field, tracked per item class.
    Pre-loads IDs from existing JSONL files so append runs don't re-insert already-scraped items.
    """

    def __init__(self):
        self._seen: dict[str, set] = {}

    def open_spider(self, spider):
        import glob, json
        for path in glob.glob("*.jsonl"):
            type_name = path.replace(".jsonl", "")
            self._seen.setdefault(type_name, set())
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                item_id = json.loads(line).get("id")
                                if item_id:
                                    self._seen[type_name].add(item_id)
                            except Exception:
                                pass
            except Exception:
                pass
        spider.logger.info(
            "DuplicatesPipeline pre-loaded IDs: %s",
            {k: len(v) for k, v in self._seen.items()},
        )

    def process_item(self, item, spider):
        key = type(item).__name__
        item_id = item.get("id")
        if not item_id:
            return item
        if key not in self._seen:
            self._seen[key] = set()
        if item_id in self._seen[key]:
            raise DropItem(f"Duplicate {key}: {item_id}")
        self._seen[key].add(item_id)
        return item


# class CustomDuplicatesPipeline(object):
#     """Removes duplicates, using the 'artist', 'date' and 'title' fields as composite key"""
#
#     def __init__(self):
#         self.events_seen = set()
#
#     def process_item(self, item, spider):
#
#         # Only use DuplicatesPipeline for EventItem instances
#         if not isinstance(item, EventItem):
#             return item
#
#         combined_key = f'{item["artist"]}-{item["date"]}-{item["title"]}'
#
#         if combined_key in self.events_seen:
#             raise DropItem("Duplicate item found: %s", item)
#         else:
#             self.events_seen.add(combined_key)
#             return item


class DatesPipeline(object):
    """Reformat the 'date' field, removing the last 3 chars"""

    def process_item(self, item, spider):

        # Only use DuplicatesPipeline for EventItem instances
        if not isinstance(item, EventItem):
            return item

        if item.get("date"):
            item["date"] = item["date"].strip()
            return item
        else:
            raise DropItem(f"Missing date in {item.get('id', '?')}")


class MyJsonLinesItemExporter(object):
    """Distribute items across multiple JSONL files according to item types (type(item).__name__)"""

    def open_spider(self, spider):
        self.item_to_exporter = {}
        self._file_handles = {}

    def close_spider(self, spider):
        for exporter in self.item_to_exporter.values():
            exporter.finish_exporting()
        for f in self._file_handles.values():
            f.flush()
            f.close()

    def _exporter_for_item(self, item):
        type_name = str(type(item).__name__)
        if type_name not in self.item_to_exporter:
            f = open("{}.jsonl".format(type_name), "ab")
            self._file_handles[type_name] = f
            exporter = JsonLinesItemExporter(f, encoding="utf-8", ensure_ascii=False)
            exporter.start_exporting()
            self.item_to_exporter[type_name] = exporter
        return self.item_to_exporter[type_name]

    def process_item(self, item, spider):
        exporter = self._exporter_for_item(item)
        exporter.export_item(item)
        self._file_handles[str(type(item).__name__)].flush()
        return item
