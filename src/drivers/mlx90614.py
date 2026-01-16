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

# Indirizzi EEPROM
MLX90614_EEPROM_EMISSIVITY = const(0x24)  # Registro emissività (EEPROM)
MLX90614_EEPROM_CONFIG = const(0x25)  # Config register


class MLX90614:
    """Driver per sensore MLX90614"""

    def __init__(self, i2c, addr=MLX90614_I2C_ADDR, config=None):
        """
        Inizializza il sensore

        Args:
            i2c: istanza I2C
            addr: indirizzo I2C del sensore (default 0x5A)
            config: istanza Config per calibrazione (opzionale)
        """
        self.i2c = i2c
        self.addr = addr
        self._buf = bytearray(3)
        self.config = config

        # Calcola coefficienti di calibrazione lineare
        self._cal_enabled = False
        self._cal_m = 1.0  # coefficiente angolare
        self._cal_q = 0.0  # intercetta

        if config and config.calibration_enabled:
            self._calculate_calibration()

        # Verifica che il sensore sia presente
        if addr not in i2c.scan():
            raise OSError(f"MLX90614 not found at address {hex(addr)}")

        print(f"MLX90614 initialized at {hex(addr)}")
        if self._cal_enabled:
            print(f"Calibration enabled: m={self._cal_m:.4f}, q={self._cal_q:.4f}")

    def _calculate_calibration(self):
        """
        Calcola i coefficienti di calibrazione lineare usando due punti
        Formula: temp_corretta = m * temp_letta + q

        Dove:
            m = (y2 - y1) / (x2 - x1)  [coefficiente angolare]
            q = y1 - m * x1             [intercetta]
        """
        try:
            x1 = self.config.calibration_point1_raw   # es. 36.3
            y1 = self.config.calibration_point1_real  # es. 60.0
            x2 = self.config.calibration_point2_raw   # es. 58.2
            y2 = self.config.calibration_point2_real  # es. 100.0

            # Evita divisione per zero
            if abs(x2 - x1) < 0.1:
                print("Warning: calibration points too close, using default")
                return

            # Calcola coefficienti
            self._cal_m = (y2 - y1) / (x2 - x1)
            self._cal_q = y1 - self._cal_m * x1
            self._cal_enabled = True

        except Exception as e:
            print(f"Error calculating calibration: {e}")
            self._cal_enabled = False

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

            # Debug: stampa temperatura prima della calibrazione
            print(f"Raw temp: {temp_c:.1f}°C")

            # Applica calibrazione lineare se abilitata
            if self._cal_enabled:
                temp_c = self._cal_m * temp_c + self._cal_q
                print(f"Calibrated temp: {temp_c:.1f}°C")

            return round(temp_c, 1)

        except Exception as e:
            print(f"Error reading temperature: {e}")
            import sys
            sys.print_exception(e)
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
            Temperatura calibrata in °C o None se errore
        """
        return self._read_temp(MLX90614_TOBJ1)

    def read_object_temp_raw(self):
        """
        Legge la temperatura RAW (non calibrata) dell'oggetto

        Returns:
            Temperatura raw in °C o None se errore
        """
        # Temporaneamente disabilita calibrazione
        cal_enabled = self._cal_enabled
        self._cal_enabled = False
        temp = self._read_temp(MLX90614_TOBJ1)
        self._cal_enabled = cal_enabled
        return temp

    def read_both(self):
        """
        Legge entrambe le temperature (calibrata e ambiente)

        Returns:
            Tupla (object_temp, ambient_temp) o (None, None) se errore
        """
        obj_temp = self.read_object_temp()
        time.sleep_ms(10)  # Piccola pausa tra le letture
        amb_temp = self.read_ambient_temp()
        return obj_temp, amb_temp

    def read_all(self):
        """
        Legge tutte le temperature: calibrata, raw, ambiente

        Returns:
            Tupla (object_temp_calibrated, object_temp_raw, ambient_temp)
        """
        obj_temp = self.read_object_temp()
        time.sleep_ms(10)
        obj_temp_raw = self.read_object_temp_raw()
        time.sleep_ms(10)
        amb_temp = self.read_ambient_temp()
        return obj_temp, obj_temp_raw, amb_temp

    # === Funzioni per gestione Emissività EEPROM ===

    def _crc8(self, data):
        """
        Calcola CRC-8 per comunicazione EEPROM MLX90614
        Polinomio: 0x07 (x^8 + x^2 + x + 1)

        Args:
            data: bytes da processare

        Returns:
            CRC-8 calcolato
        """
        crc = 0x00
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x80:
                    crc = (crc << 1) ^ 0x07
                else:
                    crc = crc << 1
            crc &= 0xFF
        return crc

    def read_emissivity(self):
        """
        Legge il valore di emissività dalla EEPROM

        Returns:
            Emissività come float 0.0-1.0, o None se errore
        """
        try:
            # Leggi 3 bytes da EEPROM (2 data + 1 PEC)
            data = bytearray(3)
            self.i2c.readfrom_mem_into(self.addr, MLX90614_EEPROM_EMISSIVITY, data)

            # Estrai valore (16 bit little-endian)
            raw_value = (data[1] << 8) | data[0]

            # Converti in emissività (0x0000 = 0.0, 0xFFFF = 1.0)
            emissivity = raw_value / 65535.0

            print(f"Emissivity from EEPROM: {emissivity:.4f} (raw: 0x{raw_value:04X})")
            return emissivity

        except Exception as e:
            print(f"Error reading emissivity: {e}")
            return None

    def write_emissivity(self, emissivity):
        """
        Scrive un nuovo valore di emissività nella EEPROM

        ATTENZIONE: La EEPROM ha un numero limitato di cicli di scrittura (~100k)
        Usare con cautela!

        Args:
            emissivity: valore di emissività 0.0-1.0

        Returns:
            True se successo, False altrimenti
        """
        try:
            # Validazione input
            if not (0.0 <= emissivity <= 1.0):
                print(f"Error: emissivity must be 0.0-1.0, got {emissivity}")
                return False

            # Converti emissività in valore EEPROM (16 bit)
            raw_value = int(emissivity * 65535)

            print(f"Writing emissivity {emissivity:.4f} (0x{raw_value:04X}) to EEPROM...")

            # FASE 1: Cancella vecchio valore (write 0x0000)
            erase_data = bytearray([0x00, 0x00])

            # Calcola CRC per erase (indirizzo + data)
            crc_data = bytearray([self.addr << 1, MLX90614_EEPROM_EMISSIVITY]) + erase_data
            crc = self._crc8(crc_data)

            # Scrivi 0x0000 + CRC
            erase_packet = erase_data + bytearray([crc])
            self.i2c.writeto_mem(self.addr, MLX90614_EEPROM_EMISSIVITY, erase_packet)
            time.sleep_ms(10)  # Wait per erase

            # FASE 2: Scrivi nuovo valore
            write_data = bytearray([raw_value & 0xFF, (raw_value >> 8) & 0xFF])

            # Calcola CRC per write
            crc_data = bytearray([self.addr << 1, MLX90614_EEPROM_EMISSIVITY]) + write_data
            crc = self._crc8(crc_data)

            # Scrivi valore + CRC
            write_packet = write_data + bytearray([crc])
            self.i2c.writeto_mem(self.addr, MLX90614_EEPROM_EMISSIVITY, write_packet)
            time.sleep_ms(10)  # Wait per write

            # Verifica scrittura
            time.sleep_ms(50)  # Attesa extra per stabilizzazione
            verify = self.read_emissivity()
            if verify is not None and abs(verify - emissivity) < 0.001:
                print(f"Emissivity written successfully: {verify:.4f}")
                return True
            else:
                print(f"Verification failed: expected {emissivity:.4f}, got {verify}")
                return False

        except Exception as e:
            print(f"Error writing emissivity: {e}")
            import sys
            sys.print_exception(e)
            return False
