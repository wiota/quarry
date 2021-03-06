import os
from quarry import create_app
from landlord import Landlord
from flask import Flask
import newrelic.agent

if __name__ == '__main__' :
    app = Flask(__name__)
    app.debug = os.environ.get('DEVEL', 'FALSE').upper() == 'TRUE'
    app.wsgi_app = Landlord(create_app, subdomains=['media'])
    newrelic.agent.initialize('newrelic.ini')
    port = int(os.environ.get('PORT', 5003))
    app.run(host="0.0.0.0", port=port, use_reloader=True)
