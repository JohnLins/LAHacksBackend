from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

def _ensure_user_columns():
    engine = db.session.get_bind()
    if engine.dialect.name != 'sqlite':
        return

    existing = {
        row[1]
        for row in db.session.execute(db.text('PRAGMA table_info(user)')).fetchall()
    }
    columns = {
        'account_modes': "ALTER TABLE user ADD COLUMN account_modes VARCHAR(80) DEFAULT ''",
        'task_topics': "ALTER TABLE user ADD COLUMN task_topics TEXT DEFAULT ''",
        'onboarding_completed': 'ALTER TABLE user ADD COLUMN onboarding_completed BOOLEAN DEFAULT 0',
    }
    for name, statement in columns.items():
        if name not in existing:
            db.session.execute(db.text(statement))
    db.session.commit()

def init_db(app):
    with app.app_context():
        db.create_all()
        _ensure_user_columns()
