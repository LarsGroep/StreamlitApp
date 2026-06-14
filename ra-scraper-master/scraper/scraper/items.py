import scrapy


class EventItem(scrapy.Item):
    id = scrapy.Field()
    date = scrapy.Field()
    artist = scrapy.Field()
    title = scrapy.Field()
    link = scrapy.Field()
    venue = scrapy.Field()
    city = scrapy.Field()


class EventLineupItem(scrapy.Item):
    id = scrapy.Field()
    lineup = scrapy.Field()


class EventPriceItem(scrapy.Item):
    id = scrapy.Field()
    closed_prices = scrapy.Field()
    onsale_prices = scrapy.Field()


class PartyflockArtistItem(scrapy.Item):
    id = scrapy.Field()
    artist = scrapy.Field()
    partyflock_url = scrapy.Field()
    partyflock_artist_id = scrapy.Field()
    fans = scrapy.Field()
    total_performances = scrapy.Field()
    upcoming_performances = scrapy.Field()
    past_performances = scrapy.Field()
    views = scrapy.Field()
    views_since = scrapy.Field()
    photos = scrapy.Field()
    videos = scrapy.Field()
    vote_result = scrapy.Field()
    vote_count = scrapy.Field()
    genres = scrapy.Field()
    last_performance_date = scrapy.Field()
    last_performance_event = scrapy.Field()
    last_performance_venue = scrapy.Field()
    last_performance_city = scrapy.Field()
    scraped_at = scrapy.Field()


class PartyflockEventItem(scrapy.Item):
    id = scrapy.Field()
    artist = scrapy.Field()
    partyflock_artist_id = scrapy.Field()
    event_name = scrapy.Field()
    event_url = scrapy.Field()
    start_date = scrapy.Field()
    venue = scrapy.Field()
    city = scrapy.Field()
    country = scrapy.Field()
    latitude = scrapy.Field()
    longitude = scrapy.Field()
    scraped_at = scrapy.Field()


class PartyflockLineupItem(scrapy.Item):
    id = scrapy.Field()
    event_url = scrapy.Field()
    event_name = scrapy.Field()
    start_date = scrapy.Field()
    venue = scrapy.Field()
    city = scrapy.Field()
    country = scrapy.Field()
    lineup = scrapy.Field()
    scraped_at = scrapy.Field()


class FestivalLineupItem(scrapy.Item):
    id = scrapy.Field()
    festival_name = scrapy.Field()
    festival_year = scrapy.Field()
    artist = scrapy.Field()
    scraped_at = scrapy.Field()


class ArtistBillingItem(scrapy.Item):
    """Per-event billing data scraped from the RA artist page.
    Captures headliner status, full lineup, and venue capacity for each booking.
    Written to ArtistBillingItem.jsonl by the pipeline."""
    id = scrapy.Field()              # "{ra_slug}::{event_id}" — unique per artist+event
    artist = scrapy.Field()          # canonical artist name from RA
    ra_slug = scrapy.Field()         # RA artist slug used for the query
    event_id = scrapy.Field()        # RA event numeric ID
    event_url = scrapy.Field()       # https://ra.co/events/{id}
    date = scrapy.Field()            # YYYY-MM-DD
    title = scrapy.Field()           # event title
    venue = scrapy.Field()           # venue name
    city = scrapy.Field()            # city / area name
    country = scrapy.Field()         # country name
    venue_capacity = scrapy.Field()  # venue capacity (int or None)
    lineup = scrapy.Field()          # ordered list of artist names
    headliner_names = scrapy.Field() # subset of lineup marked headliner:true by RA
    is_headliner = scrapy.Field()    # bool — is THIS artist marked as headliner?
    lineup_size = scrapy.Field()     # total artists on bill
    scraped_at = scrapy.Field()
