"""
App principale SmartThermo
Gestisce display, sensore, WiFi, web server e tre modalità operative
"""
import gc
import time
from machine import Pin
from drivers.mlx90614 import MLX90614
from wifi_manager import WiFiManager
from web_server import WebServer
from config import Config
from pid_controller import PIDController


class ThermoApp:
    """Applicazione principale del termometro"""

    # Modalità operative
    MODE_READING = 0
    MODE_THERMOSTAT = 1
    MODE_GRAPH = 2
    MODE_NAMES = ["Reading", "Thermostat", "Graph"]

    # Modalità di lettura
    READING_ONSHOOT = "OnShoot"
    READING_CONTINUE = "Continue"

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
        self.current_mode = self.MODE_READING
        self.running = False

        # Stato temperature
        self.object_temp = None
        self.ambient_temp = None
        self.last_reading_time = 0

        # Stato termostato
        self.editing_target = False  # Flag per editing target in modalità thermostat

        # Storico per grafico (ultimi 128 punti = larghezza display)
        self.temp_history = []
        self.max_history = 128

        # Inizializza hardware
        self._init_hardware()

        # Inizializza WiFi
        self.wifi_manager = WiFiManager(self.config)

        # Inizializza web server
        self.app_state = {
            'object_temp': None,
            'ambient_temp': None,
            'last_reading': 0
        }
        self.web_server = WebServer(self.wifi_manager, self.config, self.sensor, self.app_state)

        # Inizializza PID per termostato
        self.pid = PIDController(
            self.config.thermostat_p,
            self.config.thermostat_i,
            self.config.thermostat_d,
            self.config.thermostat_target
        )

        # Tapo controller (lazy init)
        self.tapo = None

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
        self.btn_left = Pin(self.config.PIN_LEFT, Pin.IN, Pin.PULL_UP)
        self.btn_right = Pin(self.config.PIN_RIGHT, Pin.IN, Pin.PULL_UP)

        # Laser
        self.laser = Pin(self.config.PIN_LASER, Pin.OUT)
        self.laser.value(0)

        # Buzzer
        try:
            self.buzzer = Pin(self.config.PIN_BUZZER, Pin.OUT)
            self.buzzer.value(0)
        except:
            self.buzzer = None

        # Debouncing
        self.last_btn_time = 0
        self.debounce_ms = 200

    def _init_tapo(self):
        """Inizializza controller Tapo se abilitato"""
        if not self.config.tapo_enabled:
            return None

        try:
            from tapo_control import TapoP100
            tapo_ip = self.config.get('tapo.ip')
            tapo_email = self.config.get('tapo.email', '')
            tapo_password = self.config.get('tapo.password', '')

            return TapoP100(tapo_ip, tapo_email, tapo_password)
        except Exception as e:
            print(f"Error initializing Tapo: {e}")
            return None

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
            time.sleep(2)  # Mostra IP per 2 secondi

        # Inizializza Tapo se necessario
        if self.current_mode == self.MODE_THERMOSTAT and self.config.tapo_enabled:
            self.tapo = self._init_tapo()

        # Avvia loop principale
        self.running = True
        self.run()

    def run(self):
        """Loop principale dell'applicazione"""
        last_display_update = 0
        last_web_update = 0

        while self.running:
            try:
                current_time = time.ticks_ms()

                # Gestisci richieste web server (non blocca)
                self.web_server.handle_requests(timeout_ms=5)

                # Gestisci input pulsanti
                self._handle_input()

                # Aggiorna letture se necessario
                if self._should_update_reading(current_time):
                    self._read_temperatures()
                    last_display_update = current_time

                # Aggiorna display
                if time.ticks_diff(current_time, last_display_update) >= 100:
                    self._update_display()
                    last_display_update = current_time

                # Aggiorna web state periodicamente
                if time.ticks_diff(current_time, last_web_update) >= 1000:
                    self._update_web_state()
                    last_web_update = current_time

                # Gestisci termostato se attivo
                if self.current_mode == self.MODE_THERMOSTAT and self.config.thermostat_active:
                    self._handle_thermostat()

                # Gestisci laser
                self._update_laser()

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

        self.cleanup()

    def _should_update_reading(self, current_time):
        """Determina se aggiornare la lettura"""
        reading_mode = self.config.reading_mode

        if reading_mode == self.READING_CONTINUE:
            # Lettura continua con refresh rate
            refresh = self.config.refresh_rate
            return time.ticks_diff(current_time, self.last_reading_time) >= refresh

        # OnShoot: lettura solo quando richiesto (gestito da _handle_input)
        return False

    def _handle_input(self):
        """Gestisce input dai pulsanti"""
        # UP: cambia modalità o incrementa valore
        if self._read_button(self.btn_up):
            if self.editing_target:
                # Incrementa target temperature
                target = self.config.thermostat_target + 1
                target = min(target, 150)
                self.config.set('thermostat.target', target)
                self.pid.set_setpoint(target)
            else:
                # Cambia modalità
                self.current_mode = (self.current_mode - 1) % 3
                self._on_mode_change()

        # DOWN: cambia modalità o decrementa valore
        elif self._read_button(self.btn_down):
            if self.editing_target:
                # Decrementa target temperature
                target = self.config.thermostat_target - 1
                target = max(target, 0)
                self.config.set('thermostat.target', target)
                self.pid.set_setpoint(target)
            else:
                # Cambia modalità
                self.current_mode = (self.current_mode + 1) % 3
                self._on_mode_change()

        # LEFT: in modalità Thermostat entra in editing target
        elif self._read_button(self.btn_left):
            if self.current_mode == self.MODE_THERMOSTAT:
                self.editing_target = True

        # RIGHT: conferma editing o entra in setup
        elif self._read_button(self.btn_right):
            if self.editing_target:
                # Conferma e salva
                self.config.save()
                self.editing_target = False
                self._beep()
            else:
                # Entra in setup (TODO: implementare)
                pass

        # FIRE: lettura in modalità OnShoot
        elif self._read_button(self.btn_fire):
            if self.config.reading_mode == self.READING_ONSHOOT:
                self._read_temperatures()
                self._beep()

    def _on_mode_change(self):
        """Callback quando cambia modalità"""
        # Reset editing
        self.editing_target = False

        # Inizializza Tapo se si entra in modalità Thermostat
        if self.current_mode == self.MODE_THERMOSTAT and self.config.tapo_enabled:
            if not self.tapo:
                self.tapo = self._init_tapo()

    def _read_temperatures(self):
        """Legge le temperature dal sensore"""
        if not self.sensor:
            return

        obj_temp, amb_temp = self.sensor.read_both()

        self.object_temp = obj_temp
        self.ambient_temp = amb_temp
        self.last_reading_time = time.ticks_ms()

        # Aggiorna storico per grafico
        if obj_temp is not None:
            self.temp_history.append(obj_temp)
            if len(self.temp_history) > self.max_history:
                self.temp_history.pop(0)

    def _update_web_state(self):
        """Aggiorna stato per web server"""
        self.app_state['object_temp'] = self.object_temp
        self.app_state['ambient_temp'] = self.ambient_temp
        self.app_state['last_reading'] = self.last_reading_time

    def _update_display(self):
        """Aggiorna il display in base alla modalità corrente"""
        self.display.fill(0)

        # Header (top 10px)
        self._draw_header()

        # Contenuto modalità (centrale 44px: da y=10 a y=54)
        if self.current_mode == self.MODE_READING:
            self._draw_reading_mode()
        elif self.current_mode == self.MODE_THERMOSTAT:
            self._draw_thermostat_mode()
        elif self.current_mode == self.MODE_GRAPH:
            self._draw_graph_mode()

        # Footer (bottom 10px: da y=54 a y=64)
        self._draw_footer()

        self.display.show()

    def _draw_header(self):
        """Disegna header con info WiFi"""
        # Ottieni info WiFi
        wifi_status = self.wifi_manager.get_status()

        if wifi_status['sta']['connected']:
            # Connesso come STA
            ssid = wifi_status['sta']['ssid'] or '?'
            text = f"STA:{ssid[:10]}"
        elif wifi_status['ap']['active']:
            # Modalità AP
            ssid = wifi_status['ap']['ssid']
            text = f"AP:{ssid[:11]}"
        else:
            # Nessuna connessione
            text = "WiFi:Off"

        self.display.text(text, 0, 0, 1)

    def _draw_footer(self):
        """Disegna footer con menu"""
        mode_name = self.MODE_NAMES[self.current_mode]

        if self.editing_target:
            # Mostra che si sta editando
            text = f"{mode_name} *EDIT*"
        else:
            text = f"{mode_name} Set>"

        self.display.text(text, 0, 56, 1)

    def _draw_reading_mode(self):
        """Disegna modalità Reading"""
        if self.config.bignum_enabled:
            # Modalità BigNum: temperatura grande
            if self.object_temp is not None:
                temp_str = f"{self.object_temp:.1f}C"
                # Centra il testo (approssimativo)
                x = max(0, (128 - len(temp_str) * 8) // 2)
                y = 26  # Centro area (10 + 44/2 - 4)
                self.display.text(temp_str, x, y, 1)
            else:
                self.display.text("--.-C", 40, 26, 1)
        else:
            # Modalità normale: 2 righe
            y_obj = 20
            y_amb = 36

            if self.object_temp is not None:
                self.display.text(f"Obj: {self.object_temp:.1f}C", 10, y_obj, 1)
            else:
                self.display.text("Obj: --.-C", 10, y_obj, 1)

            if self.ambient_temp is not None:
                self.display.text(f"Amb: {self.ambient_temp:.1f}C", 10, y_amb, 1)
            else:
                self.display.text("Amb: --.-C", 10, y_amb, 1)

    def _draw_thermostat_mode(self):
        """Disegna modalità Thermostat"""
        target = self.config.thermostat_target
        active = self.config.thermostat_active

        # Riga 1: temperatura corrente
        y1 = 18
        if self.object_temp is not None:
            self.display.text(f"Temp: {self.object_temp:.1f}C", 5, y1, 1)
        else:
            self.display.text("Temp: --.-C", 5, y1, 1)

        # Riga 2: target (evidenziato se in editing)
        y2 = 32
        if self.editing_target:
            self.display.text(f">Tgt: {target}C<", 5, y2, 1)
        else:
            self.display.text(f"Target: {target}C", 5, y2, 1)

        # Riga 3: stato
        y3 = 46
        if active:
            # Mostra output PID
            if self.object_temp is not None:
                output = self.pid.update(self.object_temp)
                state = "ON" if output > 50 else "OFF"
                self.display.text(f"PID:{output:.0f}% {state}", 5, y3, 1)
            else:
                self.display.text("PID: Wait...", 5, y3, 1)
        else:
            self.display.text("Status: OFF", 5, y3, 1)

    def _draw_graph_mode(self):
        """Disegna modalità Graph"""
        if not self.temp_history:
            self.display.text("No data", 40, 30, 1)
            return

        # Area grafico: y da 10 a 54 (44 pixel altezza)
        graph_height = 44
        graph_y_start = 10

        # Trova min/max per scalare
        min_temp = min(self.temp_history)
        max_temp = max(self.temp_history)
        temp_range = max_temp - min_temp if max_temp > min_temp else 1

        # Disegna grafico
        for i in range(1, len(self.temp_history)):
            x1 = i - 1
            x2 = i

            # Scala temperature in pixel (inverti Y perché 0 è in alto)
            y1 = graph_y_start + graph_height - int(((self.temp_history[i-1] - min_temp) / temp_range) * graph_height)
            y2 = graph_y_start + graph_height - int(((self.temp_history[i] - min_temp) / temp_range) * graph_height)

            # Limita y
            y1 = max(graph_y_start, min(y1, graph_y_start + graph_height - 1))
            y2 = max(graph_y_start, min(y2, graph_y_start + graph_height - 1))

            # Disegna linea
            self.display.line(x1, y1, x2, y2, 1)

        # Mostra scala
        self.display.text(f"{max_temp:.0f}", 0, 10, 1)
        self.display.text(f"{min_temp:.0f}", 0, 48, 1)

    def _handle_thermostat(self):
        """Gestisce logica termostato con PID"""
        if not self.object_temp or not self.tapo:
            return

        # Aggiorna PID
        output = self.pid.update(self.object_temp)

        # Controllo on/off semplice basato su output PID
        # Se output > 50% accendi, altrimenti spegni
        try:
            if output > 50:
                if not self.tapo.is_on:
                    self.tapo.turn_on()
            else:
                if self.tapo.is_on:
                    self.tapo.turn_off()
        except Exception as e:
            print(f"Error controlling Tapo: {e}")

    def _update_laser(self):
        """Aggiorna stato laser"""
        if not self.config.laser_enabled:
            self.laser.value(0)
            return

        # Laser on in modalità Continue
        if self.config.reading_mode == self.READING_CONTINUE:
            self.laser.value(1)
        else:
            # Laser on quando FIRE premuto in OnShoot
            self.laser.value(1 if self.btn_fire.value() == 0 else 0)

    def _show_splash(self):
        """Mostra schermata iniziale"""
        self.display.fill(0)
        self.display.text("SmartThermo", 20, 15, 1)
        self.display.text("v2.0", 50, 30, 1)

        # Mostra IP se disponibile
        ip = self.wifi_manager.get_ip()
        if ip:
            self.display.text(ip, 10, 45, 1)

        self.display.show()
        time.sleep(2)

    def _beep(self):
        """Emette beep breve"""
        if self.buzzer:
            try:
                self.buzzer.value(1)
                time.sleep_ms(50)
                self.buzzer.value(0)
            except:
                pass

    def _read_button(self, btn):
        """Legge pulsante con debouncing"""
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
