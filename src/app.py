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
from buzzer import Buzzer


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

        if self.config.bignum_enabled:
            from bignum import BigNum
            self.big = BigNum(self.display)

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
        # Sensore MLX90614 con calibrazione
        try:
            self.sensor = MLX90614(self.i2c, config=self.config)
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
            self.buzzer = Buzzer(self.config.PIN_BUZZER)
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
                    if self.config.reading_mode == self.READING_CONTINUE and self.buzzer and self.object_temp is not None:
                        self.buzzer.note_on(int(self.object_temp*100))
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
                # Entra in setup
                self._enter_setup()

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
        if self.config.bignum_enabled and hasattr(self, 'big'):
            # Modalità BigNum: temperatura grande
            if self.object_temp is not None:
                self.big.printNum(self.object_temp, 0, 15)
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
        graph_height = 38
        graph_y_start = 15

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
                self.buzzer.beep(1000,50,75)
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

    def _enter_setup(self):
        """Entra nell'app di setup"""
        print("Entering setup mode...")

        # Spegni laser e buzzer
        self.laser.value(0)
        #if self.buzzer:
            #self.buzzer.value(0)

        # Ferma web server temporaneamente (mantiene WiFi)
        # Non serve cleanup completo, solo pausa

        # Importa e avvia setup passando callback per autotune
        import sys
        import setup

        # Crea callback per autotune che chiama il metodo dell'app
        autotune_callback = lambda: self.autotune_pid()

        setup.main(self.display, autotune_callback)

        # Cleanup modulo setup
        del sys.modules['setup']
        del setup
        gc.collect()

        # Ricarica configurazione (potrebbe essere stata modificata)
        self.config.reload()

        # Ricarica parametri PID
        self.pid.set_tunings(
            self.config.thermostat_p,
            self.config.thermostat_i,
            self.config.thermostat_d
        )
        self.pid.set_setpoint(self.config.thermostat_target)

        print("Returned from setup mode")

    def autotune_pid(self):
        """
        Auto-tune PID con focus su NON superare mai il target
        Misura l'inerzia termica e calcola parametri conservativi
        """
        if not self.sensor or not self.tapo:
            print("Autotune failed: sensor or Tapo not available")
            return False

        target = self.config.thermostat_target
        print(f"Starting PID autotune for target: {target}C")

        self.display.fill(0)
        self.display.text("PID Auto-tune", 15, 10, 1)
        self.display.text("Phase 1/3", 30, 25, 1)
        self.display.text("Measuring...", 20, 40, 1)
        self.display.show()

        # === FASE 1: Misura inerzia termica ===
        # Riscalda fino a ~70% del target, poi spegni e misura overshoot

        print("Phase 1: Measuring thermal inertia...")

        # Punto di test: 70% del target (o target-20C se target basso)
        test_point = max(target * 0.7, target - 20)

        # Accendi riscaldamento
        self.tapo.turn_on()
        start_temp = self.sensor.read_object_temp()

        # Riscalda fino al test point
        while True:
            temp = self.sensor.read_object_temp()
            if temp is None:
                continue

            self.display.fill(0)
            self.display.text("Heating...", 30, 15, 1)
            self.display.text(f"T: {temp:.1f}C", 30, 30, 1)
            self.display.text(f"-> {test_point:.0f}C", 30, 45, 1)
            self.display.show()

            if temp >= test_point:
                break

            time.sleep(1)

        # Spegni e misura overshoot
        self.tapo.turn_off()
        temp_at_shutoff = self.sensor.read_object_temp()
        time.sleep(2)  # Attendi stabilizzazione lettura

        max_temp = temp_at_shutoff
        overshoot_time = 0

        # Misura per 60 secondi quanto sale ancora
        print("Measuring overshoot...")
        for i in range(60):
            temp = self.sensor.read_object_temp()
            if temp is None:
                continue

            if temp > max_temp:
                max_temp = temp
                overshoot_time = i

            self.display.fill(0)
            self.display.text("Measuring", 30, 15, 1)
            self.display.text(f"Peak: {max_temp:.1f}C", 20, 30, 1)
            self.display.text(f"Time: {i}s", 30, 45, 1)
            self.display.show()

            time.sleep(1)

        overshoot = max_temp - temp_at_shutoff
        print(f"Overshoot: {overshoot:.1f}C in {overshoot_time}s")

        # === FASE 2: Misura cooling rate ===
        print("Phase 2: Measuring cooling rate...")

        self.display.fill(0)
        self.display.text("Phase 2/3", 30, 25, 1)
        self.display.text("Cooling...", 25, 40, 1)
        self.display.show()

        # Aspetta che scenda di almeno 10C
        temp_start_cooling = max_temp
        time_start = time.ticks_ms()

        while True:
            temp = self.sensor.read_object_temp()
            if temp is None:
                continue

            if temp <= temp_start_cooling - 10:
                break

            time.sleep(1)

        time_elapsed = time.ticks_diff(time.ticks_ms(), time_start) / 1000.0
        cooling_rate = 10.0 / time_elapsed  # °C per secondo

        print(f"Cooling rate: {cooling_rate:.3f} C/s")

        # === FASE 3: Calcola parametri PID conservativi ===
        print("Phase 3: Calculating PID parameters...")

        self.display.fill(0)
        self.display.text("Phase 3/3", 30, 25, 1)
        self.display.text("Computing...", 20, 40, 1)
        self.display.show()

        # Calcola margine di sicurezza
        # Dobbiamo spegnere PRIMA del target considerando:
        # 1. L'overshoot misurato
        # 2. Un margine di sicurezza del 50%
        safety_margin = overshoot * 1.5

        # Stima del tempo di risposta del sistema
        # Basato su overshoot_time
        response_time = max(overshoot_time, 5)  # Minimo 5 secondi

        # Calcola parametri PID conservativi
        # Kp: proporzionale - deve essere piccolo per evitare overshoot
        # Più alto l'overshoot, più piccolo deve essere Kp
        kp = 1.0 / (1 + overshoot)  # Range tipico 0.3-0.8

        # Ki: integrale - lento per stabilità
        # Deve integrare lentamente per non causare overshoot
        ki = kp / (response_time * 4)  # Range tipico 0.01-0.05

        # Kd: derivativo - per anticipare e frenare prima del target
        # Importante per fermare PRIMA considerando l'inerzia
        kd = kp * response_time / 2  # Range tipico 0.5-2.0

        print(f"Calculated PID: P={kp:.3f}, I={ki:.4f}, D={kd:.3f}")
        print(f"Safety margin: {safety_margin:.1f}C")

        # Salva parametri
        self.config.set('thermostat.p', kp)
        self.config.set('thermostat.i', ki)
        self.config.set('thermostat.d', kd)
        self.config.save()

        # Aggiorna PID
        self.pid.set_tunings(kp, ki, kd)

        # === FASE 4: Test validazione (opzionale ma consigliato) ===
        print("Phase 4: Validation test...")

        self.display.fill(0)
        self.display.text("Testing PID", 25, 15, 1)
        self.display.text("Target test", 25, 30, 1)
        self.display.show()

        # Reset PID
        self.pid.reset()

        # Aspetta che la temperatura scenda sotto target - 15C
        while True:
            temp = self.sensor.read_object_temp()
            if temp and temp < target - 15:
                break
            time.sleep(2)

        # Test di avvicinamento al target con PID
        test_duration = 300  # 5 minuti max
        max_reached = 0
        target_reached = False

        for i in range(test_duration):
            temp = self.sensor.read_object_temp()
            if temp is None:
                continue

            # Aggiorna PID
            output = self.pid.update(temp)

            # Controllo conservativo: spegni se vicino al target
            if temp >= target - safety_margin:
                self.tapo.turn_off()
            elif output > 50:
                self.tapo.turn_on()
            else:
                self.tapo.turn_off()

            if temp > max_reached:
                max_reached = temp

            if abs(temp - target) < 1.0:
                target_reached = True

            self.display.fill(0)
            self.display.text("Testing...", 30, 10, 1)
            self.display.text(f"T: {temp:.1f}C", 25, 25, 1)
            self.display.text(f"Tgt: {target}C", 25, 40, 1)
            self.display.text(f"Max: {max_reached:.1f}C", 15, 55, 1)
            self.display.show()

            # Se raggiunto target e stabile per 30s, esci
            if target_reached and i > 30:
                if abs(temp - target) < 1.0:
                    break

            time.sleep(1)

        # Spegni
        self.tapo.turn_off()

        # Valuta risultato
        success = max_reached <= target + 1.0  # Tolleranza 1C

        self.display.fill(0)
        if success:
            self.display.text("SUCCESS!", 30, 15, 1)
            self.display.text(f"Max: {max_reached:.1f}C", 20, 30, 1)
            self.display.text(f"P={kp:.2f} I={ki:.3f}", 10, 45, 1)
            print("Autotune completed successfully!")
        else:
            self.display.text("WARNING!", 30, 15, 1)
            self.display.text(f"Overshoot!", 25, 30, 1)
            self.display.text(f"{max_reached:.1f}>{target}C", 20, 45, 1)
            print(f"Autotune warning: reached {max_reached:.1f}C")

        self.display.show()
        time.sleep(5)

        return success

    def cleanup(self):
        """Libera risorse"""
        print("Cleaning up ThermoApp...")

        self.running = False

        # Spegni laser
        if self.laser:
            self.laser.value(0)

        # Spegni buzzer
        #if self.buzzer:
            #self.buzzer.value(0)

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
