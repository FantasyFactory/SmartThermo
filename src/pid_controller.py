"""
Controllore PID per termostato
Implementazione semplice di un controllore PID
"""
import time


class PIDController:
    """Controllore PID con anti-windup"""

    def __init__(self, kp, ki, kd, setpoint=0):
        """
        Inizializza il PID

        Args:
            kp: guadagno proporzionale
            ki: guadagno integrale
            kd: guadagno derivativo
            setpoint: valore target
        """
        self.kp = kp
        self.ki = ki
        self.kd = kd
        self.setpoint = setpoint

        self._last_error = 0
        self._integral = 0
        self._last_time = time.ticks_ms()

    def update(self, current_value):
        """
        Calcola l'output del PID

        Args:
            current_value: valore corrente

        Returns:
            Output del PID (0-100%)
        """
        now = time.ticks_ms()
        dt = time.ticks_diff(now, self._last_time) / 1000.0  # in secondi

        if dt <= 0:
            dt = 0.001

        # Calcola errore
        error = self.setpoint - current_value

        # Proporzionale
        p_term = self.kp * error

        # Integrale (con anti-windup)
        self._integral += error * dt
        # Limita integrale per evitare windup
        self._integral = max(min(self._integral, 100), -100)
        i_term = self.ki * self._integral

        # Derivativo
        d_term = 0
        if dt > 0:
            d_term = self.kd * (error - self._last_error) / dt

        # Output totale
        output = p_term + i_term + d_term

        # Limita output 0-100%
        output = max(min(output, 100), 0)

        # Salva stato
        self._last_error = error
        self._last_time = now

        return output

    def set_tunings(self, kp, ki, kd):
        """Aggiorna i parametri PID"""
        self.kp = kp
        self.ki = ki
        self.kd = kd

    def set_setpoint(self, setpoint):
        """Aggiorna il setpoint"""
        self.setpoint = setpoint

    def reset(self):
        """Reset del controllore"""
        self._integral = 0
        self._last_error = 0
        self._last_time = time.ticks_ms()
