"""Compatibility entry point. Runs the same shared API as app.py."""
import argparse
from app import create_app

if __name__ == '__main__':
    from waitress import serve
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=5001)
    args = parser.parse_args()
    serve(create_app(), host=args.host, port=args.port)
