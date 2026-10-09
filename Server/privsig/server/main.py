import argparse
import os
from pathlib import Path
import uvicorn
from .api import create_app

def main():
    from privsig.runtime import prepare_stdio
    prepare_stdio()
    parser=argparse.ArgumentParser(description='PRIVSIG central school service')
    parser.add_argument('--host',default=os.getenv('PRIVSIG_HOST','127.0.0.1'))
    parser.add_argument('--port',type=int,default=int(os.getenv('PRIVSIG_PORT','8765')))
    parser.add_argument('--database',default=os.getenv('DATABASE_URL','sqlite:///privsig-demo.db'))
    parser.add_argument('--demo',action='store_true')
    args=parser.parse_args()
    if args.demo and args.host not in {'127.0.0.1','localhost','::1'}:
        parser.error('Demo ze znanymi hasłami działa tylko na localhost.')
    if not args.demo and not args.database.startswith('postgresql'):
        parser.error('Centralny serwer wymaga PostgreSQL. SQLite jest tylko do demonstracji.')
    uvicorn.run(create_app(args.database,args.demo),host=args.host,port=args.port,workers=1,access_log=False,use_colors=False)

if __name__=='__main__': main()
