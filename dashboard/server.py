#!/usr/bin/env python3
"""
Trading System Status Dashboard Server
Serves a lightweight HTML dashboard showing system status and sanity check results.
"""

import json
import subprocess
import sqlite3
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import os
import sys

# Configuration
PORT = 9000
DASHBOARD_DIR = Path(__file__).parent
API_DIR = Path("/opt/trading/automatictrader-api")
RUNNER_DIR = Path("/opt/trading/traderunner")
DB_PATH = API_DIR / "data" / "automatictrader.db"


class StatusHandler(SimpleHTTPRequestHandler):
    """Custom HTTP handler for status dashboard"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DASHBOARD_DIR), **kwargs)
    
    def do_GET(self):
        if self.path == '/api/status':
            self.send_status_json()
        else:
            super().do_GET()
    
    def send_status_json(self):
        """Send JSON status data"""
        try:
            status = self.get_system_status()
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(status).encode())
        except Exception as e:
            self.send_error(500, f"Error getting status: {str(e)}")
    
    def get_system_status(self):
        """Collect system status information"""
        return {
            'api': self.check_api_status(),
            'worker': self.check_worker_status(),
            'database': self.check_database_status(),
            'sanity': self.get_sanity_results(),
            'logs': self.get_logs()
        }
    
    def check_api_status(self):
        """Check if API is running"""
        try:
            result = subprocess.run(
                ['pgrep', '-f', 'uvicorn app:app'],
                capture_output=True,
                text=True
            )
            running = result.returncode == 0
            
            # Get mode from .env
            mode = "unknown"
            env_file = API_DIR / ".env"
            if env_file.exists():
                with open(env_file) as f:
                    for line in f:
                        if line.startswith('AT_WORKER_MODE'):
                            mode = line.split('=')[1].strip().strip('"')
            
            return {
                'running': running,
                'mode': mode,
                'port': 8080
            }
        except Exception as e:
            return {'running': False, 'mode': 'error', 'error': str(e)}
    
    def check_worker_status(self):
        """Check if worker is running"""
        try:
            result = subprocess.run(
                ['pgrep', '-f', 'python.*worker.py'],
                capture_output=True,
                text=True
            )
            return {'running': result.returncode == 0}
        except Exception as e:
            return {'running': False, 'error': str(e)}
    
    def check_database_status(self):
        """Check database status"""
        try:
            if not DB_PATH.exists():
                return {
                    'initialized': False,
                    'intent_count': 0
                }
            
            conn = sqlite3.connect(str(DB_PATH))
            cursor = conn.cursor()
            
            # Check if tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='order_intents'")
            table_exists = cursor.fetchone() is not None
            
            intent_count = 0
            if table_exists:
                cursor.execute("SELECT COUNT(*) FROM order_intents")
                intent_count = cursor.fetchone()[0]
            
            conn.close()
            
            return {
                'initialized': table_exists,
                'intent_count': intent_count
            }
        except Exception as e:
            return {
                'initialized': False,
                'intent_count': 0,
                'error': str(e)
            }
    
    def get_sanity_results(self):
        """Get latest sanity check results"""
        try:
            sanity_script = RUNNER_DIR / "scripts" / "sanity_check.sh"
            if not sanity_script.exists():
                return {'passed': 0, 'warnings': 0, 'failed': 0}
            
            # Run sanity check
            result = subprocess.run(
                [str(sanity_script)],
                capture_output=True,
                text=True,
                cwd=str(RUNNER_DIR / "scripts")
            )
            
            # Parse output for summary
            output = result.stdout
            passed = 0
            warnings = 0
            failed = 0
            
            for line in output.split('\n'):
                if 'Passed:' in line:
                    passed = int(line.split(':')[1].strip())
                elif 'Warnings:' in line:
                    warnings = int(line.split(':')[1].strip())
                elif 'Failed:' in line:
                    failed = int(line.split(':')[1].strip())
            
            return {
                'passed': passed,
                'warnings': warnings,
                'failed': failed
            }
        except Exception as e:
            return {
                'passed': 0,
                'warnings': 0,
                'failed': 0,
                'error': str(e)
            }
    
    def get_logs(self):
        """Get recent logs from API and Worker using journalctl"""
        try:
            api_log = ""
            worker_log = ""
            errors = []
            
            # Get API logs from journalctl
            try:
                result = subprocess.run(
                    ['journalctl', '-u', 'automatictrader-api', '-n', '10', '--no-pager'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                api_log = result.stdout
                
                # Extract errors
                for line in api_log.split('\n'):
                    if 'ERROR' in line or 'error' in line.lower() or 'failed' in line.lower():
                        # Clean up journalctl formatting
                        if ' -- ' in line:
                            errors.append(line.split(' -- ', 1)[1].strip())
                        else:
                            errors.append(line.strip())
            except Exception as e:
                api_log = f"Error reading API logs: {str(e)}"
            
            # Get Worker logs from journalctl
            try:
                result = subprocess.run(
                    ['journalctl', '-u', 'automatictrader-worker', '-n', '10', '--no-pager'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                worker_log = result.stdout
                
                # Extract errors
                for line in worker_log.split('\n'):
                    if 'ERROR' in line or 'error' in line.lower() or 'failed' in line.lower():
                        if ' -- ' in line:
                            errors.append(line.split(' -- ', 1)[1].strip())
                        else:
                            errors.append(line.strip())
            except Exception as e:
                worker_log = f"Error reading Worker logs: {str(e)}"
            
            return {
                'api_log': api_log.strip() if api_log else None,
                'worker_log': worker_log.strip() if worker_log else None,
                'errors': list(set(errors))[-10:]  # Unique errors, max 10
            }
        except Exception as e:
            return {
                'api_log': None,
                'worker_log': None,
                'errors': [f'Error reading logs: {str(e)}']
            }
    
    def log_message(self, format, *args):
        """Override to customize logging"""
        print(f"[{self.log_date_time_string()}] {format % args}")


def main():
    """Start the status dashboard server"""
    os.chdir(DASHBOARD_DIR)
    
    server_address = ('', PORT)
    httpd = HTTPServer(server_address, StatusHandler)
    
    print("=" * 50)
    print("Trading System Status Dashboard")
    print("=" * 50)
    print(f"Server started on port {PORT}")
    print(f"Access at: http://192.168.178.55:{PORT}")
    print("Press Ctrl+C to stop")
    print("=" * 50)
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...") 
        httpd.shutdown()


if __name__ == '__main__':
    main()
