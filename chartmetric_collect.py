import requests
import csv
import json
import time
from typing import List, Dict

class ChartmetricArtistFetcher:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.chartmetric.com/api/artist/list/filter"
        self.genre_ids = [
            501175, 507730, 501815, 507614, 507733, 501261, 507816, 507725,
            507781, 501633, 501431, 501446, 507655, 507545, 501438, 16873,
            501511, 501176, 507850, 507546, 501267, 507692, 501841
        ]
        self.all_artists = []
        self.seen_artists = set()

    def get_artist_id(self, artist: Dict) -> str:
        """Extract artist ID from response - try multiple field names."""
        # Try different possible field names
        possible_keys = [
            "chartmetric_artist_id",
            "cm_artist",
            "id",
            "artist_id"
        ]
        
        for key in possible_keys:
            if key in artist and artist[key]:
                return str(artist[key])
        
        # If none found, use artist name as fallback
        return artist.get("name", "unknown")

    def fetch_all_artists(self, limit: int = 100, delay: float = 0.3) -> List[Dict]:
        """
        Fetch all artists, one genre at a time.
        """
        headers = {"Authorization": f"Bearer {self.api_key}"}
        max_offset = 10000
        
        print(f"Starting to fetch from {len(self.genre_ids)} genres...")
        print(f"Note: First genre has 55K+ artists. Will fetch up to 10,000 per genre.\n")
        
        for genre_idx, genre_id in enumerate(self.genre_ids, 1):
            print(f"Genre {genre_idx}/{len(self.genre_ids)}: ID {genre_id}")
            
            offset = 0
            genre_count = 0
            
            while offset < max_offset:
                params = {
                    "subTagId": genre_id,
                    "limit": limit,
                    "offset": offset,
                    "sortColumn": "latest.sp_followers"
                }
                
                try:
                    response = requests.get(
                        self.base_url,
                        params=params,
                        headers=headers,
                        timeout=30
                    )
                    response.raise_for_status()
                    
                    data = response.json()
                    inner_obj = data.get("obj", {})
                    artists = inner_obj.get("obj", [])
                    total_count = inner_obj.get("total", 0)
                    
                    if not artists:
                        break
                    
                    # Add artists and track unique ones
                    for artist in artists:
                        artist_id = self.get_artist_id(artist)
                        if artist_id not in self.seen_artists:
                            self.all_artists.append(artist)
                            self.seen_artists.add(artist_id)
                    
                    genre_count += len(artists)
                    print(f"  offset {offset:5d}: {len(artists)} artists fetched")
                    
                    if offset + limit >= total_count or offset + limit >= max_offset:
                        print(f"  → Reached limit. Genre total: {genre_count} artists")
                        break
                    
                    offset += limit
                    time.sleep(delay)
                    
                except Exception as e:
                    print(f"  ERROR at offset {offset}: {e}")
                    break
            
            print(f"  Overall unique artists so far: {len(self.all_artists)}\n")
            time.sleep(0.5)
        
        print(f"\n{'='*60}")
        print(f"✅ COMPLETE! Total unique artists: {len(self.all_artists)}")
        print(f"{'='*60}\n")
        return self.all_artists

    def flatten_artist_dict(self, artist: Dict) -> Dict:
        """Flatten artist dictionary for CSV."""
        flattened = {}
        for key, value in artist.items():
            if isinstance(value, (dict, list)):
                flattened[key] = json.dumps(value) if value else ""
            else:
                flattened[key] = value if value is not None else ""
        return flattened

    def export_to_csv(self, filename: str = "techno_artists.csv") -> None:
        """Export artists to CSV."""
        if not self.all_artists:
            print("No artists to export!")
            return
        
        flattened = [self.flatten_artist_dict(a) for a in self.all_artists]
        all_keys = set()
        for artist in flattened:
            all_keys.update(artist.keys())
        
        fieldnames = sorted(all_keys)
        
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(flattened)
        
        print(f"✅ Exported {len(self.all_artists)} artists to '{filename}'")
        print(f"   Columns: {len(fieldnames)}")


def main():
    API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6NTQzNDQ1NiwiYXBpX2tleV9pZCI6MTU5ODkzLCJ0aW1lc3RhbXAiOjE3ODEwMDkwMzc3MDQsImlhdCI6MTc4MTAwOTAzNywiZXhwIjoxNzgxMDEyNjM3fQ.VtJVWU7utobTK6LnkSND3P5JbLX7zEojR839Keusf-U"
    
    if API_KEY == "YOUR_API_KEY_HERE":
        print("❌ ERROR: Please set your API key in the script!")
        return
    
    fetcher = ChartmetricArtistFetcher(api_key=API_KEY)
    artists = fetcher.fetch_all_artists(limit=100, delay=0.3)
    
    if artists:
        fetcher.export_to_csv("techno_artists.csv")


if __name__ == "__main__":
    main()