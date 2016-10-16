import json
import requests
import json
import sys, os
import pika, re
import zlib
from bs4 import BeautifulSoup
requests.packages.urllib3.disable_warnings()

class FacebookSuggestedPageAPI:
    _cookie = open('cookie.txt', 'r').readline()

    def getPageData(self, cookie=_cookie, pageLink="https://www.facebook.com/donlaima/"):
        #
        # Parse page data
        #
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
        res = requests.get(pageLink, verify=False, headers=headers)
        res.encoding  = "utf-8"

        #find match for category 
        matches = re.findall(r'categoryLabel:"([^"]+)"', res.text)
        
        #to find content, we must find and parse the meta tag
        #we can regex it but soup is faster
        soup = BeautifulSoup(res.text, "html.parser")
        meta_description = soup.select("meta[name='description']")
        
        #get the content attribute of the description meta tag
        meta_description_content = meta_description[0].get('content')
        # find regex match for page name
        dmatches = re.findall(r'ownerName:"([^"]+)"', res.text)
        # find regex match for page description
        lmatch = re.findall(r'([0-9,]+)', meta_description_content)
        # find regex match for post description
        pmatch = re.findall(r'{body:{text:"([^"]+)', res.text)

        return {
            "title": dmatches[0],
            "category": matches[0],
            "description": meta_description_content,
            "likes": int(lmatch[0].replace(",", "")),
            "mentions": int(lmatch[1].replace(",", ""))
        }
        
    def querySuggestions(self,cookie=_cookie,pageId='838617286180599'):
        #
        # Query suggestions given page id
        # returns dict of (pageId, pageName, pageLink)

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
        
        res = requests.get("https://www.facebook.com/pages/?ref=page_suggestions_on_liking_refresh&frompageid=" + str(pageId), verify=False, headers=headers )
        res.encoding  = "utf-8"
        body = res.text
        

        # find regex matches for 
        # pageID: string, pageName: string, pageProfileName: some sort of facebook's dom identifier
        matches = re.findall(r'pageID:([0-9]+),pageName:"([^"]+)".*?page_profile_name:{.*?(__elem.*?)"}', body)
        A = []
        for m in matches:
            # find the identifier referred to by pageProfileName
            # and grab the element ID as identified by pageProfileName
            # Facebook / React (or something) stores the target element ID
            # in a some array of the following format 
            # [pageProfileName, elementID, some number]  <- call this Gamma
            # what we want is elementID so we'll query for it using pageProfileName
            pageProfileName = m[2]
            GammaMatches = re.findall(r'\["'+pageProfileName+'",\s*"([^"]+)".*?\]', body)
            datum = list(m)
            # datum.append(GammaMatches[0])

            # after we get Gamma we can get 
            # link href with id equal Gamma, call this alphaTagElem
            aTags = re.findall(r'<a.*?>.*?</a>', body)
            aTagHtml = "\n".join(aTags)
            soup = BeautifulSoup(aTagHtml, "html.parser")
            alphaTagElem = soup.find(id=GammaMatches[0])
            datum[2] = (alphaTagElem.get('href'))

            A.append({
                "pageId": datum[0],
                "pageTitle": datum[1],
                "pageUrl": datum[2]
            })
            
        return A

fsp = FacebookSuggestedPageAPI()
# pd = fsp.getPageData()
# print(pd)
sugseed = fsp.querySuggestions()
print(sugseed)
# for sug in sugseed:
#    A = fsp.querySuggestions(pageId=sug[0]) 
#    print(A)