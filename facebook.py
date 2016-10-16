import json
import requests
import json
import sys, os
import pika, re
import zlib
from bs4 import BeautifulSoup
from pymongo import MongoClient

requests.packages.urllib3.disable_warnings()

class StokaInstance:
    STORAGE = {}
    def __init__(self, rabbit_mq_connection, seed_page_object, group_name="fb_default_stoka", cookie=""):
        self.fbHorse = FacebookHorseShitAPI()
        self.group_name = group_name;
        self.rabbit_channel = rabbit_mq_connection.channel();
        self.rabbit_channel.queue_declare(queue=group_name,durable=True)
        self.mongo_client = MongoClient("mongodb://cloud.alphastoka.com:27017")
        self.mongo_db = self.mongo_client['stoka_' + group_name]
        self.cookie = cookie
        # seed the queue
        self.seed_page_object = seed_page_object
        self.astoka_progress = 0
        self.astoka_error = 0
        self.pushQ(seed_page_object)
            
    
    # check if it's in mongo or in some sort of fast memoryview
    # this is for preventing dupe , it's not 100% proof but it's better than nthing
    def inStorage(self, object):
        return object["id"] in self.STORAGE
    
    # push object to work queue
    # so other can pick up this object and populate the queue
    # with the object's follower
    def pushQ(self, object):
        self.rabbit_channel.basic_publish(exchange='',
                      routing_key=self.group_name,
                      body=json.dumps(object),
                      properties=pika.BasicProperties(
                         delivery_mode = 2, 
                      ))

    def _rabbit_consume_callback(self, ch, method, properties, body):
        # Called on pop done
        # this is async pop callback
        ch.basic_ack(delivery_tag = method.delivery_tag)
        p = json.loads(body.decode("utf-8") )

        F = self.fbHorse.querySuggestions(cookie=self.cookie,pageId=p["id"])

        if F is None or len(F) == 0:
            return
        
        for f in F:
            if self.inStorage(f):
                continue
            
            self.pushQ(f)
            self.process(f)

    def popQ(self):
        print("Popping Q")
        self.rabbit_channel.basic_qos(prefetch_count=1)
        self.rabbit_channel.basic_consume(self._rabbit_consume_callback,
                      queue=self.group_name)
        # this is blocking (forever)
        self.rabbit_channel.start_consuming()

    # Processing of the object in each iteration of pop()
    # object = User object (contains id, and username etc.)
    def process(self, object):
        self.astoka_progress = self.astoka_progress + 1
        self.save(self.fbHorse.getPageData(object, self.cookie))
        print("@astoka.progress ", self.astoka_progress)
        print("@astoka.error ", self.astoka_error)

  # persist to mongodb
    def save(self, object):
        # short term memory checking if we have seen this
        self.STORAGE[object["id"]] = True
        try:
            result = self.mongo_db.facebook.insert_one(object)
            print("[x] Persisting %s " % object["title"])
        except Exception as ex:
            self.astoka_error = self.astoka_error + 1
            print("[o] Exception while saving to mongo (might be duplicate)", ex)
    
    # entry point
    def run(self):
        #do work!
        self.popQ()


class FacebookHorseShitAPI:

    def getPageData(self, object, cookie):
        #
        # Parse page data
        # object: relationship object given by querySuggestion
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
        res = requests.get(object["url"], verify=False, headers=headers)
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
        lmatch = re.findall(r'([0-9,]+) likes', meta_description_content)
        tmatch = re.findall(r'([0-9,]+) talking', meta_description_content)
        # find regex match for post description
        pmatch = re.findall(r'{body:{text:"([^"]+)', res.text)

        print(meta_description_content, lmatch[0])
        return {
            "title": dmatches[0],
            "category": matches[0],
            "description": meta_description_content,
            "likes": int(lmatch[0].replace(",", "")),
            "mentions": int(tmatch[0].replace(",", "")),
            "url": object["url"],
            "_title": object["title"],
            "id": object["id"]
        }
        
    def querySuggestions(self,cookie,pageId='838617286180599'):
        print("querying", pageId)

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
        
        url = "https://www.facebook.com/pages/?frompageid=" + str(pageId)
        print(url)
        res = requests.get(url, verify=False, headers=headers )
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
                "id": datum[0],
                "title": datum[1],
                "url": datum[2]
            })
            
        return A


if __name__ == '__main__':
    RABBIT_USR = os.getenv('RABBIT_USR', "rabbitmq")
    RABBIT_PWD = os.getenv('RABBIT_PWD', "Nc77WrHuAR58yUPl")
    RABBIT_PORT = os.getenv('RABBIT_PORT', 32774)
    RABBIT_HOST = os.getenv('RABBIT_HOST', 'localhost')
    SEED_PAGE_NAME = os.getenv('SEED_ID', 'prachyagraphic')
    GROUP_NAME = os.getenv('GROUP_NAME', 'test')
    COOKIE = os.getenv('COOKIE')

    print("using configuration", RABBIT_HOST, RABBIT_PWD, RABBIT_USR, int(RABBIT_PORT))

    credentials = pika.PlainCredentials(RABBIT_USR, RABBIT_PWD)
    print("Connecting to Rabbit..")
    connection = pika.BlockingConnection(pika.ConnectionParameters(
               RABBIT_HOST, port=int(RABBIT_PORT), credentials=credentials))
            
    print("Finding seed id..")
    seed_url = "https://www.facebook.com/%s/" % (SEED_PAGE_NAME,)
    #determine seed id from provided seed username
    res = requests.get(seed_url, verify=False)
    res.encoding  = "utf-8"
    soup = BeautifulSoup(res.text, "html.parser")
    meta = soup.select("meta[property='al:ios:url']")
    seed_id = meta[0].get("content").split("=")[-1]

    print("Starting Stoka with seed %s.." % (seed_id,))
    instance = StokaInstance(connection,seed_page_object={
        "id": seed_id,
        "url": seed_url   
    }, group_name=GROUP_NAME, cookie=COOKIE)

    instance.run()