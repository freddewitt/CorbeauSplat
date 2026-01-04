import os
import subprocess
import signal
import sys
import threading
import http.server
import socketserver
from app.core.system import resolve_binary, resolve_project_root

class SuperSplatEngine:
    """Moteur pour gérer le serveur SuperSplat et le serveur de données"""
    
    def __init__(self):
        self.supersplat_process = None
        self.data_server_process = None
        self.data_server_thread = None
        self.httpd = None
        
    def get_supersplat_path(self):
        root = resolve_project_root()
        return os.path.join(root, "engines", "supersplat")
        
    def start_supersplat(self, port=3000):
        """Lance le serveur SuperSplat via npm serve"""
        splat_path = self.get_supersplat_path()
        if not os.path.exists(splat_path):
            return False, "Moteur SuperSplat non trouvé"
            
        # Stop existing if any
        self.stop_supersplat()
        
        cmd = ["npx", "serve", "dist", "-p", str(port), "--no-clipboard"]
        
        try:
            # On Windows, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
            kwargs = {}
            if sys.platform != "win32":
                kwargs['preexec_fn'] = os.setsid
                
            self.supersplat_process = subprocess.Popen(
                cmd,
                cwd=splat_path,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                # universal_newlines=True, # Avoid text mode to prevent buffering issues sometimes? No, True is better for logging
                text=True,
                **kwargs
            )
            return True, f"SuperSplat démarré sur http://localhost:{port}"
        except Exception as e:
            return False, str(e)

    def stop_supersplat(self):
        """Arrête le serveur SuperSplat"""
        if self.supersplat_process:
            if sys.platform != "win32":
                try:
                    os.killpg(os.getpgid(self.supersplat_process.pid), signal.SIGTERM)
                except:
                    self.supersplat_process.terminate()
            else:
                self.supersplat_process.terminate()
            self.supersplat_process.wait()
            self.supersplat_process = None

    def start_data_server(self, directory, port=8000):
        """Lance un serveur HTTP simple pour servir les PLY (CORS enabled)"""
        self.stop_data_server()
        
        if not os.path.exists(directory):
            return False, "Dossier de données introuvable"
            
        try:
            # We use a custom handler to enable CORS, otherwise SuperSplat can't fetch local files
            class CORSRequestHandler(http.server.SimpleHTTPRequestHandler):
                def end_headers(self):
                    self.send_header('Access-Control-Allow-Origin', '*')
                    super().end_headers()
                
                # Silent log
                def log_message(self, format, *args):
                    pass

            def run_server():
                # Change dir context for the server
                # Thread-safe? We just use directory in handler Init? 
                # SimpleHTTPRequestHandler serves current directory.
                # So we must os.chdir? That's bad for the main app.
                # Better: pass directory to init if possible, or use partial.
                # In Python 3.7+, partial(SimpleHTTPRequestHandler, directory=directory) works.
                from functools import partial
                
                handler_class = partial(CORSRequestHandler, directory=directory)
                
                try:
                    # Bind to localhost only for security
                    self.httpd = socketserver.TCPServer(("127.0.0.1", port), handler_class)
                    self.httpd.serve_forever()
                except Exception as e:
                    print(f"Erreur Data Server: {e}")

            self.data_server_thread = threading.Thread(target=run_server, daemon=True)
            self.data_server_thread.start()
            
            return True, f"Serveur de données démarré sur http://localhost:{port}"
            
        except Exception as e:
            return False, str(e)

    def stop_data_server(self):
        """Arrête le serveur de données"""
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None
        if self.data_server_thread:
            self.data_server_thread.join(timeout=1)
            self.data_server_thread = None

    def stop_all(self):
        self.stop_supersplat()
        self.stop_data_server()
