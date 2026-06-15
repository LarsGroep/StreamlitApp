all: build notify

.PHONY: all clean ra partyflock events festivals build discover process notify

module = scraper
object = jsonl

clean:
	rm -rf $(module)/*.$(object)

ra:
	cd $(module) && scrapy crawl ra_artist_spider

partyflock:
	cd $(module) && scrapy crawl partyflock_spider

events:
	cd $(module) && scrapy crawl partyflock_event_spider

festivals:
	cd $(module) && scrapy crawl festival_spider

discover:
	cd $(module) && python discover_artists.py

lastfm:
	cd $(module)/lastfm && python lastfm_scraper.py

scrape-missing:
	cd $(module) && python scrape_missing_partyflock.py

# WARNING: 'build' wipes all JSONL before re-scraping. Use 'scrape-missing' to append only gaps.
build: clean ra partyflock events festivals

process: build discover lastfm
	cd $(module) && python export_to_excel.py

notify: process
	cd $(module) && python3 notifications.py


