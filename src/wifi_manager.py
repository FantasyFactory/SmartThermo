"""
WiFi Manager per SmartThermo
Gestisce connessione STA, AP, BOTH con fallback automatico
"""
import network
import time
import gc


class WiFiManager:
    """Gestione WiFi con supporto STA, AP, BOTH"""

    MODE_OFF = "Off"
    MODE_STA = "STA"
    MODE_AP = "AP"
    MODE_BOTH = "BOTH"

    def __init__(self, config):
        """
        Inizializza il WiFi Manager

        Args:
            config: istanza della configurazione
        """
        self.config = config
        self.sta = network.WLAN(network.STA_IF)
        self.ap = network.WLAN(network.AP_IF)
        self.sta_connected = False
        self.ap_active = False

    def start(self):
        """
        Avvia il WiFi in base alla configurazione
        Gestisce fallback ad AP se STA fallisce
        """
        mode = self.config.wifi_mode
        print(f"Starting WiFi in mode: {mode}")

        if mode == self.MODE_OFF:
            self._disable_all()
            return False

        elif mode == self.MODE_STA:
            success = self._start_sta()
            if not success:
                print("STA failed, falling back to AP mode")
                self._start_ap()
            return success

        elif mode == self.MODE_AP:
            return self._start_ap()

        elif mode == self.MODE_BOTH:
            sta_success = self._start_sta()
            ap_success = self._start_ap()
            return sta_success or ap_success

        return False

    def _disable_all(self):
        """Disabilita tutti i WiFi"""
        if self.sta.active():
            self.sta.active(False)
        if self.ap.active():
            self.ap.active(False)
        self.sta_connected = False
        self.ap_active = False
        print("WiFi disabled")

    def _start_sta(self):
        """
        Avvia WiFi in modalità Station (client)

        Returns:
            True se connesso, False altrimenti
        """
        known = self.config.get('wifi.known', [])
        selected = self.config.get('wifi.selected', 0)

        if not known or selected >= len(known):
            print("No valid WiFi configuration")
            return False

        network_config = known[selected]
        ssid = network_config.get('ssid')
        password = network_config.get('password')

        if not ssid:
            print("No SSID configured")
            return False

        print(f"Connecting to WiFi: {ssid}")

        # Attiva STA
        self.sta.active(True)
        time.sleep(1)

        # Connetti
        self.sta.connect(ssid, password)

        # Aspetta connessione (max 15 secondi)
        max_wait = 15
        while max_wait > 0:
            if self.sta.isconnected():
                self.sta_connected = True
                print(f"Connected! IP: {self.sta.ifconfig()[0]}")
                return True

            time.sleep(1)
            max_wait -= 1
            print(".", end="")

        print("\nConnection failed")
        self.sta.active(False)
        self.sta_connected = False
        return False

    def _start_ap(self):
        """
        Avvia WiFi in modalità Access Point

        Returns:
            True se avviato, False altrimenti
        """
        ap_config = self.config.get('wifi.ap_credentials', {})
        ssid = ap_config.get('ssid', 'SmartThermo')
        password = ap_config.get('password', '12345678')
        ap_ip = self.config.get('wifi.ap_ip', '192.168.4.1')

        print(f"Starting AP: {ssid}")

        # Attiva AP
        self.ap.active(True)
        time.sleep(1)

        # Configura AP
        self.ap.config(essid=ssid, password=password, authmode=network.AUTH_WPA_WPA2_PSK)

        # Configura IP statico
        self.ap.ifconfig((ap_ip, '255.255.255.0', ap_ip, ap_ip))

        self.ap_active = True
        print(f"AP started! IP: {ap_ip}")
        return True

    def scan_networks(self):
        """
        Scansiona le reti WiFi disponibili

        Returns:
            Lista di dizionari con info reti [(ssid, rssi, authmode), ...]
        """
        if not self.sta.active():
            self.sta.active(True)
            time.sleep(1)

        print("Scanning networks...")
        networks = self.sta.scan()

        # Formatta risultati
        result = []
        for net in networks:
            ssid = net[0].decode('utf-8')
            rssi = net[3]
            authmode = net[4]
            result.append({
                'ssid': ssid,
                'rssi': rssi,
                'secure': authmode != 0
            })

        # Ordina per segnale
        result.sort(key=lambda x: x['rssi'], reverse=True)

        print(f"Found {len(result)} networks")
        return result

    def test_connection(self, ssid, password):
        """
        Testa una connessione WiFi senza salvarla

        Args:
            ssid: nome rete
            password: password

        Returns:
            True se connessione riuscita, False altrimenti
        """
        print(f"Testing connection to: {ssid}")

        # Salva stato corrente
        was_active = self.sta.active()

        # Attiva e prova a connettersi
        self.sta.active(True)
        time.sleep(1)

        self.sta.connect(ssid, password)

        # Aspetta max 15 secondi
        max_wait = 15
        success = False

        while max_wait > 0:
            if self.sta.isconnected():
                success = True
                print("Test successful!")
                break

            time.sleep(1)
            max_wait -= 1

        # Disconnetti
        if self.sta.isconnected():
            self.sta.disconnect()

        # Ripristina stato
        if not was_active:
            self.sta.active(False)

        return success

    def get_status(self):
        """
        Ottiene lo stato corrente del WiFi

        Returns:
            Dizionario con informazioni sullo stato
        """
        status = {
            'mode': self.config.wifi_mode,
            'sta': {
                'active': self.sta.active(),
                'connected': self.sta.isconnected(),
                'ip': self.sta.ifconfig()[0] if self.sta.isconnected() else None,
                'ssid': None
            },
            'ap': {
                'active': self.ap.active(),
                'ip': self.ap.ifconfig()[0] if self.ap.active() else None,
                'ssid': self.config.get('wifi.ap_credentials.ssid', 'SmartThermo')
            }
        }

        # Ottieni SSID corrente se connesso
        if self.sta.isconnected():
            known = self.config.get('wifi.known', [])
            selected = self.config.get('wifi.selected', 0)
            if known and selected < len(known):
                status['sta']['ssid'] = known[selected].get('ssid')

        return status

    def get_ip(self):
        """
        Ottiene l'IP principale da usare per il server web

        Returns:
            Indirizzo IP o None
        """
        if self.sta.isconnected():
            return self.sta.ifconfig()[0]
        elif self.ap.active():
            return self.ap.ifconfig()[0]
        return None

    def cleanup(self):
        """Libera risorse"""
        gc.collect()
