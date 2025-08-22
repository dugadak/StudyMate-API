#!/usr/bin/env python3
"""
Simple API Server for StudyMate
This server provides basic endpoints for health checks and status monitoring.
"""
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from datetime import datetime

class APIHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_json({'status': 'StudyMate API Server is running', 'timestamp': datetime.now().isoformat()})
        elif self.path == '/health':
            self.send_json({'status': 'healthy', 'service': 'StudyMate API'})
        elif self.path == '/api/':
            self.send_json({'message': 'StudyMate API v1.0', 'endpoints': ['/health', '/api/']})
        else:
            self.send_error(404, 'Not Found')
    
    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def log_message(self, format, *args):
        # Log to stdout for systemd or supervisord
        print(f"[{datetime.now().isoformat()}] {format % args}")

if __name__ == '__main__':
    port = 8000
    httpd = HTTPServer(('0.0.0.0', port), APIHandler)
    print(f'StudyMate API Server running on port {port}...')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print('\nShutting down server...')
        httpd.shutdown()