import json
import os
import secrets
import time
import urllib.error
import urllib.request

from eth_keys import keys
from eth_utils import keccak
from flask import Blueprint, request, jsonify, session
from models import User, WorldIDNullifier
from db import db

world_bp = Blueprint('world', __name__)

WORLD_ID_APP_ID = os.getenv('WORLD_ID_APP_ID', '')
WORLD_ID_RP_ID = os.getenv('WORLD_ID_RP_ID', '')
WORLD_ID_ACTION = os.getenv('WORLD_ID_ACTION', 'verify-account')
WORLD_ID_ENVIRONMENT = os.getenv('WORLD_ID_ENVIRONMENT', 'staging')
WORLD_ID_SIGNING_KEY = os.getenv('WORLD_ID_SIGNING_KEY', '')
WORLD_ID_VERIFY_BASE_URLS = {
    'production': 'https://developer.world.org',
    'staging': 'https://staging-developer.worldcoin.org',
}


def _current_user():
    user_id = session.get('user_id')
    if not user_id:
        return None
    return User.query.get(user_id)


def _world_configured():
    return all([WORLD_ID_APP_ID, WORLD_ID_RP_ID, WORLD_ID_SIGNING_KEY])


def _hash_to_field(input_bytes):
    value = int.from_bytes(keccak(input_bytes), 'big') >> 8
    return value.to_bytes(32, 'big')


def _compute_signature_message(nonce, created_at, expires_at, action):
    action_hash = _hash_to_field(action.encode('utf-8')) if action else b''
    return (
        b'\x01'
        + nonce
        + int(created_at).to_bytes(8, 'big')
        + int(expires_at).to_bytes(8, 'big')
        + action_hash
    )


def _sign_request(signing_key_hex, action, ttl_seconds=300):
    raw_key = signing_key_hex[2:] if signing_key_hex.startswith('0x') else signing_key_hex
    private_key = keys.PrivateKey(bytes.fromhex(raw_key))
    nonce = _hash_to_field(secrets.token_bytes(32))
    created_at = int(time.time())
    expires_at = created_at + ttl_seconds
    message = _compute_signature_message(nonce, created_at, expires_at, action)
    prefix = b'\x19Ethereum Signed Message:\n' + str(len(message)).encode('ascii')
    digest = keccak(prefix + message)
    signature = private_key.sign_msg_hash(digest)
    signature_bytes = (
        signature.r.to_bytes(32, 'big')
        + signature.s.to_bytes(32, 'big')
        + bytes([signature.v + 27])
    )
    return {
        'sig': '0x' + signature_bytes.hex(),
        'nonce': '0x' + nonce.hex(),
        'created_at': created_at,
        'expires_at': expires_at,
    }


@world_bp.route('/config', methods=['GET'])
def config():
    return jsonify({
        'configured': _world_configured(),
        'app_id': WORLD_ID_APP_ID,
        'rp_id': WORLD_ID_RP_ID,
        'action': WORLD_ID_ACTION,
        'environment': WORLD_ID_ENVIRONMENT,
    })


@world_bp.route('/rp-signature', methods=['POST'])
def rp_signature():
    user = _current_user()
    if not user:
        return jsonify({'error': 'Not logged in'}), 401
    if not _world_configured():
        return jsonify({'error': 'World ID is not configured on the server'}), 503

    data = request.get_json(silent=True) or {}
    action = data.get('action', WORLD_ID_ACTION)
    if action != WORLD_ID_ACTION:
        return jsonify({'error': 'Invalid World ID action'}), 400

    try:
        signature = _sign_request(WORLD_ID_SIGNING_KEY, action)
    except ValueError:
        return jsonify({'error': 'Invalid World ID signing key'}), 500

    return jsonify({
        'app_id': WORLD_ID_APP_ID,
        'rp_id': WORLD_ID_RP_ID,
        'action': action,
        'environment': WORLD_ID_ENVIRONMENT,
        **signature,
    })


@world_bp.route('/verify', methods=['POST'])
def verify():
    user = _current_user()
    if not user:
        return jsonify({'error': 'Not logged in'}), 401
    if not _world_configured():
        return jsonify({'error': 'World ID is not configured on the server'}), 503

    data = request.get_json(silent=True) or {}
    idkit_response = data.get('idkitResponse')
    if not idkit_response:
        return jsonify({'error': 'Missing IDKit response'}), 400
    if idkit_response.get('action') != WORLD_ID_ACTION:
        return jsonify({'error': 'Invalid World ID action'}), 400

    base_url = WORLD_ID_VERIFY_BASE_URLS.get(WORLD_ID_ENVIRONMENT)
    if not base_url:
        return jsonify({'error': 'Invalid World ID environment'}), 500

    verify_url = f'{base_url}/api/v4/verify/{WORLD_ID_RP_ID}'
    encoded_body = json.dumps(idkit_response).encode('utf-8')
    world_request = urllib.request.Request(
        verify_url,
        data=encoded_body,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )

    try:
        with urllib.request.urlopen(world_request, timeout=15) as response:
            verification = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode('utf-8')
        return jsonify({'error': 'World ID verification failed', 'detail': detail}), 400
    except urllib.error.URLError as exc:
        return jsonify({'error': 'Could not reach World ID verification API', 'detail': str(exc)}), 502

    if not verification.get('success'):
        return jsonify({'error': 'World ID verification failed', 'detail': verification}), 400

    nullifier = verification.get('nullifier')
    if not nullifier:
        for result in verification.get('results', []):
            if result.get('success') and result.get('nullifier'):
                nullifier = result['nullifier']
                break
    if not nullifier:
        return jsonify({'error': 'World ID response did not include a nullifier'}), 400

    existing = WorldIDNullifier.query.filter_by(
        nullifier=nullifier,
        action=WORLD_ID_ACTION,
    ).first()
    if existing and existing.user_id != user.id:
        return jsonify({'error': 'This World ID proof was already used'}), 409
    if not existing:
        db.session.add(WorldIDNullifier(
            nullifier=nullifier,
            action=WORLD_ID_ACTION,
            user=user,
        ))

    user.world_id_verified = True
    db.session.commit()
    return jsonify({'message': 'World ID verified', 'verification': verification})
