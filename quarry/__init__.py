import os
from flask import Flask
from flask.ext.cors import cross_origin
from toolbox import tools
from toolbox.emailer import ExceptionEmail
import traceback

def create_app(hostname):
    app = Flask(__name__)
    db = tools.initialize_db(app)

    dev = os.environ.get('DEVEL', 'FALSE').upper() == 'TRUE'
    app.debug = dev

    # This is required for subdomains to work
    app.config["SERVER_NAME"] = hostname
    if dev:
        app.config["SERVER_NAME"] += ":%s" % (os.environ.get('PORT'))

    app.host = tools.get_host_by_hostname(hostname)

    @app.route('/<media_name>', subdomain='media')
    @cross_origin()
    def media(media_name):
        return tools.retrieve_image(media_name, app.host.bucketname)

    if app.host is None:
        # This host doesn't exist. Add a ping endpoint for monitoring.
        @app.route('/ping')
        def ping():
            return ''

        return app

    # Set the error handler/mailer
    if not app.debug:
        @app.errorhandler(Exception)
        def catch_all(exception):
            tb = traceback.format_exc()
            ExceptionEmail(exception, tb, app.host, "quarry").send()

    app.logger.debug("App created for %s" % (app.host.hostname))

    return app
