from flask import Blueprint, request, jsonify, session
from models import User
from db import db

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json(silent=True) or {}
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    if not username or not password:
        return jsonify({'error': 'Username and password are required'}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({'error': 'Username already exists'}), 400
    user = User(username=username)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return jsonify({'message': 'User registered', 'user': user.to_dict()})

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json(silent=True) or {}
    user = User.query.filter_by(username=data.get('username')).first()
    if user and user.check_password(data.get('password') or ''):
        session['user_id'] = user.id
        return jsonify({'message': 'Logged in', 'user': user.to_dict()})
    return jsonify({'error': 'Invalid credentials'}), 401

@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return jsonify({'message': 'Logged out'})

@auth_bp.route('/me', methods=['GET'])
def me():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Not logged in'}), 401
    user = User.query.get(user_id)
    if not user:
        # Session can become stale if the DB is reset or the user row is deleted.
        session.pop('user_id', None)
        return jsonify({'error': 'Not logged in'}), 401
    return jsonify(user.to_dict())

@auth_bp.route('/profile', methods=['PATCH'])
def update_profile():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Not logged in'}), 401
    user = User.query.get(user_id)
    if not user:
        session.pop('user_id', None)
        return jsonify({'error': 'Not logged in'}), 401

    data = request.get_json(silent=True) or {}
    modes = data.get('account_modes', [])
    topics = data.get('task_topics', [])
    if not isinstance(modes, list) or not any(mode in ('worker', 'contractor') for mode in modes):
        return jsonify({'error': 'Select at least one account mode'}), 400
    if not isinstance(topics, list) or not topics:
        return jsonify({'error': 'Select at least one task topic'}), 400

    clean_modes = [mode for mode in ('worker', 'contractor') if mode in modes]
    clean_topics = []
    for topic in topics:
        value = str(topic).strip().lower()
        if value and value not in clean_topics:
            clean_topics.append(value)

    user.account_modes = ','.join(clean_modes)
    user.task_topics = ','.join(clean_topics[:12])
    user.onboarding_completed = bool(data.get('onboarding_completed', False))
    db.session.commit()
    return jsonify({'message': 'Profile updated', 'user': user.to_dict()})
