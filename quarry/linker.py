import os
import boto
import requests
import json
import redis


class MediaLinker():
    def __init__(self, host):
        self.bucketname = host.bucketname
        self.conn = boto.connect_s3()
        self.bucket = self.conn.get_bucket(host.bucketname)
        self.url = "http://%s.s3.amazonaws.com/" % (self.bucketname)
        self.redis = redis.from_url(os.environ['REDISTOGO_URL'])

    def in_s3(self, filename):
        return self.bucket.get_key(filename) is not None

    def in_redis(self, filename):
        return self.redis.get(filename)

    def link(self, media_name, w=None, h=None, function="resize_to_fit"):
        filename = self.filename(media_name, w, h, function)
        url = self.in_redis(filename)

        if not url:
            if w or h and not self.in_s3(filename):
                self.resize(media_name, filename, w, h, function)

        url = "%s%s" % (self.url, filename)
        self.redis.set(filename, url)
        return url

    def filename(self, media_name, w=None, h=None, function="resize_to_fit"):
        fn, ext = os.path.splitext(media_name)
        if w or h:
            fn += "-"  # Separator for size
            if w:
                fn += "%sw" % (w)
            if h:
                fn += "%sh" % (h)
        if function is not "resize_to_fit":
            fn += function
        return "%s%s" % (fn, ext)

    def resize(self, media_name, filename, w, h, function):
        params = {}
        fn, ext = os.path.splitext(media_name)
        if w:
            params["width"] = int(w)
        if h:
            params["height"] = int(h)

        blit_job = {
            "application_id": os.environ['BLITLINE_APPLICATION_ID'],
            "src": {
                "name": "s3",
                "bucket": self.bucketname,
                "key": media_name
            },
            "functions": []
        }
        if ext.lower() == ".gif":
            # This image is a gif, to resize we need to preprocess
            blit_job["pre_process"] = {
                "resize_gif": {
                    "params": params,
                    "s3_destination": {
                        "bucket": self.bucketname,
                        "key": filename
                    }
                }
            }
            # Since we preprocessed, we don't need to run a function
            blit_job["functions"].append({
                "name": "no_op",
                "save": {
                    "image_identifier": media_name
                }
            })
        else:  # This is a regular image
            blit_job["functions"].append({
                "name": function,
                "params": params,
                "save": {
                    "image_identifier": media_name,
                    "save_profiles": "true",
                    "quality": 90,
                    "s3_destination": {
                        "bucket": self.bucketname,
                        "key": filename
                    },
                }
            })

        # POST the job to blitline
        r = requests.post(
            "http://api.blitline.com/job",
            data={
                'json': json.dumps(blit_job)
            })

        # Long-poll to wait for response
        job_id = r.json()["results"]["job_id"]
        _ = requests.get(
            "http://cache.blitline.com/listen/%s" % (job_id))
