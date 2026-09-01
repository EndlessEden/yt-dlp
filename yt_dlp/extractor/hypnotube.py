import json
from urllib.parse import quote
from yt_dlp.extractor.common import InfoExtractor

class HypnotubeIE(InfoExtractor):
    _VALID_URL = r'https?://(?:www\.)?hypnotube\.com/video/(?P<id>[^/]+)\.html?'
    
    def _real_extract(self, url):
        video_id = self._match_id(url)
        return_path = f"/video/{video_id}.html"
        post_url = f"https://hypnotube.com/age-gate?return={quote(return_path)}"
        
        # 1. Mimic the JS initial fetch payload
        payload = {"timeZone": "", "languages": ["en-US"]}
        
        response = self._download_json(
            post_url, video_id, 
            note="Clearing age-gate (Initial Pass)",
            data=json.dumps(payload).encode('utf-8'), 
            headers={'Content-Type': 'application/json'}
        )
        
        # Replicate the JS geolocation logic, to respond appropriately to it.[1.8.2026]
        if response.get('escalate') == 'geolocation' and response.get('challenge'):
            self.to_screen("Proxy IP detected; sending geolocation decline fallback...")
            payload['geoChallenge'] = response['challenge']
            payload['geoDeclined'] = True 
            
            response = self._download_json(
                post_url, video_id, 
                note="Clearing age-gate (Geo Fallback Pass)",
                data=json.dumps(payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            
        # Extract the actual URLs [1.9.2026]
        real_url = response.get('redirect') or return_path
        if not real_url.startswith('http'):
            real_url = f"https://hypnotube.com{real_url}"
        
        # Downloading the actual page with videos [1.8.2026]
        webpage = self._download_webpage(real_url, video_id)

        # video URL regex [1.9.2026, v3]
        raw_video_url = self._html_search_regex(
            r'(https?://media\.hypnotube\.com/videos/[^"\']+)',
            webpage,
            'video_url'
        )

        # cleanup the regex returned url and make sure they are unescaped and token is intact. [1.9.2026 -- so much wasted time...]
        video_url = raw_video_url.replace('&amp;', '&')

        # extract thumbnail url, and account for JSON escaping (\/) in the raw HTML. [1.9.2026 -- note: needs improvement]
        raw_thumbnail = self._html_search_regex(
            r'(https?:[\\/]+cdn\.hypnotube\.com[\\/]+thumbs[\\/]+[^"\']+)',
            webpage,
            'thumbnail',
            default=None
        )

        thumbnails = []
        if raw_thumbnail:
            clean_thumb = raw_thumbnail.replace('\\/', '/').replace('&amp;', '&')
            thumbnails.append({'url': clean_thumb})

        # remove proxy for the downloader, if present. Proxy breaks downloading urls of video/thumbnails [1.9.2026 -- i use aria2c in testing and media/cdn subdomains block most public proxies. As the agegate and other site elements dont restrict the subdomains its unneeded. | note: this should be made optional, but fine for now.]
        self._downloader.params['proxy'] = ''

        return {
            'id': video_id,
            'title': self._html_search_regex(r'<title>(.+?)</title>', webpage, 'title', default=video_id),
            'url': video_url,
            'thumbnails': thumbnails,
            'ext': 'mp4',
        }
