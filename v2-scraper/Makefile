.PHONY: all beatport-charts beatport-labels mixcloud ra-genre ra-labels clean build-frameworks

module = scraper

# --- Individual spiders ---

beatport-charts:
	cd $(module) && scrapy crawl beatport_charts

beatport-labels:
	cd $(module) && scrapy crawl beatport_labels

mixcloud:
	cd $(module) && scrapy crawl mixcloud_shows

ra-genre:
	cd $(module) && scrapy crawl ra_genre_artists

ra-labels:
	cd $(module) && scrapy crawl ra_labels

# --- Full scrape (all sources) ---
all: beatport-charts beatport-labels mixcloud ra-genre ra-labels

# --- Post-processing ---
build-frameworks:
	python build_frameworks.py

# WARNING: removes all JSONL output
clean:
	rm -f $(module)/*.jsonl
