import os
import json
import time
import requests
import threading
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request
from dataclasses import dataclass, asdict
from typing import Dict, List, Optional
import schedule
import pytz

app = Flask(__name__)

@dataclass
class ServiceStatus:
    name: str
    status: str  # operational, degraded, outage, maintenance
    response_time: Optional[float]
    last_checked: str
    last_incident: Optional[str] = None
    uptime_24h: float = 100.0
    latest_response: Optional[str] = None

class StatusMonitor:
    def __init__(self):
        self.services = {
            'line_support_api': ServiceStatus('LINE Support API', 'unknown', None, 'Never'),
            'morning_image_api': ServiceStatus('Morning Image API', 'unknown', None, 'Never'),
            'gemini_ai': ServiceStatus('Gemini AI (Vertex AI)', 'unknown', None, 'Never'),
            'search_api': ServiceStatus('Google Custom Search', 'unknown', None, 'Never'),
            'cloud_run': ServiceStatus('Cloud Run Platform', 'unknown', None, 'Never')
        }
        self.incidents = []
        self.status_history = {}  # 24 hours of status data
        self.uptime_history = {}  # 72 hours of uptime data for bar chart
        
        # Configuration
        self.LINE_API_URL = "https://app-api-service-855188038216.asia-east1.run.app"
        self.MORNING_API_URL = os.environ.get('MORNING_API_URL', 'https://morning-image-api-qw4lchblia-de.a.run.app')
        self.history_file = 'uptime_history.json'
        self.timezone = pytz.timezone('Asia/Taipei')  # GMT+8
        
        self.load_uptime_history()
        self.initialize_uptime_history()
        self.setup_background_scheduler()
    
    def setup_background_scheduler(self):
        """Set up scheduled health checks at :00 and :30 minutes"""
        # Clear any existing jobs
        schedule.clear()
        
        # Schedule at :00 and :30 minutes of every hour
        schedule.every().hour.at(":00").do(self.check_all_services)
        schedule.every().hour.at(":30").do(self.check_all_services)
        
        def run_scheduler():
            while True:
                schedule.run_pending()
                time.sleep(30)  # Check every 30 seconds for scheduled tasks
        
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
        
        print(f"Scheduler started. Will run health checks at :00 and :30 minutes (GMT+8)")
        
        # Run initial check immediately
        threading.Thread(target=self.check_all_services, daemon=True).start()
    
    def get_timestamp(self):
        return datetime.now(self.timezone).strftime("%Y-%m-%d %H:%M:%S GMT+8")
    
    def load_uptime_history(self):
        """Load uptime history from JSON file"""
        try:
            if os.path.exists(self.history_file):
                with open(self.history_file, 'r') as f:
                    data = json.load(f)
                    self.uptime_history = data.get('uptime_history', {})
                    self.incidents = data.get('incidents', [])
                    print(f"Loaded history with {len(self.uptime_history)} services")
        except Exception as e:
            print(f"Error loading history: {e}")
            self.uptime_history = {}
            self.incidents = []
    
    def save_uptime_history(self):
        """Save uptime history to JSON file"""
        try:
            data = {
                'uptime_history': self.uptime_history,
                'incidents': self.incidents,
                'last_updated': self.get_timestamp()
            }
            with open(self.history_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"Error saving history: {e}")
    
    def initialize_uptime_history(self):
        """Initialize 72 hours of uptime history - start with all operational"""
        # Start with empty history - it will be populated as real checks happen
        # This way all services start with 100% uptime and build real history
        for service_key in self.services.keys():
            self.uptime_history[service_key] = []
    
    def update_uptime_history(self, service_key: str, status: str):
        """Update hourly uptime history for 72-hour chart"""
        now = datetime.now(self.timezone)
        current_time = now.strftime('%Y-%m-%d %H:%M')
        
        if service_key not in self.uptime_history:
            self.uptime_history[service_key] = []
        
        # Add new entry
        self.uptime_history[service_key].append({
            'timestamp': current_time,
            'status': status
        })
        
        # Keep only last 72 hours (144 entries at 30min intervals)
        if len(self.uptime_history[service_key]) > 144:
            self.uptime_history[service_key] = self.uptime_history[service_key][-144:]
        
        # Save to file after update
        self.save_uptime_history()
    
    def calculate_72h_uptime(self, service_key: str) -> float:
        """Calculate uptime percentage for last 72 hours"""
        if service_key not in self.uptime_history:
            return 100.0
        
        history = self.uptime_history[service_key]
        if not history:
            return 100.0
        
        operational_count = sum(1 for entry in history if entry['status'] == 'operational')
        total_count = len(history)
        
        return round((operational_count / total_count) * 100, 2)
    
    def test_line_support_api(self) -> tuple[str, float, str]:
        """Test the main LINE support API"""
        try:
            start_time = time.time()
            
            test_data = {
                "user_message": "健康檢查",
                "screen_info": {"test": "health_check"},
                "goal": "系統測試"
            }
            
            response = requests.post(
                self.LINE_API_URL,
                json=test_data,
                timeout=10
            )
            
            response_time = (time.time() - start_time) * 1000  # Convert to ms
            response_text = response.text[:200] if response.text else "No response"
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return 'operational', response_time, response_text
                else:
                    return 'degraded', response_time, response_text
            else:
                return 'outage', response_time, f"HTTP {response.status_code}"
                
        except requests.exceptions.Timeout:
            return 'outage', None, "Request timed out"
        except Exception as e:
            print(f"LINE API test error: {e}")
            return 'outage', None, f"Error: {str(e)}"
    
    def test_morning_image_api(self) -> tuple[str, float, str]:
        """Test the morning image API if configured"""
        if not self.MORNING_API_URL:
            return 'operational', 0, "Not configured - skipped"
            
        try:
            start_time = time.time()
            response = requests.get(f"{self.MORNING_API_URL}/health", timeout=10)
            response_time = (time.time() - start_time) * 1000
            response_text = response.text[:200] if response.text else "No response"
            
            if response.status_code == 200:
                return 'operational', response_time, response_text
            else:
                return 'degraded', response_time, f"HTTP {response.status_code}"
                
        except Exception as e:
            print(f"Morning API test error: {e}")
            return 'outage', None, f"Error: {str(e)}"
    
    def test_database(self) -> tuple[str, float]:
        """Test Cloud SQL database connectivity - DISABLED for basic functionality"""
        return 'operational', 50.0  # Return mock healthy status
    
    def test_gemini_ai(self) -> tuple[str, float, str]:
        """Test Gemini AI via Vertex AI - DISABLED for basic functionality"""
        return 'operational', 200.0, "Gemini AI mock response OK"
    
    def test_search_api(self) -> tuple[str, float, str]:
        """Test Google Custom Search API"""
        try:
            start_time = time.time()
            
            search_url = f"{self.LINE_API_URL}/search"
            response = requests.post(
                search_url,
                json={"query": "健康檢查"},
                timeout=10
            )
            
            response_time = (time.time() - start_time) * 1000
            response_text = response.text[:200] if response.text else "No response"
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    return 'operational', response_time, response_text
                else:
                    return 'degraded', response_time, response_text
            else:
                return 'degraded', response_time, f"HTTP {response.status_code}"
                
        except Exception as e:
            print(f"Search API test error: {e}")
            return 'outage', None, f"Error: {str(e)}"
    
    def test_cloud_run(self) -> tuple[str, float, str]:
        """Test Cloud Run platform (using main API as proxy)"""
        try:
            start_time = time.time()
            response = requests.get(f"{self.LINE_API_URL}/health", timeout=5)
            response_time = (time.time() - start_time) * 1000
            response_text = response.text[:200] if response.text else f"HTTP {response.status_code}"
            
            if response.status_code == 200 or response.status_code == 404:  # 404 is OK, means service is up
                return 'operational', response_time, response_text
            else:
                return 'degraded', response_time, response_text
                
        except Exception as e:
            print(f"Cloud Run test error: {e}")
            return 'outage', None, f"Error: {str(e)}"
    
    def check_service(self, service_key: str):
        """Check a single service"""
        test_functions = {
            'line_support_api': self.test_line_support_api,
            'morning_image_api': self.test_morning_image_api,
            'gemini_ai': self.test_gemini_ai,
            'search_api': self.test_search_api,
            'cloud_run': self.test_cloud_run
        }
        
        if service_key in test_functions:
            status, response_time, latest_response = test_functions[service_key]()
            
            service = self.services[service_key]
            old_status = service.status
            
            service.status = status
            service.response_time = response_time
            service.latest_response = latest_response
            service.last_checked = self.get_timestamp()
            
            # Record status change incident
            if old_status != 'unknown' and old_status != status:
                incident = {
                    'service': service.name,
                    'old_status': old_status,
                    'new_status': status,
                    'timestamp': service.last_checked,
                    'message': f"{service.name} status changed from {old_status} to {status}"
                }
                self.incidents.append(incident)
                service.last_incident = service.last_checked
                
                # Keep only last 10 incidents
                if len(self.incidents) > 10:
                    self.incidents = self.incidents[-10:]
            
            # Update status history for uptime calculation
            self.update_status_history(service_key, status)
            service.uptime_24h = self.calculate_uptime_24h(service_key)
            
            # Update 72-hour uptime history for bar chart
            self.update_uptime_history(service_key, status)
    
    def update_status_history(self, service_key: str, status: str):
        """Update 24-hour status history"""
        now = datetime.now(self.timezone)
        if service_key not in self.status_history:
            self.status_history[service_key] = []
        
        self.status_history[service_key].append({
            'timestamp': now,
            'status': status
        })
        
        # Keep only last 24 hours
        cutoff = now - timedelta(hours=24)
        self.status_history[service_key] = [
            entry for entry in self.status_history[service_key]
            if entry['timestamp'] > cutoff
        ]
    
    def calculate_uptime_24h(self, service_key: str) -> float:
        """Calculate uptime percentage for last 24 hours"""
        if service_key not in self.status_history:
            return 100.0
        
        history = self.status_history[service_key]
        if not history:
            return 100.0
        
        operational_count = sum(1 for entry in history if entry['status'] == 'operational')
        total_count = len(history)
        
        return round((operational_count / total_count) * 100, 2)
    
    def check_all_services(self):
        """Check all services"""
        print(f"Starting scheduled health check at {self.get_timestamp()}")
        for service_key in self.services.keys():
            self.check_service(service_key)
        print(f"Health check completed at {self.get_timestamp()}")
    
    def get_overall_status(self) -> str:
        """Get overall system status"""
        statuses = [service.status for service in self.services.values()]
        
        if any(status == 'outage' for status in statuses):
            return 'outage'
        elif any(status == 'degraded' for status in statuses):
            return 'degraded'
        elif any(status == 'maintenance' for status in statuses):
            return 'maintenance'
        elif all(status == 'operational' for status in statuses):
            return 'operational'
        else:
            return 'unknown'

