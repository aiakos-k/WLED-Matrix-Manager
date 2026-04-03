class Config:  # pragma: no cover
    CORS_HEADERS = "Content-Type"
    CORS_RESOURCES = {
        r"/api/*": {
            "origins": ["http://localhost:5173"],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            "supports_credentials": True,
            "max_age": 3600,
        }
    }
    CORS_SUPPORTS_CREDENTIALS = True
