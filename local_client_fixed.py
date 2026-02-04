"""
Minimal clean LocalFileClient used for diagnostics (safe copy).
"""

import os
import json
import uuid
import logging
import hashlib
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LocalFileClient:
    def __init__(self, client_id, local_folder, host='0.0.0.0', port=5000):
        self.client_id = client_id
        self.local_folder = os.path.abspath(local_folder)
        self.host = host
        self.port = port
        self.app = Flask(__name__)
        CORS(self.app)
        os.makedirs(self.local_folder, exist_ok=True)
        self.operations_log = self._load_operations_log()
        self._setup_routes()

    def _setup_routes(self):
        @self.app.route('/health', methods=['GET'])
        def health():
            return jsonify({'status': 'ok', 'client_id': self.client_id})

        @self.app.route('/', methods=['GET'])
        def index():
            return ("<html><body><h2>Local Client " + self.client_id + "</h2>"
                    "<p><a href='/health'>/health</a></p></body></html>"), 200, {'Content-Type': 'text/html'}

    def _load_operations_log(self):
        p = os.path.join(self.local_folder, '.client_log.json')
        if os.path.exists(p):
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def run(self):
        self.app.run(host=self.host, port=self.port, debug=False)


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--id', default=str(uuid.uuid4())[:8])
    p.add_argument('--folder', default='./downloads_local')
    p.add_argument('--host', default='0.0.0.0')
    p.add_argument('--port', type=int, default=5000)
    args = p.parse_args()
    c = LocalFileClient(args.id, args.folder, host=args.host, port=args.port)
    c.run()


if __name__ == '__main__':
    main()