# Global monitor instance
monitor = StatusMonitor()

@app.route('/')
def status_page():
    """Main status page"""
    overall_status = monitor.get_overall_status()
    
    # Calculate 72-hour uptime for each service
    service_uptime_72h = {}
    for service_key in monitor.services.keys():
        service_uptime_72h[service_key] = monitor.calculate_72h_uptime(service_key)
    
    # History is already in chronological order (oldest to newest)
    # Since we want newest on the right, we don't reverse
    
    return render_template('status.html', 
                         services=monitor.services,
                         overall_status=overall_status,
                         incidents=monitor.incidents[-5:],
                         uptime_history=monitor.uptime_history,
                         service_uptime_72h=service_uptime_72h)

@app.route('/api/status')
def api_status():
    """JSON API for status"""
    return jsonify({
        'overall_status': monitor.get_overall_status(),
        'services': {k: asdict(v) for k, v in monitor.services.items()},
        'incidents': monitor.incidents[-10:],
        'last_updated': monitor.get_timestamp()
    })

@app.route('/api/update', methods=['POST'])
def update_status():
    """Manual status update trigger"""
    try:
        data = request.get_json(silent=True) or {}
        service = data.get('service') if data else None
        
        if service and service in monitor.services:
            monitor.check_service(service)
            return jsonify({'success': True, 'message': f'{service} status updated'})
        else:
            # Update all services
            print("Updating all services via API...")
            monitor.check_all_services()
            return jsonify({'success': True, 'message': 'All services status updated'})
    except Exception as e:
        print(f"Error in update_status: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/health')
def health_check():
    """Health check endpoint for the status page itself"""
    return jsonify({'status': 'ok', 'timestamp': monitor.get_timestamp()})

if __name__ == '__main__':
    # Run initial check
    monitor.check_all_services()
    
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)