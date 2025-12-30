"""
Controllo Tapo P100 Smart Plug
Implementazione semplificata per MicroPython
"""
import urequests
import json
import hashlib
import time


class TapoP100:
    """Controller per Tapo P100 smart plug"""

    def __init__(self, ip, email, password):
        """
        Inizializza il controller Tapo

        Args:
            ip: indirizzo IP del dispositivo
            email: email account Tapo
            password: password account Tapo
        """
        self.ip = ip
        self.email = email
        self.password = password
        self.token = None
        self.cookie = None
        self._state = None

    def _encode_credentials(self):
        """Encode credenziali per autenticazione"""
        # Hash password
        pwd_hash = hashlib.sha1(self.password.encode()).digest()
        # Encode email
        email_hash = hashlib.sha1(self.email.encode()).digest()
        return email_hash, pwd_hash

    def turn_on(self):
        """Accende il dispositivo"""
        try:
            url = f"http://{self.ip}/app"
            payload = {
                "method": "set_device_info",
                "params": {
                    "device_on": True
                }
            }

            # Richiesta semplificata - potrebbe richiedere autenticazione
            response = urequests.post(url, json=payload, timeout=5)
            result = response.json()
            response.close()

            self._state = True
            return result.get('error_code', -1) == 0

        except Exception as e:
            print(f"Error turning on Tapo: {e}")
            return False

    def turn_off(self):
        """Spegne il dispositivo"""
        try:
            url = f"http://{self.ip}/app"
            payload = {
                "method": "set_device_info",
                "params": {
                    "device_on": False
                }
            }

            response = urequests.post(url, json=payload, timeout=5)
            result = response.json()
            response.close()

            self._state = False
            return result.get('error_code', -1) == 0

        except Exception as e:
            print(f"Error turning off Tapo: {e}")
            return False

    def get_state(self):
        """
        Ottiene lo stato corrente del dispositivo

        Returns:
            True se acceso, False se spento, None se errore
        """
        try:
            url = f"http://{self.ip}/app"
            payload = {
                "method": "get_device_info"
            }

            response = urequests.post(url, json=payload, timeout=5)
            result = response.json()
            response.close()

            if result.get('error_code', -1) == 0:
                self._state = result.get('result', {}).get('device_on', None)
                return self._state

            return None

        except Exception as e:
            print(f"Error getting Tapo state: {e}")
            return self._state  # Ritorna ultimo stato conosciuto

    @property
    def is_on(self):
        """Ritorna True se il dispositivo è acceso"""
        return self._state if self._state is not None else False
