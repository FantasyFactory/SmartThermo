"""
Driver per sensore di temperatura a infrarossi MLX90614
Supporta lettura temperatura oggetto e ambiente via I2C
"""
import time
from micropython import const

# Indirizzi registri MLX90614
MLX90614_I2C_ADDR = const(0x5A)
MLX90614_TA = const(0x06)  # Ambient temperature
MLX90614_TOBJ1 = const(0x07)  # Object temperature


class MLX90614:
    """Driver per sensore MLX90614"""

    def __init__(self, i2c, addr=MLX90614_I2C_ADDR):
        """
        Inizializza il sensore

        Args:
            i2c: istanza I2C
            addr: indirizzo I2C del sensore (default 0x5A)
        """
        self.i2c = i2c
        self.addr = addr
        self._buf = bytearray(3)

        # Verifica che il sensore sia presente
        if addr not in i2c.scan():
            raise OSError(f"MLX90614 not found at address {hex(addr)}")

        print(f"MLX90614 initialized at {hex(addr)}")

    def _read_temp(self, register):
        """
        Legge la temperatura da un registro

        Args:
            register: registro da leggere (TA o TOBJ1)

        Returns:
            Temperatura in gradi Celsius
        """
        try:
            # Leggi 3 bytes (2 dati + 1 PEC)
            self.i2c.readfrom_mem_into(self.addr, register, self._buf)

            # Converti in temperatura
            # I dati sono in formato little-endian
            temp_raw = (self._buf[1] << 8) | self._buf[0]

            # Converti in Celsius
            # Il valore è in 0.02K per LSB, 0x0000 = -273.15°C
            temp_k = temp_raw * 0.02
            temp_c = temp_k - 273.15

            return round(temp_c, 1)

        except Exception as e:
            print(f"Error reading temperature: {e}")
            return None

    def read_ambient_temp(self):
        """
        Legge la temperatura ambiente (del sensore stesso)

        Returns:
            Temperatura in °C o None se errore
        """
        return self._read_temp(MLX90614_TA)

    def read_object_temp(self):
        """
        Legge la temperatura dell'oggetto misurato

        Returns:
            Temperatura in °C o None se errore
        """
        return self._read_temp(MLX90614_TOBJ1)

    def read_both(self):
        """
        Legge entrambe le temperature

        Returns:
            Tupla (object_temp, ambient_temp) o (None, None) se errore
        """
        obj_temp = self.read_object_temp()
        time.sleep_ms(10)  # Piccola pausa tra le letture
        amb_temp = self.read_ambient_temp()
        return obj_temp, amb_temp
