from datetime import datetime

from flask import Blueprint, request, jsonify, session
from models import Task, User
from db import db

tasks_bp = Blueprint('tasks', __name__)


def _current_user():
    user_id = session.get('user_id')
    if not user_id:
        return None
    return User.query.get(user_id)


@tasks_bp.route('/', methods=['POST'])
def create_task():
    data = request.json
    task = Task(
        description=data['description'],
        compensation=data.get('compensation', 0.0),
        requester_address=data.get('requester_address'),
    )
    db.session.add(task)
    db.session.commit()
    return jsonify({'message': 'Task created', 'task_id': task.id})

@tasks_bp.route('/', methods=['GET'])
def list_tasks():
    tasks = Task.query.all()
    return jsonify([
        {
            'id': t.id,
            'description': t.description,
            'status': t.status,
            'compensation': t.compensation,
            'assigned_user': t.assigned_user.username if t.assigned_user else None,
            'response_text': t.response_text if t.status in ('submitted', 'completed') else None,
        } for t in tasks
    ])

@tasks_bp.route('/<int:task_id>/accept', methods=['POST'])
def accept_task(task_id):
    user = _current_user()
    if not user:
        return jsonify({'error': 'Not logged in'}), 401
    if not user.world_id_verified:
        return jsonify({'error': 'World ID verification required'}), 403
    task = Task.query.get(task_id)
    if not task or task.status != 'open':
        return jsonify({'error': 'Task not available'}), 400
    # Treat legacy "accept" as "claim".
    task.status = 'claimed'
    task.assigned_user = user
    db.session.commit()
    return jsonify({'message': 'Task accepted'})

@tasks_bp.route('/<int:task_id>/claim', methods=['POST'])
def claim_task(task_id):
    user = _current_user()
    if not user:
        return jsonify({'error': 'Not logged in'}), 401
    if not user.world_id_verified:
        return jsonify({'error': 'World ID verification required'}), 403
    task = Task.query.get(task_id)
    if not task or task.status != 'open':
        return jsonify({'error': 'Task not available'}), 400
    task.status = 'claimed'
    task.assigned_user = user
    db.session.commit()
    return jsonify({'message': 'Task claimed'})


@tasks_bp.route('/<int:task_id>/submit', methods=['POST'])
def submit_task(task_id):
    user = _current_user()
    if not user:
        return jsonify({'error': 'Not logged in'}), 401
    task = Task.query.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    if task.assigned_user_id != user.id or task.status not in ('claimed', 'accepted'):
        return jsonify({'error': 'Task not assigned to you'}), 400

    data = request.get_json(silent=True) or {}
    response_text = data.get('response_text')
    if not response_text or not str(response_text).strip():
        return jsonify({'error': 'response_text is required'}), 400

    task.response_text = str(response_text)
    task.response_submitted_at = datetime.utcnow()
    task.status = 'submitted'

    # Demo payout on submit.
    user.fake_balance += task.compensation
    db.session.commit()
    return jsonify({'message': 'Task submitted'})


@tasks_bp.route('/responses/pending', methods=['GET'])
def pending_responses():
    requester_address = request.args.get('requester_address', '').strip()
    if not requester_address:
        return jsonify({'error': 'requester_address is required'}), 400

    tasks = Task.query.filter_by(
        requester_address=requester_address,
        status='submitted',
        response_delivered_at=None,
    ).all()

    return jsonify([
        {
            'task_id': t.id,
            'response_text': t.response_text,
            'response_submitted_at': int(t.response_submitted_at.timestamp()) if t.response_submitted_at else None,
        }
        for t in tasks
    ])


@tasks_bp.route('/responses/pending-all', methods=['GET'])
def pending_responses_all():
    tasks = Task.query.filter_by(
        status='submitted',
        response_delivered_at=None,
    ).all()

    return jsonify([
        {
            'task_id': t.id,
            'requester_address': t.requester_address,
            'response_text': t.response_text,
            'response_submitted_at': int(t.response_submitted_at.timestamp()) if t.response_submitted_at else None,
        }
        for t in tasks
        if t.requester_address and t.response_text
    ])


@tasks_bp.route('/<int:task_id>/responses/delivered', methods=['POST'])
def mark_response_delivered(task_id):
    task = Task.query.get(task_id)
    if not task:
        return jsonify({'error': 'Task not found'}), 404
    if task.status != 'submitted' or not task.response_text:
        return jsonify({'error': 'No submitted response for this task'}), 400
    if task.response_delivered_at is not None:
        return jsonify({'message': 'Already delivered'})

    task.response_delivered_at = datetime.utcnow()
    db.session.commit()
    return jsonify({'message': 'Marked delivered'})


@tasks_bp.route('/<int:task_id>/complete', methods=['POST'])
def complete_task(task_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Not logged in'}), 401
    task = Task.query.get(task_id)
    if not task or task.status not in ('accepted', 'claimed') or task.assigned_user_id != user_id:
        return jsonify({'error': 'Task not assigned to you'}), 400
    task.status = 'completed'
    user = User.query.get(user_id)
    user.fake_balance += task.compensation
    db.session.commit()
    return jsonify({'message': 'Task completed, balance updated'})
