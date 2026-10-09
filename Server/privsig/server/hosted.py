"""Hosted API with PostgreSQL and optional fictitious initial school."""
import hashlib
import hmac
import os

from sqlalchemy import select
from .api import create_app, hasher, audit
from .db import School, User


def initialize_fictional_school(app, admin_password, student_password, secret):
    """Called before serving requests. Existing databases are never reset."""
    factory = app.state.factory
    with factory() as db:
        if db.scalar(select(School.id).limit(1)):
            return False
    for password in (admin_password, student_password):
        if len(password) < 16 or password == 'PrivsigDemo!2026':
            raise ValueError('Set distinct initial passwords with at least 16 characters.')
    if admin_password == student_password:
        raise ValueError('Administrator and student passwords must differ.')
    if len(secret) < 32:
        raise ValueError('Set PRIVSIG_BOOTSTRAP_SECRET with at least 32 characters.')
    from .seed import seed_demo, NAMES
    usernames = [pair[0] for pair in NAMES.values()] + ['nauczyciel2']
    passwords = {username: hmac.new(secret.encode(), username.encode(), hashlib.sha256).hexdigest() + 'Aa1!' for username in usernames}
    passwords['admin'] = admin_password
    passwords['uczen'] = student_password
    # Seed data and non-default credential hashes commit in one transaction.
    seed_demo(factory, passwords=passwords)
    with factory.begin() as db:
        users = list(db.scalars(select(User)))
        admin = next(user for user in users if user.username == 'admin')
        for user in users:
            audit(db, admin, 'bootstrap:initial-credentials', user.id)
    return True


def normalized_postgres_url(url):
    for prefix in ('postgresql://', 'postgres://'):
        if url.startswith(prefix):
            return 'postgresql+psycopg://' + url[len(prefix):]
    if url.startswith('postgresql+psycopg://'):
        return url
    raise ValueError('Hosted service requires DATABASE_URL for PostgreSQL.')


def main():
    import uvicorn
    url = normalized_postgres_url(os.environ.get('DATABASE_URL', ''))
    app = create_app(url, demo=False)
    if os.environ.get('PRIVSIG_INITIAL_FICTIONAL_SCHOOL') == '1':
        initialize_fictional_school(
            app, os.environ.get('PRIVSIG_ADMIN_PASSWORD', ''),
            os.environ.get('PRIVSIG_STUDENT_PASSWORD', ''),
            os.environ.get('PRIVSIG_BOOTSTRAP_SECRET', ''),
        )
    uvicorn.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', '10000')),
                workers=1, access_log=False, use_colors=False)


if __name__ == '__main__':
    main()
