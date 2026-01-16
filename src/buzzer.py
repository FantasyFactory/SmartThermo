from machine import Pin, PWM
import time

def beep(pin_num, frequency, duration_ms):
    """
    Genera un beep usando PWM
    
    Args:
        pin_num: Numero GPIO del pin collegato al buzzer
        frequency: Frequenza del tono in Hz (1-1000 per ESP8266)
        duration_ms: Durata del beep in millisecondi
    """
    try:
        # Crea oggetto PWM
        buzzer = PWM(Pin(pin_num))
        
        # Imposta frequenza
        buzzer.freq(frequency)
        
        # Imposta duty cycle al 50% (512 su 1023) per volume massimo
        buzzer.duty(512)
        
        # Aspetta per la durata specificata
        time.sleep_ms(duration_ms)
        
        # Ferma il PWM
        buzzer.duty(0)
        buzzer.deinit()
        
    except Exception as e:
        print(f"Errore beep: {e}")

# Versione con controllo volume
def beep_volume(pin_num, frequency, duration_ms, volume=50):
    """
    Genera un beep con controllo volume
    
    Args:
        pin_num: Numero GPIO del pin
        frequency: Frequenza in Hz (1-1000)
        duration_ms: Durata in ms
        volume: Volume in percentuale (0-100)
    """
    try:
        buzzer = PWM(Pin(pin_num))
        buzzer.freq(frequency)
        
        # Converti volume percentuale in duty cycle (0-1023)
        duty = int((volume / 100) * 1023)
        buzzer.duty(duty)
        
        time.sleep_ms(duration_ms)
        
        buzzer.duty(0)
        buzzer.deinit()
        
    except Exception as e:
        print(f"Errore beep: {e}")
        

# Classe Buzzer per uso più avanzato
class Buzzer:
    def __init__(self, pin_num):
        self.pin_num = pin_num
        self.pwm = None
    
    def beep(self, frequency=1000, duration_ms=100, volume=50):
        """Singolo beep"""
        beep_volume(self.pin_num, frequency, duration_ms, volume)
    
    def double_beep(self, frequency=1000, duration_ms=100, pause_ms=100):
        """Doppio beep"""
        self.beep(frequency, duration_ms)
        time.sleep_ms(pause_ms)
        self.beep(frequency, duration_ms)
    
    def success(self):
        """Suono di successo (tono ascendente)"""
        self.beep(800, 100)
        self.beep(1000, 100)
        self.beep(1200, 150)
    
    def error(self):
        """Suono di errore (tono discendente)"""
        self.beep(1200, 100)
        self.beep(1000, 100)
        self.beep(800, 200)
    
    def alert(self, times=3):
        """Allarme ripetuto"""
        for _ in range(times):
            self.beep(1500, 200)
            time.sleep_ms(100)
    
    def click(self):
        """Suono click per feedback pulsanti"""
        self.beep(2000, 20, volume=30)
    
    def melody(self, notes):
        """
        Suona una melodia
        notes: lista di tuple (frequenza, durata_ms)
        """
        for freq, duration in notes:
            if freq == 0:  # Pausa
                time.sleep_ms(duration)
            else:
                self.beep(freq, duration)
            time.sleep_ms(10)  # Piccola pausa tra note
            
    def note_on(self, frequency, volume=50):
        try:
            self.pwm = PWM(Pin(self.pin_num))
            self.pwm.freq(frequency)
            
            # Converti volume percentuale in duty cycle (0-1023)
            duty = int((volume / 100) * 1023)
            self.pwm.duty(duty)
            
        except Exception as e:
            print(f"Errore beep: {e}")
        
    def note_off(self):
        try:
            self.pwm.duty(0)
            self.pwm.deinit()
            
        except Exception as e:
            print(f"Errore beep: {e}")

# Esempi di utilizzo
if __name__ == "__main__":
    # Esempio semplice
    BUZZER_PIN = 1  # GPIO15 per ESP8266
    
    # Beep singolo
    beep(BUZZER_PIN, 1000, 200)
    
    # Con controllo volume
    beep_volume(BUZZER_PIN, 800, 300, volume=75)
    
    # Usando la classe
    buzzer = Buzzer(BUZZER_PIN)
    
    # Feedback per menu
    buzzer.click()  # Click su pulsante
    time.sleep(1)
    
    buzzer.success()  # Operazione completata
    time.sleep(1)
    
    buzzer.error()  # Errore
    time.sleep(1)
    
    # Melodia semplice (note Do-Re-Mi)
    melody_notes = [
        (262, 200),  # Do
        (294, 200),  # Re
        (330, 200),  # Mi
        (262, 400),  # Do lungo
    ]
    buzzer.melody(melody_notes)