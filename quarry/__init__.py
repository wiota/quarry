import os
from flask import Flask
from toolbox import tools
from toolbox.emailer import ExceptionEmail
import traceback
from quarry import media


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
