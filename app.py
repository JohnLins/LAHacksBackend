from pathlib import Path

from flask import Flask
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
