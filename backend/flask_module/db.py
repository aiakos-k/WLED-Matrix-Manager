from flask import abort
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


def get_or_404(model, id):
    """Get entity by ID or abort with 404 - SQLAlchemy 2.0 compatible"""
    instance = db.session.get(model, id)
    if instance is None:
        abort(404, description=f"{model.__name__} not found")
    return instance
