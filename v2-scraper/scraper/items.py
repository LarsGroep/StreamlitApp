import scrapy


class BeatportChartItem(scrapy.Item):
    """One track entry from a Beatport genre top-100 chart."""
    id = scrapy.Field()              # beatport track id
    rank = scrapy.Field()            # 1-100
    genre = scrapy.Field()           # e.g. "Tech House"
    genre_id = scrapy.Field()        # beatport genre id
    title = scrapy.Field()
    mix_name = scrapy.Field()
    artists = scrapy.Field()         # list of artist names
    label = scrapy.Field()           # label name
    label_id = scrapy.Field()        # beatport label id
    publish_date = scrapy.Field()
    scraped_at = scrapy.Field()


class BeatportLabelArtistItem(scrapy.Item):
    """Artist appearing on a Beatport label's releases."""
    id = scrapy.Field()              # md5 of label_slug + artist_name
    label_name = scrapy.Field()
    label_slug = scrapy.Field()
    label_id = scrapy.Field()
    framework = scrapy.Field()       # sound framework from framework_labels.json
    tier = scrapy.Field()            # label tier (A+, A, B)
    artist_name = scrapy.Field()
    artist_id = scrapy.Field()       # beatport artist id (if available)
    release_count = scrapy.Field()   # number of releases on this label
    latest_release = scrapy.Field()  # date of latest release
    scraped_at = scrapy.Field()


class MixcloudEpisodeItem(scrapy.Item):
    """One episode/cloudcast from a Mixcloud show."""
    id = scrapy.Field()              # Mixcloud key (path), e.g. /solidgrooves/ep-278/
    show_username = scrapy.Field()   # e.g. "solidgrooves"
    show_name = scrapy.Field()       # display name
    framework = scrapy.Field()       # which sound framework this show maps to
    episode_name = scrapy.Field()
    url = scrapy.Field()
    created_time = scrapy.Field()
    play_count = scrapy.Field()
    listener_count = scrapy.Field()
    favorite_count = scrapy.Field()
    featured_artists = scrapy.Field()  # list extracted from episode title
    tags = scrapy.Field()              # list of Mixcloud genre tags
    scraped_at = scrapy.Field()


class RAGenreArtistItem(scrapy.Item):
    """Artist appearing in RA lineups for a specific genre tag."""
    id = scrapy.Field()              # md5 of genre_tag + artist_name
    genre_tag = scrapy.Field()       # e.g. "tech-house"
    artist_name = scrapy.Field()
    ra_slug = scrapy.Field()
    event_count = scrapy.Field()     # how many genre-tagged events they appear in
    venues = scrapy.Field()          # list of unique venues
    cities = scrapy.Field()          # list of unique cities
    scraped_at = scrapy.Field()


class RALabelArtistItem(scrapy.Item):
    """Artist appearing on an RA label's releases."""
    id = scrapy.Field()              # md5 of label_slug + artist_name
    label_name = scrapy.Field()
    label_slug = scrapy.Field()
    artist_name = scrapy.Field()
    release_count = scrapy.Field()
    scraped_at = scrapy.Field()
