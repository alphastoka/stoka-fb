import json
import requests
import json
import sys, os
import pika, re
import zlib

class FacebookSuggestedPageAPI:
    _cookie = open('cookie.txt', 'r').readline()
    def query(self,cookie=_cookie):
        # build request header
        # as realistically as possible to mimic browser
        headers = {
            "accept-encoding": "utf-8",
            "accept-language": "en-US,en;q=0.8,th;q=0.6,ja;q=0.4",
            "upgrade-insecure-requests": "1",
            "cookie": cookie,
            "accept": "text/html",
            "authority": "www.facebook.com",
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "cache-control" : "max-age=0",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/53.0.2785.143 Safari/537.36"
        }
        
        res = requests.get("https://www.facebook.com/pages/?ref=page_suggestions_on_liking_refresh&frompageid=838617286180599", verify=False, headers=headers )
        res.encoding  = "utf-8"
        return res.text

fsp = FacebookSuggestedPageAPI()
body = fsp.query()
matches = re.findall(r'pageID:([0-9]+),pageName:"([^"]+)"', body)
for m in matches:
    print(m)