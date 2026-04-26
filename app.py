from pathlib import Path

import logging
import time
from uuid import uuid4

from flask import Flask, request, g
from flask_cors import CORS
import os

try:
    from dotenv import load_dotenv
    backend_dir = Path(__file__).resolve().parent
    load_dotenv(backend_dir.parent / '.env')
    load_dotenv(backend_dir / '.env', override=True)
except ImportError:
    pass

from db import db, init_db
from routes.auth import auth_bp
from routes.tasks import tasks_bp
from routes.world import world_bp

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev')
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'sqlite:///marketplace.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Allow calling the API from any origin (browser CORS).
# Note: With session cookies, browsers require SameSite=None; Secure.
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)
app.config['SESSION_COOKIE_SAMESITE'] = 'None'
app.config['SESSION_COOKIE_SECURE'] = True

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

@app.before_request
def _request_start():
    g.request_id = request.headers.get("X-Request-ID", uuid4().hex[:12])
    g.t0 = time.time()
    app.logger.info(
        "request start rid=%s method=%s path=%s remote=%s ua=%s",
        g.request_id,
        request.method,
        request.path,
        request.headers.get("X-Forwarded-For", request.remote_addr),
        (request.headers.get("User-Agent") or "")[:120],
    )


@app.after_request
def _request_end(response):
    rid = getattr(g, "request_id", "-")
    t0 = getattr(g, "t0", None)
    elapsed_ms = int((time.time() - t0) * 1000) if t0 else -1
    app.logger.info(
        "request end rid=%s status=%s elapsed_ms=%s",
        rid,
        response.status_code,
        elapsed_ms,
    )
    response.headers["X-Request-ID"] = rid
    return response

db.init_app(app)

# Register blueprints
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(tasks_bp, url_prefix='/api/tasks')
app.register_blueprint(world_bp, url_prefix='/api/world')

with app.app_context():
    init_db(app)

if __name__ == '__main__':
    app.run(
        host='0.0.0.0',
        port=int(os.getenv('PORT', '5000')),
        debug=os.getenv('FLASK_DEBUG', '').lower() in ('1', 'true', 'yes', 'on'),
    )
