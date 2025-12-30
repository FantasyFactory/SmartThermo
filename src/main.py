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

        # Inizializza pulsanti per controllo avvio PRIMA di tutto
        # RIGHT per entrare in setup all'avvio
        # FIRE per bloccare l'avvio (debug mode)
        print("Initializing buttons...")
        self.btn_right = Pin(self.config.PIN_RIGHT, Pin.IN, Pin.PULL_UP)
        self.btn_fire = Pin(self.config.PIN_FIRE, Pin.IN, Pin.PULL_UP)

        # Breve delay per stabilizzare i pin
        time.sleep(0.05)

        # Verifica subito se FIRE è premuto
        if self.btn_fire.value() == 0:
            print("\n" + "="*40)
            print("!!! DEBUG MODE DETECTED !!!")
            print("FIRE button is pressed")
            print("="*40 + "\n")

        # Inizializza display OLED
        try:
            self.display = SSD1306_I2C(128, 64, self.i2c)
            print("Display initialized")
        except Exception as e:
            print(f"Error initializing display: {e}")
            self.display = None

        # Mostra splash screen (dà 1 secondo per premere FIRE)
        if self.display:
            self.show_splash()

    def show_splash(self):
        """Mostra schermata di avvio"""
        self.display.fill(0)
        self.display.text("SmartThermo", 20, 10, 1)
        self.display.text("v1.0", 50, 25, 1)
        self.display.text("Hold FIRE", 28, 45, 1)
        self.display.text("for Debug", 28, 55, 1)
        self.display.show()

        # Sleep più lungo per dare tempo di premere FIRE
        # Durante questo tempo controlliamo continuamente
        start = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start) < 1500:  # 1.5 secondi
            if self.btn_fire.value() == 0:
                print("DEBUG: FIRE pressed during splash!")
            time.sleep(0.1)

    def check_setup_mode(self):
        """Controlla se entrare in modalità setup (pulsante RIGHT premuto all'avvio)"""
        return self.btn_right.value() == 0

    def check_debug_mode(self):
        """Controlla se entrare in debug mode (pulsante FIRE premuto all'avvio)"""
        return self.btn_fire.value() == 0

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
        # Se FIRE premuto all'avvio, entra in DEBUG MODE (blocca esecuzione)
        if self.check_debug_mode():
            print("\n" + "="*40)
            print("DEBUG MODE - Execution halted")
            print("FIRE button pressed at boot")
            print("REPL available for debugging")
            print("="*40 + "\n")

            if self.display:
                self.display.fill(0)
                self.display.text("DEBUG MODE", 25, 20, 1)
                self.display.text("REPL Ready", 25, 35, 1)
                self.display.show()

            # Loop infinito per mantenere il controllo e non far riavviare boot.py
            while True:
                time.sleep(1)

        # Altrimenti avvia app normale
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
