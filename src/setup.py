"""
App Setup - Interfaccia di configurazione per SmartThermo
Crea un menu navigabile per modificare tutte le impostazioni
"""
import gc
from menu import Menu, MenuItem
from config import Config


class SetupApp:
    """Applicazione di setup/configurazione"""

    def __init__(self, display, i2c=None, autotune_callback=None):
        """
        Inizializza l'app di setup

        Args:
            display: istanza del display OLED già inizializzato
            i2c: istanza I2C per sensore (opzionale, per calibrazione)
            autotune_callback: callback per auto-tune PID (opzionale)
        """
        self.display = display
        self.i2c = i2c
        self.config = Config()
        self.menu = None
        self.exit_requested = False
        self.autotune_callback = autotune_callback

    def _build_menu_tree(self):
        """Costruisce l'albero del menu di setup"""

        # === WIFI MENU ===
        wifi_items = [
            MenuItem(
                MenuItem.TYPE_LIST,
                "Mode",
                choices=["Off", "AP", "STA", "BOTH"],
                get_value=lambda: self.config.wifi_mode,
                set_value=lambda v: self.config.set('wifi.mode', v)
            ),
            MenuItem(
                MenuItem.TYPE_LIST,
                "SSID",
                choices=self._get_known_ssids(),
                get_value=lambda: self._get_selected_ssid(),
                set_value=lambda v: self._set_selected_ssid(v)
            ),
        ]

        # === PREFERENCES MENU ===
        preferences_items = [
            MenuItem(
                MenuItem.TYPE_BOOL,
                "Laser",
                get_value=lambda: self.config.laser_enabled,
                set_value=lambda v: self.config.set('preferences.laser', v)
            ),
            MenuItem(
                MenuItem.TYPE_BOOL,
                "BigNum",
                get_value=lambda: self.config.bignum_enabled,
                set_value=lambda v: self.config.set('preferences.bignum', v)
            ),
            MenuItem(
                MenuItem.TYPE_LIST,
                "Reading",
                choices=["OnShoot", "Continue"],
                get_value=lambda: self.config.reading_mode,
                set_value=lambda v: self.config.set('preferences.reading', v)
            ),
            MenuItem(
                MenuItem.TYPE_INT,
                "Refresh",
                min_val=50,
                max_val=1000,
                step=50,
                get_value=lambda: self.config.refresh_rate,
                set_value=lambda v: self.config.set('preferences.refresh', v)
            ),
        ]

        # === THERMOSTAT MENU ===
        thermostat_items = [
            MenuItem(
                MenuItem.TYPE_BOOL,
                "Active",
                get_value=lambda: self.config.thermostat_active,
                set_value=lambda v: self.config.set('thermostat.active', v)
            ),
            MenuItem(
                MenuItem.TYPE_INT,
                "Target",
                min_val=0,
                max_val=150,
                step=1,
                get_value=lambda: self.config.thermostat_target,
                set_value=lambda v: self.config.set('thermostat.target', v)
            ),
            MenuItem(
                MenuItem.TYPE_FLOAT,
                "P",
                min_val=0.0,
                max_val=10.0,
                step=0.1,
                get_value=lambda: self.config.thermostat_p,
                set_value=lambda v: self.config.set('thermostat.p', v)
            ),
            MenuItem(
                MenuItem.TYPE_FLOAT,
                "I",
                min_val=0.0,
                max_val=10.0,
                step=0.1,
                get_value=lambda: self.config.thermostat_i,
                set_value=lambda v: self.config.set('thermostat.i', v)
            ),
            MenuItem(
                MenuItem.TYPE_FLOAT,
                "D",
                min_val=0.0,
                max_val=10.0,
                step=0.1,
                get_value=lambda: self.config.thermostat_d,
                set_value=lambda v: self.config.set('thermostat.d', v)
            ),
            MenuItem(
                MenuItem.TYPE_ACTION,
                "Auto tune PID",
                action=lambda: self._autotune_pid()
            ),
        ]

        # === TAPO MENU ===
        tapo_items = [
            MenuItem(
                MenuItem.TYPE_BOOL,
                "Enable",
                get_value=lambda: self.config.tapo_enabled,
                set_value=lambda v: self.config.set('tapo.enabled', v)
            ),
            MenuItem(
                MenuItem.TYPE_IP,
                "IP",
                get_value=lambda: self.config.tapo_ip,
                set_value=lambda v: self.config.set('tapo.ip', v)
            ),
        ]

        # === ROOT MENU ===
        root_items = [
            MenuItem(MenuItem.TYPE_LEVEL, "Wifi", items=wifi_items),
            MenuItem(MenuItem.TYPE_LEVEL, "Preferences", items=preferences_items),
            MenuItem(MenuItem.TYPE_LEVEL, "Thermostat", items=thermostat_items),
            MenuItem(MenuItem.TYPE_LEVEL, "Tapo", items=tapo_items),
            MenuItem(
                MenuItem.TYPE_ACTION,
                "Calibration",
                action=lambda: self._calibration_menu()
            ),
            MenuItem(MenuItem.TYPE_LABEL, "---"),
            MenuItem(
                MenuItem.TYPE_ACTION,
                "Save and Exit",
                action=lambda: self._save_and_exit()
            ),
            MenuItem(
                MenuItem.TYPE_ACTION,
                "Exit",
                action=lambda: self._exit_without_save()
            ),
        ]

        return root_items

    def _get_known_ssids(self):
        """Ottiene la lista degli SSID noti"""
        known = self.config.wifi_known
        return [net['ssid'] for net in known] if known else ["None"]

    def _get_selected_ssid(self):
        """Ottiene l'SSID selezionato correntemente"""
        selected = self.config.wifi_selected
        known = self.config.wifi_known
        if known and 0 <= selected < len(known):
            return known[selected]['ssid']
        return "None"

    def _set_selected_ssid(self, ssid):
        """Imposta l'SSID selezionato"""
        known = self.config.wifi_known
        for i, net in enumerate(known):
            if net['ssid'] == ssid:
                self.config.set('wifi.selected', i)
                break

    def _autotune_pid(self):
        """Esegue auto-tuning PID chiamando il callback dell'app principale"""
        if self.autotune_callback:
            # Chiama la funzione di autotune dell'app principale
            self.autotune_callback()
        else:
            # Fallback se callback non disponibile
            self.display.fill(0)
            self.display.text("Auto-tune PID", 0, 0, 1)
            self.display.text("Not available", 0, 12, 1)
            self.display.text("in setup mode", 0, 24, 1)
            self.display.show()
            import time
            time.sleep(2)

    def _calibration_menu(self):
        """Menu interattivo per calibrazione sensore"""
        from machine import Pin
        import time

        # Controlla se i2c è disponibile
        if not self.i2c:
            self.display.fill(0)
            self.display.text("I2C not", 0, 0, 1)
            self.display.text("available", 0, 12, 1)
            self.display.show()
            time.sleep(2)
            return

        # Inizializza sensore temporaneamente
        from drivers.mlx90614 import MLX90614
        try:
            sensor = MLX90614(self.i2c, config=self.config)
        except Exception as e:
            self.display.fill(0)
            self.display.text("Sensor error", 0, 0, 1)
            self.display.text(str(e)[:16], 0, 12, 1)
            self.display.show()
            time.sleep(2)
            return

        # Init pulsanti
        btn_up = Pin(self.config.PIN_UP, Pin.IN, Pin.PULL_UP)
        btn_down = Pin(self.config.PIN_DOWN, Pin.IN, Pin.PULL_UP)
        btn_left = Pin(self.config.PIN_LEFT, Pin.IN, Pin.PULL_UP)
        btn_right = Pin(self.config.PIN_RIGHT, Pin.IN, Pin.PULL_UP)
        btn_fire = Pin(self.config.PIN_FIRE, Pin.IN, Pin.PULL_UP)

        # Stato calibrazione - carica valori correnti
        cal_points = [
            {'raw': self.config.calibration_point1_raw, 'real': self.config.calibration_point1_real},
            {'raw': self.config.calibration_point2_raw, 'real': self.config.calibration_point2_real},
        ]

        selected_row = 0  # 0-1 per punti calibrazione, 2 per Update
        editing = False
        edit_value = 0
        last_button_time = 0
        debounce = 200  # ms

        def read_button(btn):
            nonlocal last_button_time
            if btn.value() == 0:
                now = time.ticks_ms()
                if time.ticks_diff(now, last_button_time) > debounce:
                    last_button_time = now
                    return True
            return False

        def draw_screen():
            self.display.fill(0)

            # Header
            self.display.text("RAW   -  Real", 0, 0, 1)

            # Punti di calibrazione
            for i, point in enumerate(cal_points):
                y = 12 + i * 12
                cursor = ">" if selected_row == i else " "
                if editing and selected_row == i:
                    # Evidenzia valore in edit
                    text = f"{cursor}{point['raw']:5.1f} >[{edit_value:5.1f}]"
                else:
                    text = f"{cursor}{point['raw']:5.1f}  {point['real']:6.1f}"
                self.display.text(text[:16], 0, y, 1)

            # Riga Update
            y = 12 + len(cal_points) * 12
            cursor = ">" if selected_row == len(cal_points) else " "
            self.display.text(f"{cursor}Update", 0, y, 1)

            # Footer hint
            if editing:
                self.display.text("UP/DN:chg R:ok", 0, 56, 1)
            else:
                self.display.text("F:read L:edit", 0, 56, 1)

            self.display.show()

        # Loop principale menu calibrazione
        running = True
        while running:
            draw_screen()

            if editing:
                # Modalità editing valore Real
                if read_button(btn_up):
                    edit_value += 1
                    edit_value = min(edit_value, 500)
                elif read_button(btn_down):
                    edit_value -= 1
                    edit_value = max(edit_value, 0)
                elif read_button(btn_right):
                    # Conferma edit
                    cal_points[selected_row]['real'] = edit_value
                    editing = False

            else:
                # Modalità selezione riga
                if read_button(btn_up):
                    selected_row = (selected_row - 1) % (len(cal_points) + 1)
                elif read_button(btn_down):
                    selected_row = (selected_row + 1) % (len(cal_points) + 1)
                elif read_button(btn_fire):
                    # Leggi temperatura e scrivi in RAW
                    if selected_row < len(cal_points):
                        temp_raw = sensor.read_object_temp_raw()
                        if temp_raw is not None:
                            cal_points[selected_row]['raw'] = temp_raw
                elif read_button(btn_left):
                    if selected_row < len(cal_points):
                        # Entra in edit mode
                        edit_value = cal_points[selected_row]['real']
                        editing = True
                    else:
                        # Esci dal menu
                        running = False
                elif read_button(btn_right):
                    if selected_row == len(cal_points):
                        # Update: salva calibrazione
                        self.config.set('calibration.point1_raw', cal_points[0]['raw'])
                        self.config.set('calibration.point1_real', cal_points[0]['real'])
                        self.config.set('calibration.point2_raw', cal_points[1]['raw'])
                        self.config.set('calibration.point2_real', cal_points[1]['real'])

                        # Mostra conferma
                        self.display.fill(0)
                        self.display.text("Calibration", 0, 20, 1)
                        self.display.text("Updated!", 0, 32, 1)
                        self.display.show()
                        time.sleep(1)
                        running = False

            time.sleep(0.05)

        # Cleanup sensore
        del sensor
        import gc
        gc.collect()

    def _save_and_exit(self):
        """Salva la configurazione ed esce"""
        self.display.fill(0)
        self.display.text("Saving...", 0, 0, 1)
        self.display.show()

        if self.config.save():
            self.display.text("Saved!", 0, 12, 1)
        else:
            self.display.text("Error!", 0, 12, 1)

        self.display.show()
        import time
        time.sleep(1)

        self.exit_requested = True
        # Forza uscita impostando current_items a lista vuota
        if self.menu:
            self.menu.current_items = []

    def _exit_without_save(self):
        """Esce senza salvare"""
        self.display.fill(0)
        self.display.text("Exiting...", 0, 0, 1)
        self.display.text("Not saved!", 0, 12, 1)
        self.display.show()
        import time
        time.sleep(1)

        self.exit_requested = True
        # Forza uscita impostando current_items a lista vuota
        if self.menu:
            self.menu.current_items = []

    def run(self):
        """Esegue l'app di setup"""
        # Mostra schermata di benvenuto
        self.display.fill(0)
        self.display.text("SmartThermo", 20, 10, 1)
        self.display.text("SETUP", 45, 30, 1)
        self.display.show()
        import time
        time.sleep(1)

        # Costruisce il menu
        root_items = self._build_menu_tree()

        # Crea e avvia il menu
        self.menu = Menu(self.display, self.config, root_items)
        self.menu.run()

        # Cleanup
        self.cleanup()

    def cleanup(self):
        """Libera la memoria"""
        if self.menu:
            self.menu.cleanup()
            del self.menu

        # Non elimina config perché è singleton e serve all'app principale
        gc.collect()
        print("Setup app cleaned up")


def main(display, i2c=None, autotune_callback=None):
    """Entry point per l'app setup"""
    app = SetupApp(display, i2c, autotune_callback)
    app.run()
    del app
    gc.collect()
