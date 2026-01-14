"""
Classe condivisa per gestione configurazione
Legge e scrive il file config.json e fornisce accesso ai valori
"""
import json
import gc

class Config:
    """Gestione configurazione del sistema"""

    _instance = None
    _config_file = 'config.json'

    def __new__(cls):
        """Singleton pattern per avere una sola istanza"""
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Inizializza e carica la configurazione"""
        if self._initialized:
            return
        self._data = {}
        self.load()
        self._initialized = True

    def load(self):
        """Carica la configurazione dal file JSON"""
        try:
            with open(self._config_file, 'r') as f:
                self._data = json.load(f)
            print("Config loaded successfully")
        except Exception as e:
            print(f"Error loading config: {e}")
            # Configurazione di default se il file non esiste
            self._data = self._get_default_config()

    def save(self):
        """Salva la configurazione sul file JSON"""
        try:
            with open(self._config_file, 'w') as f:
                json.dump(self._data, f)
            print("Config saved successfully")
            return True
        except Exception as e:
            print(f"Error saving config: {e}")
            return False

    def get(self, path, default=None):
        """
        Ottiene un valore dalla configurazione usando un path separato da punti
        Es: get('wifi.mode') ritorna il valore di _data['wifi']['mode']
        """
        keys = path.split('.')
        value = self._data
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default

    def set(self, path, value):
        """
        Imposta un valore nella configurazione usando un path separato da punti
        Es: set('wifi.mode', 'STA') imposta _data['wifi']['mode'] = 'STA'
        """
        keys = path.split('.')
        data = self._data
        try:
            for key in keys[:-1]:
                if key not in data:
                    data[key] = {}
                data = data[key]
            data[keys[-1]] = value
            return True
        except Exception as e:
            print(f"Error setting config value: {e}")
            return False

    # Accesso diretto ai PIN come costanti
    @property
    def PIN_SDA(self):
        return self.get('pins.PIN_SDA', 5)

    @property
    def PIN_SCL(self):
        return self.get('pins.PIN_SCL', 6)

    @property
    def PIN_LEFT(self):
        return self.get('pins.PIN_LEFT', 3)

    @property
    def PIN_RIGHT(self):
        return self.get('pins.PIN_RIGHT', 4)

    @property
    def PIN_FIRE(self):
        return self.get('pins.PIN_FIRE', 0)

    @property
    def PIN_LASER(self):
        return self.get('pins.PIN_LASER', 9)

    @property
    def PIN_UP(self):
        return self.get('pins.PIN_UP', 10)

    @property
    def PIN_DOWN(self):
        return self.get('pins.PIN_DOWN', 7)

    @property
    def PIN_BUZZER(self):
        return self.get('pins.PIN_BUZZER', 1)

    # Accesso a wifi
    @property
    def wifi_mode(self):
        return self.get('wifi.mode', 'AP')

    @wifi_mode.setter
    def wifi_mode(self, value):
        self.set('wifi.mode', value)

    @property
    def wifi_known(self):
        return self.get('wifi.known', [])

    @property
    def wifi_selected(self):
        return self.get('wifi.selected', 0)

    @wifi_selected.setter
    def wifi_selected(self, value):
        self.set('wifi.selected', value)

    # Accesso a preferences
    @property
    def laser_enabled(self):
        return self.get('preferences.laser', True)

    @laser_enabled.setter
    def laser_enabled(self, value):
        self.set('preferences.laser', value)

    @property
    def bignum_enabled(self):
        return self.get('preferences.bignum', False)

    @bignum_enabled.setter
    def bignum_enabled(self, value):
        self.set('preferences.bignum', value)

    @property
    def reading_mode(self):
        return self.get('preferences.reading', 'OnShoot')

    @reading_mode.setter
    def reading_mode(self, value):
        self.set('preferences.reading', value)

    @property
    def refresh_rate(self):
        return self.get('preferences.refresh', 500)

    @refresh_rate.setter
    def refresh_rate(self, value):
        self.set('preferences.refresh', value)

    # Accesso a thermostat
    @property
    def thermostat_active(self):
        return self.get('thermostat.active', False)

    @thermostat_active.setter
    def thermostat_active(self, value):
        self.set('thermostat.active', value)

    @property
    def thermostat_target(self):
        return self.get('thermostat.target', 50)

    @thermostat_target.setter
    def thermostat_target(self, value):
        self.set('thermostat.target', value)

    @property
    def thermostat_p(self):
        return self.get('thermostat.p', 1.0)

    @thermostat_p.setter
    def thermostat_p(self, value):
        self.set('thermostat.p', value)

    @property
    def thermostat_i(self):
        return self.get('thermostat.i', 0.0)

    @thermostat_i.setter
    def thermostat_i(self, value):
        self.set('thermostat.i', value)

    @property
    def thermostat_d(self):
        return self.get('thermostat.d', 0.0)

    @thermostat_d.setter
    def thermostat_d(self, value):
        self.set('thermostat.d', value)

    # Accesso a tapo
    @property
    def tapo_enabled(self):
        return self.get('tapo.enabled', False)

    @tapo_enabled.setter
    def tapo_enabled(self, value):
        self.set('tapo.enabled', value)

    @property
    def tapo_ip(self):
        return self.get('tapo.ip', '192.168.137.242')

    @tapo_ip.setter
    def tapo_ip(self, value):
        self.set('tapo.ip', value)

    # === Calibration ===

    @property
    def calibration_enabled(self):
        """Abilita/disabilita la calibrazione del sensore"""
        return self.get('calibration.enabled', False)

    @calibration_enabled.setter
    def calibration_enabled(self, value):
        self.set('calibration.enabled', value)

    @property
    def calibration_point1_raw(self):
        """Primo punto di calibrazione - valore letto dal sensore"""
        return self.get('calibration.point1_raw', 36.3)

    @calibration_point1_raw.setter
    def calibration_point1_raw(self, value):
        self.set('calibration.point1_raw', value)

    @property
    def calibration_point1_real(self):
        """Primo punto di calibrazione - valore reale"""
        return self.get('calibration.point1_real', 60.0)

    @calibration_point1_real.setter
    def calibration_point1_real(self, value):
        self.set('calibration.point1_real', value)

    @property
    def calibration_point2_raw(self):
        """Secondo punto di calibrazione - valore letto dal sensore"""
        return self.get('calibration.point2_raw', 58.2)

    @calibration_point2_raw.setter
    def calibration_point2_raw(self, value):
        self.set('calibration.point2_raw', value)

    @property
    def calibration_point2_real(self):
        """Secondo punto di calibrazione - valore reale"""
        return self.get('calibration.point2_real', 100.0)

    @calibration_point2_real.setter
    def calibration_point2_real(self, value):
        self.set('calibration.point2_real', value)

    def _get_default_config(self):
        """Configurazione di default se il file non esiste"""
        return {
            "pins": {
                "PIN_SDA": 5,
                "PIN_SCL": 6,
                "PIN_LEFT": 3,
                "PIN_RIGHT": 4,
                "PIN_FIRE": 0,
                "PIN_LASER": 9,
                "PIN_UP": 10,
                "PIN_DOWN": 7,
                "PIN_BUZZER": 1
            },
            "wifi": {
                "mode": "AP",
                "known": [],
                "selected": 0,
                "ap_ip": "192.168.4.1",
                "ap_credentials": {
                    "ssid": "SmartThermo",
                    "password": "12345678"
                }
            },
            "preferences": {
                "laser": True,
                "bignum": False,
                "reading": "OnShoot",
                "refresh": 500
            },
            "thermostat": {
                "active": False,
                "target": 50,
                "p": 1.0,
                "i": 0.0,
                "d": 0.0
            },
            "tapo": {
                "enabled": False,
                "ip": "192.168.137.242",
                "email": "",
                "password": ""
            },
            "calibration": {
                "enabled": True,
                "point1_raw": 36.3,
                "point1_real": 60.0,
                "point2_raw": 58.2,
                "point2_real": 100.0
            }
        }

    def reload(self):
        """Ricarica la configurazione dal file (utile dopo il passaggio tra app)"""
        self.load()
        gc.collect()
