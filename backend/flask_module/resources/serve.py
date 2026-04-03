import os

from flask import current_app, send_from_directory
from flask_smorest import Blueprint

blp = Blueprint("serve_react", __name__)


@blp.route("/", defaults={"path": ""})
@blp.route("/<path:path>")
def serve_react_app(path):  # pragma: no cover
    static_folder = os.path.join(current_app.static_folder)
    if path != "" and os.path.exists(os.path.join(static_folder, path)):  # pragma: no cover
        return send_from_directory(static_folder, path)  # pragma: no cover
    return send_from_directory(static_folder, "index.html")  # pragma: no cover
