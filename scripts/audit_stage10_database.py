"""Read-only migration audit against configured DB. Never print credentials.

Only SELECT, followed by rollback; no schema/data writes or migration execution.
"""
import json
import os
import sys
from pathlib import Path
from dotenv import dotenv_values
from sqlalchemy import create_engine, text, inspect
from alembic.config import Config
from alembic.script import ScriptDirectory

root = Path(__file__).resolve().parents[1]
config = Config()
config.set_main_option('script_location', str(root / 'migrations'))
result = {'head': ScriptDirectory.from_config(config).get_current_head(),
          'access': 'Read-only version, migration and unique-index metadata; connection rollback',
          'database_modified': False}
try:
    # Do not initialize Flask or run migration commands against application data.
    url = os.environ.get('DATABASE_URL') or dotenv_values(root / '.env').get('DATABASE_URL')
    if not url:
        raise ValueError('Database URL unavailable')
    engine = create_engine(url, connect_args={'connect_timeout': 8})
    with engine.connect() as connection:
        result['current'] = connection.execute(text('SELECT version_num FROM alembic_version')).scalars().all()
        result['server_version'] = connection.execute(text('SELECT VERSION()')).scalar_one()
        result['billing_unique_constraint'] = any(
            set(index['column_names']) == {'participant_id', 'billing_period'}
            for index in inspect(connection).get_unique_constraints('contributions'))
        connection.rollback()
    engine.dispose()
    result['pass'] = result['current'] == [result['head']] == ['3dfb67eddef4'] and result['billing_unique_constraint']
except Exception as error:
    result.update({'pass': False, 'error_category': type(error).__name__})
print(json.dumps(result, indent=2))
sys.exit(0 if result['pass'] else 1)
