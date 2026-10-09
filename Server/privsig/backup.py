"""Consistent database snapshots, authenticated encryption, explicit restore."""
import argparse
import os
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urlparse,unquote,parse_qs
from cryptography.fernet import Fernet

HEADER=b'PRIVSIG-BACKUP-v1\n'

def pg_env(url):
    parsed=urlparse(url.replace('postgresql+psycopg:','postgresql:',1))
    if parsed.scheme!='postgresql' or not parsed.hostname: raise ValueError('Nieprawidłowy adres PostgreSQL.')
    env=dict(os.environ)
    env.update(PGHOST=parsed.hostname,PGPORT=str(parsed.port or 5432),PGUSER=unquote(parsed.username or ''),
               PGPASSWORD=unquote(parsed.password or ''),PGDATABASE=unquote(parsed.path[1:]))
    query=parse_qs(parsed.query)
    if 'sslmode' in query: env['PGSSLMODE']=query['sslmode'][0]
    return env

def sqlite_path(url):
    if not url.startswith('sqlite:///'): raise ValueError('Nieprawidłowy adres SQLite.')
    return Path(url[len('sqlite:///'):])

def create_backup(database_url,output,key):
    cipher=Fernet(key.encode() if isinstance(key,str) else key)
    with tempfile.TemporaryDirectory(prefix='privsig-backup-') as d:
        temp=Path(d)/'snapshot'
        if database_url.startswith('sqlite'):
            path=sqlite_path(database_url)
            if not path.is_file(): raise ValueError('Nie znaleziono bazy.')
            with sqlite3.connect(path) as source,sqlite3.connect(temp) as target: source.backup(target)
        else:
            subprocess.run(['pg_dump','--format=custom','--no-owner','--file',str(temp)],env=pg_env(database_url),check=True,capture_output=True)
        encrypted=HEADER+cipher.encrypt(temp.read_bytes())
        out=Path(output); out.parent.mkdir(parents=True,exist_ok=True)
        fd=os.open(out,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
        with os.fdopen(fd,'wb') as stream: stream.write(encrypted)
    return out

def restore_backup(database_url,backup,key):
    data=Path(backup).read_bytes()
    if not data.startswith(HEADER): raise ValueError('Nieprawidłowy format kopii.')
    raw=Fernet(key.encode() if isinstance(key,str) else key).decrypt(data[len(HEADER):])
    with tempfile.TemporaryDirectory(prefix='privsig-restore-') as d:
        temp=Path(d)/'snapshot'; temp.write_bytes(raw); os.chmod(temp,0o600)
        if database_url.startswith('sqlite'):
            target_path=sqlite_path(database_url)
            with sqlite3.connect(temp) as source,sqlite3.connect(target_path) as target:
                check=source.execute('PRAGMA integrity_check').fetchone()[0]
                if check!='ok': raise ValueError('Kopia bazy jest uszkodzona.')
                source.backup(target)
        else:
            subprocess.run(['pg_restore','--clean','--if-exists','--no-owner','--exit-on-error','--dbname',pg_env(database_url)['PGDATABASE'],str(temp)],env=pg_env(database_url),check=True,capture_output=True)

def main():
    parser=argparse.ArgumentParser(description='Encrypted PRIVSIG backup')
    parser.add_argument('--generate-key',action='store_true')
    parser.add_argument('--database',default=os.getenv('DATABASE_URL'))
    parser.add_argument('--output')
    parser.add_argument('--restore')
    parser.add_argument('--confirm-replace',action='store_true')
    args=parser.parse_args()
    if args.generate_key: print(Fernet.generate_key().decode()); return
    key=os.getenv('PRIVSIG_BACKUP_KEY')
    if not key or not args.database: parser.error('Ustaw DATABASE_URL i PRIVSIG_BACKUP_KEY.')
    if args.restore:
        if not args.confirm_replace: parser.error('Zatrzymaj serwer i dodaj --confirm-replace, aby zastąpić bazę.')
        restore_backup(args.database,args.restore,key); print('Odtworzono bazę. Unieważnij stare sesje przed uruchomieniem serwera.')
    else:
        output=args.output or 'backups/privsig-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')+'.psbackup'
        create_backup(args.database,output,key); print('Utworzono zaszyfrowaną kopię.')

if __name__=='__main__': main()
