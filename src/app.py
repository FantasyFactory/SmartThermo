"""
App principale SmartThermo
Gestisce display, sensore, WiFi, web server e modalità termostato
"""
import gc
import time
from machine import Pin
from drivers.mlx90614 import MLX90614
from wifi_manager import WiFiManager
from web_server import WebServer
from config import Config


class ThermoApp:
    """Applicazione principale del termometro"""

    # Modalità di lettura
    MODE_ONSHOOT = "OnShoot"
    MODE_CONTINUE = "Continue"

    def __init__(self, display, i2c):
        """
        Inizializza l'applicazione

        Args:
            display: istanza del display OLED
            i2c: istanza I2C
        """
        self.display = display
        self.i2c = i2c
        self.config = Config()

        # Stato applicazione
        self.app_state = {
            'object_temp': None,
            'ambient_temp': None,
            'last_reading': 0
        }

        # Inizializza hardware
        self._init_hardware()

        # Inizializza WiFi
        self.wifi_manager = WiFiManager(self.config)

        # Inizializza web server
        self.web_server = WebServer(self.wifi_manager, self.config, self.sensor, self.app_state)

        self.running = False

    def _init_hardware(self):
        """Inizializza hardware (sensore, pulsanti, laser)"""
        # Sensore MLX90614
        try:
            self.sensor = MLX90614(self.i2c)
            print("Sensor initialized")
        except Exception as e:
            print(f"Error initializing sensor: {e}")
            self.sensor = None

        # Pulsanti
        self.btn_fire = Pin(self.config.PIN_FIRE, Pin.IN, Pin.PULL_UP)
        self.btn_up = Pin(self.config.PIN_UP, Pin.IN, Pin.PULL_UP)
        self.btn_down = Pin(self.config.PIN_DOWN, Pin.IN, Pin.PULL_UP)

        # Laser
        self.laser = Pin(self.config.PIN_LASER, Pin.OUT)
        self.laser.value(0)

        # Buzzer (opzionale)
        try:
            self.buzzer = Pin(self.config.PIN_BUZZER, Pin.OUT)
            self.buzzer.value(0)
        except:
            self.buzzer = None

        # Debouncing
        self.last_btn_time = 0
        self.debounce_ms = 200

    def start(self):
        """Avvia l'applicazione"""
        print("Starting ThermoApp...")

        # Mostra splash
        self._show_splash()

        # Avvia WiFi
        self.wifi_manager.start()

        # Avvia web server se WiFi attivo
        if self.wifi_manager.get_ip():
            self.web_server.start()

        # Mostra IP sul display
        self._show_ip()

        # Avvia loop principale
        self.running = True
        self.run()

    def run(self):
        """Loop principale dell'applicazione"""
        last_display_update = 0
        display_update_interval = self.config.refresh_rate  # ms

        while self.running:
            try:
                # Gestisci richieste web server
                self.web_server.handle_requests(timeout_ms=10)

                # Leggi temperature in base alla modalità
                reading_mode = self.config.reading_mode

                if reading_mode == self.MODE_CONTINUE:
                    # Modalità continua: leggi sempre
                    current_time = time.ticks_ms()
                    if time.ticks_diff(current_time, last_display_update) >= display_update_interval:
                        self._read_and_display()
                        last_display_update = current_time

                elif reading_mode == self.MODE_ONSHOOT:
                    # Modalità on-shoot: leggi solo quando premuto FIRE
                    if self._read_button(self.btn_fire):
                        self._read_and_display()
                        self._beep()

                # Controlla laser
                self._update_laser()

                # Gestisci termostato (se attivo)
                if self.config.thermostat_active:
                    self._handle_thermostat()

                # Piccola pausa per non saturare CPU
                time.sleep_ms(10)

                gc.collect()

            except KeyboardInterrupt:
                print("Interrupted by user")
                break
            except Exception as e:
                print(f"Error in main loop: {e}")
                import sys
                sys.print_exception(e)
                time.sleep(1)

        # Cleanup
        self.cleanup()

    def _read_and_display(self):
        """Legge le temperature e aggiorna il display"""
        if not self.sensor:
            return

        obj_temp, amb_temp = self.sensor.read_both()

        # Aggiorna stato
        self.app_state['object_temp'] = obj_temp
        self.app_state['ambient_temp'] = amb_temp
        self.app_state['last_reading'] = time.ticks_ms()

        # Visualizza su display
        self._display_temperatures(obj_temp, amb_temp)

    def _display_temperatures(self, obj_temp, amb_temp):
        """Mostra le temperature sul display"""
        self.display.fill(0)

        if self.config.bignum_enabled:
            # Modalità big number: mostra solo temperatura oggetto grande
            if obj_temp is not None:
                temp_str = f"{obj_temp:.1f}"
                # Centra il testo (font 8x8, max 21 char per riga)
                x = max(0, (128 - len(temp_str) * 16) // 2)
                self.display.text(temp_str, x, 20, 1)
                self.display.text("C", x + len(temp_str) * 8, 20, 1)

            # Mostra temperatura ambiente piccola
            if amb_temp is not None:
                self.display.text(f"Amb: {amb_temp:.1f}C", 0, 55, 1)
        else:
            # Modalità normale
            self.display.text("SmartThermo", 20, 0, 1)

            # Temperatura oggetto
            if obj_temp is not None:
                self.display.text(f"Object: {obj_temp:.1f} C", 5, 20, 1)
            else:
                self.display.text("Object: --.- C", 5, 20, 1)

            # Temperatura ambiente
            if amb_temp is not None:
                self.display.text(f"Ambient: {amb_temp:.1f} C", 5, 35, 1)
            else:
                self.display.text("Ambient: --.- C", 5, 35, 1)

            # Indicatore termostato
            if self.config.thermostat_active:
                target = self.config.thermostat_target
                self.display.text(f"Target: {target} C", 5, 50, 1)

        self.display.show()

    def _show_splash(self):
        """Mostra schermata iniziale"""
        self.display.fill(0)
        self.display.text("SmartThermo", 20, 15, 1)
        self.display.text("Starting...", 25, 35, 1)
        self.display.show()
        time.sleep(1)

    def _show_ip(self):
        """Mostra IP sul display"""
        ip = self.wifi_manager.get_ip()
        if ip:
            self.display.fill(0)
            self.display.text("Web Server", 25, 10, 1)
            self.display.text("Ready!", 40, 25, 1)
            self.display.text(ip, 10, 45, 1)
            self.display.show()
            time.sleep(3)

    def _update_laser(self):
        """Aggiorna stato del laser"""
        if self.config.laser_enabled:
            # Laser on quando in lettura continua o quando premuto FIRE
            if self.config.reading_mode == self.MODE_CONTINUE:
                self.laser.value(1)
            else:
                self.laser.value(1 if self.btn_fire.value() == 0 else 0)
        else:
            self.laser.value(0)

    def _handle_thermostat(self):
        """Gestisce la logica del termostato (placeholder per PID)"""
        # TODO: Implementare controllo PID
        # Per ora solo un esempio base
        obj_temp = self.app_state.get('object_temp')
        target = self.config.thermostat_target

        if obj_temp is not None:
            # Logica semplice on/off (da sostituire con PID)
            if obj_temp < target:
                # Accendi riscaldamento (es. via Tapo)
                pass
            else:
                # Spegni riscaldamento
                pass

    def _beep(self):
        """Emette un beep breve"""
        if self.buzzer:
            try:
                self.buzzer.value(1)
                time.sleep_ms(50)
                self.buzzer.value(0)
            except:
                pass

    def _read_button(self, btn):
        """Legge un pulsante con debouncing"""
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_btn_time) < self.debounce_ms:
            return False

        if btn.value() == 0:  # Premuto (pull-up)
            self.last_btn_time = now
            return True
        return False

    def cleanup(self):
        """Libera risorse"""
        print("Cleaning up ThermoApp...")

        self.running = False

        # Spegni laser
        if self.laser:
            self.laser.value(0)

        # Spegni buzzer
        if self.buzzer:
            self.buzzer.value(0)

        # Ferma web server
        if self.web_server:
            self.web_server.cleanup()

        # Cleanup WiFi
        if self.wifi_manager:
            self.wifi_manager.cleanup()

        gc.collect()
        print("ThermoApp cleaned up")


def main(display, i2c):
    """Entry point per l'app principale"""
    app = ThermoApp(display, i2c)
    app.start()
    del app
    gc.collect()
