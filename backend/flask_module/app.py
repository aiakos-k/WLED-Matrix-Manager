import os
from logging.config import dictConfig

from dotenv import load_dotenv
from flask import Flask, current_app
from flask_cors import CORS
from flask_migrate import Migrate
from flask_smorest import Api
from werkzeug.exceptions import HTTPException, NotFound

from .db import db

# Logging Configuration
dictConfig(
    {
        "version": 1,
        "formatters": {
            "default": {"format": "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"}
        },
        "handlers": {
            "wsgi": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "default",
            }
        },
        "root": {"level": "INFO", "handlers": ["wsgi"]},
    }
)

# Load environment variables
load_dotenv()

# Flask App erstellen
app = Flask(__name__, static_folder="static_ui")

# CORS Konfiguration
cors = CORS(app)
app.config["CORS_HEADERS"] = "Content-Type"

# API Konfiguration
app.config["PROPAGATE_EXCEPTIONS"] = True
app.config["API_TITLE"] = "Flask REST API"
app.config["API_VERSION"] = "v1"
app.config["OPENAPI_VERSION"] = "3.0.3"
app.config["OPENAPI_URL_PREFIX"] = ""
app.config["OPENAPI_SWAGGER_UI_PATH"] = "/swagger-ui"
app.config["OPENAPI_SWAGGER_UI_URL"] = "https://cdn.jsdelivr.net/npm/swagger-ui-dist/"

# Datenbank Konfiguration
instance_path = os.path.join(os.path.dirname(__file__), "instance")
os.makedirs(instance_path, exist_ok=True)
db_path = os.path.join(instance_path, "dev.db")
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", f"sqlite:///{db_path}")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# Initialisiere Extensions
db.init_app(app)
migrate = Migrate(app, db)
api = Api(app)

# Import all models for migrations (WICHTIG!)
from .models import Device, Frame, Scene, User, UserRole, scene_device_association  # noqa: F401
from .resources.auth_resource import blp as auth_blueprint
from .resources.device_resource import blp as device_blueprint
from .resources.scene_resource import blp as scene_blueprint
from .resources.stats_resource import blp as stats_blueprint

# Registriere API Blueprints
from .resources.user_resource import blp as user_blueprint

api.register_blueprint(auth_blueprint)
api.register_blueprint(user_blueprint, url_prefix="/api")
api.register_blueprint(device_blueprint)
api.register_blueprint(scene_blueprint)
api.register_blueprint(stats_blueprint)


# 404 für nicht existierende API Routen (MUSS VOR serve_react kommen!)
@app.route("/api/<path:path>")  # pragma: no cover
def catch_all_api(path):  # pragma: no cover
    raise NotFound(description=f"API route /api/{path} not found")


# Registriere Serve Blueprint ZULETZT
from .resources.serve import blp as serve_blueprint

api.register_blueprint(serve_blueprint)


# Allgemeiner Error Handler
@app.errorhandler(HTTPException)  # pragma: no cover
def handle_error(error):  # pragma: no cover
    default_messages = {
        400: "Bad Request",
        404: "Resource not found",
        422: "Unprocessable Entity",
        500: "Internal server error",
        501: "Not yet implemented",
        502: "Bad Gateway",
    }

    current_app.logger.error("HTTP %s: %s", error.code, getattr(error, "description", error))

    payload = getattr(error, "data", None)
    if isinstance(payload, dict):
        if "messages" in payload:
            return {"message": "Validation error", "errors": payload["messages"]}, error.code
        if "message" in payload:
            return {"message": payload["message"]}, error.code

    return {"message": default_messages.get(error.code, "Unknown error")}, error.code


@app.errorhandler(Exception)
def handle_uncaught_exception(error):
    current_app.logger.error("Uncaught exception: %s", error, exc_info=True)
    return {"message": "Internal server error"}, 500


# Für direkte Ausführung während der Entwicklung
if __name__ == "__main__":  # pragma: no cover
    app.run(host="0.0.0.0", debug=True)
