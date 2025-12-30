"""
Web Server con API REST per SmartThermo
Server HTTP asincrono leggero per MicroPython
"""
import socket
import json
import gc
import select


class WebServer:
    """Server web con API REST"""

    def __init__(self, wifi_manager, config, sensor, app_state):
        """
        Inizializza il server web

        Args:
            wifi_manager: istanza WiFiManager
            config: istanza Config
            sensor: istanza MLX90614
            app_state: dizionario con stato app (per temperature, ecc)
        """
        self.wifi_manager = wifi_manager
        self.config = config
        self.sensor = sensor
        self.app_state = app_state
        self.server_socket = None
        self.running = False

    def start(self, port=80):
        """
        Avvia il server web

        Args:
            port: porta su cui ascoltare (default 80)
        """
        ip = self.wifi_manager.get_ip()
        if not ip:
            print("No IP address available")
            return False

        try:
            # Crea socket
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('0.0.0.0', port))
            self.server_socket.listen(5)
            self.server_socket.setblocking(False)

            self.running = True
            print(f"Web server started on http://{ip}:{port}")
            return True

        except Exception as e:
            print(f"Error starting web server: {e}")
            return False

    def stop(self):
        """Ferma il server"""
        self.running = False
        if self.server_socket:
            self.server_socket.close()
            self.server_socket = None
        print("Web server stopped")

    def handle_requests(self, timeout_ms=100):
        """
        Gestisce le richieste in arrivo (chiamare nel loop principale)

        Args:
            timeout_ms: timeout in millisecondi per select
        """
        if not self.running or not self.server_socket:
            return

        try:
            # Check for incoming connections
            readable, _, _ = select.select([self.server_socket], [], [], timeout_ms / 1000.0)

            if self.server_socket in readable:
                client_socket, addr = self.server_socket.accept()
                client_socket.settimeout(3.0)
                self._handle_client(client_socket)

        except OSError:
            pass  # No connection available
        except Exception as e:
            print(f"Error handling request: {e}")

    def _send_string(self, sock, data):
        """Invia una stringa in chunk"""
        data_bytes = data.encode('utf-8')
        total_sent = 0
        chunk_size = 512

        while total_sent < len(data_bytes):
            chunk = data_bytes[total_sent:total_sent + chunk_size]
            sent = sock.send(chunk)
            if sent == 0:
                break
            total_sent += sent

    def _send_response_chunked(self, sock, headers, body):
        """Invia headers e body separatamente in chunk"""
        # Invia headers
        self._send_string(sock, headers)

        # Invia body in chunk più grandi (direttamente da stringa)
        body_bytes = body.encode('utf-8')
        chunk_size = 512
        offset = 0

        while offset < len(body_bytes):
            chunk = body_bytes[offset:offset + chunk_size]
            sent = sock.send(chunk)
            if sent == 0:
                break
            offset += sent
            gc.collect()  # Libera memoria durante l'invio

    def _handle_client(self, client_socket):
        """Gestisce una richiesta client"""
        try:
            # Leggi richiesta
            request = client_socket.recv(1024).decode('utf-8')

            if not request:
                client_socket.close()
                return

            # Parse richiesta
            lines = request.split('\r\n')
            if not lines:
                client_socket.close()
                return

            # Prima riga: GET /path HTTP/1.1
            request_line = lines[0].split(' ')
            if len(request_line) < 2:
                client_socket.close()
                return

            method = request_line[0]
            path = request_line[1]

            # Parse body per POST
            body = None
            if method == 'POST':
                try:
                    # Trova body dopo la riga vuota
                    body_start = request.find('\r\n\r\n')
                    if body_start != -1:
                        body = request[body_start + 4:]
                except:
                    pass

            # Routing - ora ritorna tupla (headers, body) o stringa per compatibilità
            response = self._route_request(method, path, body)

            # Gestisci risposta
            if isinstance(response, tuple):
                # Nuova modalità: headers e body separati
                headers, body = response
                self._send_response_chunked(client_socket, headers, body)
            else:
                # Vecchia modalità: stringa unica (per JSON API)
                self._send_string(client_socket, response)

            client_socket.close()

            gc.collect()

        except Exception as e:
            print(f"Error handling client: {e}")
            try:
                client_socket.close()
            except:
                pass

    def _route_request(self, method, path, body):
        """
        Routing delle richieste

        Args:
            method: GET, POST, etc
            path: percorso richiesto
            body: corpo della richiesta (per POST)

        Returns:
            Risposta HTTP completa
        """
        # API Routes
        if path == '/api/temp':
            return self._api_temp()

        elif path == '/api/ambient':
            return self._api_ambient()

        elif path == '/api/target':
            if method == 'GET':
                return self._api_get_target()
            elif method == 'POST':
                return self._api_set_target(body)

        elif path == '/api/config':
            if method == 'GET':
                return self._api_get_config()
            elif method == 'POST':
                return self._api_set_config(body)

        elif path == '/api/wifi/scan':
            return self._api_wifi_scan()

        elif path == '/api/wifi/test':
            if method == 'POST':
                return self._api_wifi_test(body)

        elif path == '/api/wifi/save':
            if method == 'POST':
                return self._api_wifi_save(body)

        elif path == '/api/status':
            return self._api_status()

        # Static files
        elif path == '/' or path == '/index.html':
            return self._serve_file('index.html', 'text/html')

        elif path == '/style.css':
            return self._serve_file('style.css', 'text/css')

        elif path == '/app.js':
            return self._serve_file('app.js', 'application/javascript')

        # 404
        return self._response(404, 'text/plain', 'Not Found')

    # === API Handlers ===

    def _api_temp(self):
        """GET /api/temp - Legge temperatura oggetto"""
        temp = self.sensor.read_object_temp()
        if temp is not None:
            return self._json_response({'temperature': temp, 'unit': 'C'})
        else:
            return self._json_response({'error': 'Sensor error'}, status=500)

    def _api_ambient(self):
        """GET /api/ambient - Legge temperatura ambiente"""
        temp = self.sensor.read_ambient_temp()
        if temp is not None:
            return self._json_response({'temperature': temp, 'unit': 'C'})
        else:
            return self._json_response({'error': 'Sensor error'}, status=500)

    def _api_get_target(self):
        """GET /api/target - Ottiene target termostato"""
        target = self.config.thermostat_target
        active = self.config.thermostat_active
        return self._json_response({'target': target, 'active': active})

    def _api_set_target(self, body):
        """POST /api/target - Imposta target termostato"""
        try:
            data = json.loads(body)
            if 'target' in data:
                self.config.set('thermostat.target', data['target'])
            if 'active' in data:
                self.config.set('thermostat.active', data['active'])
            return self._json_response({'success': True})
        except Exception as e:
            return self._json_response({'error': str(e)}, status=400)

    def _api_get_config(self):
        """GET /api/config - Ottiene configurazione completa"""
        return self._json_response(self.config._data)

    def _api_set_config(self, body):
        """POST /api/config - Aggiorna configurazione"""
        try:
            data = json.loads(body)
            # Aggiorna configurazione
            self.config._data = data
            self.config.save()
            return self._json_response({'success': True})
        except Exception as e:
            return self._json_response({'error': str(e)}, status=400)

    def _api_wifi_scan(self):
        """GET /api/wifi/scan - Scansiona reti WiFi"""
        try:
            networks = self.wifi_manager.scan_networks()
            return self._json_response({'networks': networks})
        except Exception as e:
            return self._json_response({'error': str(e)}, status=500)

    def _api_wifi_test(self, body):
        """POST /api/wifi/test - Testa connessione WiFi"""
        try:
            data = json.loads(body)
            ssid = data.get('ssid')
            password = data.get('password')

            if not ssid:
                return self._json_response({'error': 'SSID required'}, status=400)

            success = self.wifi_manager.test_connection(ssid, password)
            return self._json_response({'success': success})
        except Exception as e:
            return self._json_response({'error': str(e)}, status=500)

    def _api_wifi_save(self, body):
        """POST /api/wifi/save - Salva configurazione WiFi"""
        try:
            data = json.loads(body)
            ssid = data.get('ssid')
            password = data.get('password')

            if not ssid:
                return self._json_response({'error': 'SSID required'}, status=400)

            # Aggiungi alla lista delle reti note
            known = self.config.get('wifi.known', [])

            # Cerca se esiste già
            found = False
            for i, net in enumerate(known):
                if net['ssid'] == ssid:
                    known[i]['password'] = password
                    found = True
                    break

            if not found:
                known.append({'ssid': ssid, 'password': password})

            self.config.set('wifi.known', known)
            self.config.set('wifi.selected', len(known) - 1 if not found else i)
            self.config.save()

            return self._json_response({'success': True})
        except Exception as e:
            return self._json_response({'error': str(e)}, status=500)

    def _api_status(self):
        """GET /api/status - Status completo del sistema"""
        obj_temp, amb_temp = self.sensor.read_both()

        status = {
            'temperatures': {
                'object': obj_temp,
                'ambient': amb_temp
            },
            'thermostat': {
                'active': self.config.thermostat_active,
                'target': self.config.thermostat_target
            },
            'wifi': self.wifi_manager.get_status()
        }

        return self._json_response(status)

    # === Helper methods ===

    def _json_response(self, data, status=200):
        """Crea risposta JSON"""
        body = json.dumps(data)
        return self._response(status, 'application/json', body)

    def _response(self, status, content_type, body):
        """Crea risposta HTTP"""
        status_text = {
            200: 'OK',
            400: 'Bad Request',
            404: 'Not Found',
            500: 'Internal Server Error'
        }.get(status, 'Unknown')

        # Content-Length in BYTE, non caratteri
        body_bytes = body.encode('utf-8')
        content_length = len(body_bytes)

        response = f"HTTP/1.1 {status} {status_text}\r\n"
        response += f"Content-Type: {content_type}\r\n"
        response += f"Content-Length: {content_length}\r\n"
        response += "Connection: close\r\n"
        response += "Access-Control-Allow-Origin: *\r\n"
        response += "\r\n"
        response += body

        return response

    def _serve_file(self, filename, content_type):
        """Serve un file statico - ritorna (headers, body) per invio efficiente"""
        try:
            with open(f'static/{filename}', 'r') as f:
                body = f.read()

            # IMPORTANTE: Content-Length deve essere in BYTE, non caratteri!
            body_bytes = body.encode('utf-8')
            content_length = len(body_bytes)

            # Crea headers separatamente
            headers = "HTTP/1.1 200 OK\r\n"
            headers += f"Content-Type: {content_type}; charset=utf-8\r\n"
            headers += f"Content-Length: {content_length}\r\n"
            headers += "Connection: close\r\n"
            headers += "Access-Control-Allow-Origin: *\r\n"
            headers += "\r\n"

            return (headers, body)
        except Exception as e:
            print(f"Error serving file {filename}: {e}")
            return self._response(404, 'text/plain', 'File not found')

    def cleanup(self):
        """Libera risorse"""
        self.stop()
        gc.collect()
