import os
from flask import Flask, request
from flask import redirect as flask_redirect
from toolbox import tools
from toolbox.emailer import ExceptionEmail
import traceback
from quarry import media

import boto
import requests
import json


class MediaLinker():
    def __init__(self, host):
        self.bucketname = host.bucketname
        self.conn = boto.connect_s3()
        self.bucket = self.conn.get_bucket(host.bucketname)
        self.url = "http://%s.s3.amazonaws.com/" % (self.bucketname)

    def redirect(self, media_name):
        args = request.args.to_dict()
        w = args.get('w', None)
        h = args.get('h', None)
        split = media_name.split(".")
        fn = "".join(split[0:-1])
        ext = split[-1]
        params = {}

        if w is not None or h is not None:  # Some size is given
            fn += "-"  # Separator for size
            if w is not None:
                params["width"] = int(w)
                fn += "%sw" % (w)
            if h is not None:
                params["height"] = int(h)
                fn += "%sh" % (h)

            # Allow the blitline function to be passed as a param.
            # The default function is "resize_to_fit"
            function = args.get("function", "resize_to_fit")

            # The "resize_to_fit" function is the default, so to maintain backwards
            # compatibility we don't add it to the filename
            if function is not "resize_to_fit":
                fn += function

            key = self.bucket.get_key("%s.%s" % (fn, ext))

            if key is None:
                blit_job = {
                    "application_id": os.environ['BLITLINE_APPLICATION_ID'],
                    "src": {
                        "name": "s3", "bucket": self.bucketname, "key":
                        media_name
                    },
                    "functions": []
                }
                if ext.lower() == "gif":
                    # This image is a gif, to resize we need to preprocess
                    blit_job["pre_process"] = {
                        "resize_gif": {
                            "params": params, "s3_destination": {
                                "bucket": self.bucketname, "key": "%s.%s" %
                                (fn, ext)
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
                                "bucket": self.bucketname, "key": "%s.%s" %
                                (fn, ext)
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

            return flask_redirect("%s%s.%s" % (self.url, fn, ext))
        else:
            return flask_redirect("%s%s" % (self.url, media_name))


def create_app(hostname):
    app = Flask(__name__)
    db = tools.initialize_db(app)

    dev = os.environ.get('DEVEL', 'FALSE').upper() == 'TRUE'
    app.debug = dev

    app.host = tools.get_host_by_hostname(hostname)

    if app.host is None:
        # This host doesn't exist. Add a ping endpoint for monitoring.
        @app.route('/ping', subdomain="media")
        def ping():
            return hostname

        return app

    app.media = MediaLinker(app.host)

    # Set the error handler/mailer
    if not app.debug:

        @app.errorhandler(Exception)
        def catch_all(exception):
            tb = traceback.format_exc()
            ExceptionEmail(exception, tb, app.host, "quarry").send()

    media.config = app.config
    app.register_blueprint(media.mod)

    app.logger.debug("App created for %s" % (app.host.hostname))

    return app
