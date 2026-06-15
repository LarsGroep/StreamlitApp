import glob
import json

from scrapy.exceptions import DropItem
from scrapy.exporters import JsonLinesItemExporter


class DuplicatesPipeline:
    """Deduplicates by 'id' field per item type; pre-loads existing JSONL so re-runs append cleanly."""

    def __init__(self):
        self._seen: dict[str, set] = {}

    def open_spider(self):
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
        print(f"DuplicatesPipeline pre-loaded: { {k: len(v) for k, v in self._seen.items()} }")

    def process_item(self, item):
        key = type(item).__name__
        item_id = item.get("id")
        if not item_id:
            return item
        self._seen.setdefault(key, set())
        if item_id in self._seen[key]:
            raise DropItem(f"Duplicate {key}: {item_id}")
        self._seen[key].add(item_id)
        return item


class JsonLinesExporter:
    """Routes each item type to its own .jsonl file (append mode)."""

    def open_spider(self):
        self._exporters: dict = {}
        self._handles: dict = {}

    def close_spider(self):
        for exp in self._exporters.values():
            exp.finish_exporting()
        for fh in self._handles.values():
            fh.flush()
            fh.close()

    def _get_exporter(self, item):
        name = type(item).__name__
        if name not in self._exporters:
            fh = open(f"{name}.jsonl", "ab")
            self._handles[name] = fh
            exp = JsonLinesItemExporter(fh, encoding="utf-8", ensure_ascii=False)
            exp.start_exporting()
            self._exporters[name] = exp
        return self._exporters[name], name

    def process_item(self, item):
        exp, name = self._get_exporter(item)
        exp.export_item(item)
        self._handles[name].flush()
        return item
