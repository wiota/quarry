from flask import Blueprint, redirect, request
from flask.ext.cors import cross_origin
from toolbox.tools import retrieve_image
from flask import current_app as app
from flask_headers import headers

mod = Blueprint('media', __name__)


@mod.route('/<media_name>')
@mod.route('/image/<media_name>')  # Temporary
@cross_origin()
@headers({'Cache-Control': 'public, max-age=2675309'})
def media(media_name):
    return redirect(app.linker.link(media_name, **request.args.to_dict()))
