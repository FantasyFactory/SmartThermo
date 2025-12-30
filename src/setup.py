"""
App Setup - Interfaccia di configurazione per SmartThermo
Crea un menu navigabile per modificare tutte le impostazioni
"""
import gc
from menu import Menu, MenuItem
from config import Config


class SetupApp:
    """Applicazione di setup/configurazione"""

    def __init__(self, display, autotune_callback=None):
        """
        Inizializza l'app di setup

        Args:
            display: istanza del display OLED già inizializzato
            autotune_callback: callback per auto-tune PID (opzionale)
        """
        self.display = display
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


def main(display, autotune_callback=None):
    """Entry point per l'app setup"""
    app = SetupApp(display, autotune_callback)
    app.run()
    del app
    gc.collect()
