"""
SmartThermo - Main Entry Point
Termometro a infrarossi smart con ESP32-C3, OLED e sensore MLX90614
"""
import gc
import sys
from machine import Pin, I2C
import time

# Importa driver e configurazione
from drivers.ssd1306 import SSD1306_I2C
from config import Config


class SmartThermo:
    """Classe principale per gestire il dispositivo"""

    def __init__(self):
        """Inizializza l'hardware"""
        print("SmartThermo starting...")

        # Carica configurazione
        self.config = Config()

        # Inizializza I2C
        self.i2c = I2C(
            0,
            scl=Pin(self.config.PIN_SCL),
            sda=Pin(self.config.PIN_SDA),
            freq=100000  # Limitato a 100kHz per MLX90614
        )
        print("I2C initialized")

        # Scansiona I2C per vedere i dispositivi connessi
        devices = self.i2c.scan()
        print(f"I2C devices found: {[hex(d) for d in devices]}")

        # Inizializza display OLED
        try:
            self.display = SSD1306_I2C(128, 64, self.i2c)
            print("Display initialized")
        except Exception as e:
            print(f"Error initializing display: {e}")
            self.display = None

        # Mostra splash screen
        if self.display:
            self.show_splash()

        # Inizializza pulsante per entrare in setup
        # Useremo il pulsante RIGHT (PIN 4) tenuto premuto all'avvio
        self.btn_right = Pin(self.config.PIN_RIGHT, Pin.IN, Pin.PULL_UP)
        # Fire blocca l'avvio della app
        self.btn_fire = Pin(self.config.PIN_FIRE, Pin.IN, Pin.PULL_UP)

    def show_splash(self):
        """Mostra schermata di avvio"""
        self.display.fill(0)
        self.display.text("SmartThermo", 20, 20, 1)
        self.display.text("v1.0", 50, 35, 1)
        self.display.show()
        time.sleep(1)

    def check_setup_mode(self):
        """Controlla se entrare in modalità setup (pulsante RIGHT premuto)"""
        return self.btn_right.value() == 0

    def run_setup(self):
        """Avvia l'app di setup"""
        print("Starting setup mode...")

        # Importa e avvia setup
        import setup
        setup.main(self.display)

        # Cleanup del modulo setup per liberare memoria
        del sys.modules['setup']
        del setup
        gc.collect()

        print("Setup mode exited")

        # Ricarica la configurazione (potrebbe essere stata modificata)
        self.config.reload()

    def run_main_app(self):
        """Avvia l'app principale del termometro"""
        print("Starting main app...")

        # Importa e avvia app principale
        import app
        if self.btn_fire.value() != 0:
            app.main(self.display, self.i2c)

        # Cleanup del modulo app per liberare memoria
        del sys.modules['app']
        del app
        gc.collect()

        print("Main app exited")

    def run(self):
        """Loop principale"""
        # Controlla se entrare in setup
        if self.check_setup_mode():
            self.run_setup()

        # Avvia app principale
        self.run_main_app()


def main():
    """Entry point"""
    try:
        app = SmartThermo()
        app.run()
    except KeyboardInterrupt:
        print("\nShutdown by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        import sys
        sys.print_exception(e)
    finally:
        gc.collect()
        print("SmartThermo stopped")


if __name__ == '__main__':
    main()
