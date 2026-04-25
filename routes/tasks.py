from flask import Blueprint, request, jsonify, session
from models import Task, User
from db import db

tasks_bp = Blueprint('tasks', __name__)

@tasks_bp.route('/', methods=['POST'])
def create_task():
    data = request.json
    task = Task(
        description=data['description'],
        compensation=data.get('compensation', 0.0)
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
            'assigned_user': t.assigned_user.username if t.assigned_user else None
        } for t in tasks
    ])

@tasks_bp.route('/<int:task_id>/accept', methods=['POST'])
def accept_task(task_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Not logged in'}), 401
    user = User.query.get(user_id)
    if not user.world_id_verified:
        return jsonify({'error': 'World ID verification required'}), 403
    task = Task.query.get(task_id)
    if not task or task.status != 'open':
        return jsonify({'error': 'Task not available'}), 400
    task.status = 'accepted'
    task.assigned_user = user
    db.session.commit()
    return jsonify({'message': 'Task accepted'})

@tasks_bp.route('/<int:task_id>/complete', methods=['POST'])
def complete_task(task_id):
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Not logged in'}), 401
    task = Task.query.get(task_id)
    if not task or task.status != 'accepted' or task.assigned_user_id != user_id:
        return jsonify({'error': 'Task not assigned to you'}), 400
    task.status = 'completed'
    user = User.query.get(user_id)
    user.fake_balance += task.compensation
    db.session.commit()
    return jsonify({'message': 'Task completed, balance updated'})
