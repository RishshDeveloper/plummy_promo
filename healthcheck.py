"""
Простой HTTP сервер для health-check облачных платформ
Запускается в отдельном потоке вместе с ботом
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import os

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        """Обработка GET запросов"""
        if self.path == '/' or self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status": "healthy", "service": "PlummyPromo Bot"}')
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        """Отключаем логи HTTP сервера"""
        pass

def start_health_check_server(port=8080):
    """Запуск health-check сервера в отдельном потоке"""
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"✅ Health-check сервер запущен на порту {port}")
    return server

