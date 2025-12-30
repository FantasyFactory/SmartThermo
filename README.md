# SmartThermo
Smart advanced IR thermometer con ESP32-C3 e MicroPython

## Descrizione
Termometro a infrarossi "smart" basato su ESP32-C3 con display OLED SSD1306 e sensore MLX90614. Il progetto include un'interfaccia di configurazione navigabile tramite pulsanti e supporto per funzionalità avanzate come controllo WiFi, termostato PID e integrazione Tapo.

## Hardware

### Componenti
- **ESP32-C3**: microcontrollore con MicroPython
- **Display OLED SSD1306**: 128x64 pixel, interfaccia I2C
- **Sensore MLX90614**: termometro a infrarossi, interfaccia I2C
- **5 Pulsanti**: navigazione menu (UP, DOWN, LEFT, RIGHT, FIRE)
- **Laser**: puntatore per misurazione
- **Buzzer**: feedback audio

### Pinout
```
PIN_SDA    = 5   # I2C Data
PIN_SCL    = 6   # I2C Clock
PIN_LEFT   = 3   # Pulsante sinistra
PIN_RIGHT  = 4   # Pulsante destra
PIN_FIRE   = 0   # Pulsante fuoco/conferma
PIN_LASER  = 9   # Controllo laser
PIN_UP     = 10  # Pulsante su
PIN_DOWN   = 7   # Pulsante giù
PIN_BUZZER = 1   # Buzzer
```

### Connessioni I2C
- Frequenza I2C: 100kHz (limitata dal sensore MLX90614)
- Display OLED: indirizzo 0x3C
- Sensore MLX90614: indirizzo 0x5A (default)

## Struttura Software

Il progetto è organizzato in modo modulare per ottimizzare l'uso della memoria di MicroPython:

```
src/
├── boot.py              # Script di avvio automatico
├── main.py              # Entry point principale
├── config.py            # Gestione configurazione (singleton)
├── config.json          # File di configurazione
├── menu.py              # Sistema di menu generico
├── setup.py             # App di configurazione
└── drivers/
    └── ssd1306.py       # Driver display OLED
```

### Architettura

#### 1. Config (`config.py`)
Classe singleton per gestire la configurazione:
- Lettura/scrittura file JSON
- Accesso tramite properties (es. `config.PIN_UP`, `config.wifi_mode`)
- Metodi `get(path)` e `set(path, value)` per accesso gerarchico
- Metodo `reload()` per ricaricare dopo modifiche

#### 2. Menu (`menu.py`)
Sistema di menu navigabile generico che supporta:
- **Label**: separatori/etichette
- **Level**: menu con sottovoci
- **Action**: esegue un callback
- **Int**: valori interi con min/max/step
- **Float**: valori decimali con min/max/step
- **IP**: indirizzi IPv4 (4 ottetti 0-255)
- **List**: selezione da lista di stringhe
- **Bool**: ON/OFF

Navigazione:
- **UP/DOWN**: scorrono le voci (o modificano valori in editing)
- **RIGHT**: entra in sottomenu/editing o esegue azione
- **LEFT**: esce da sottomenu/editing

#### 3. Setup (`setup.py`)
App di configurazione che mappa i valori di `config.json` su un menu navigabile:
- WiFi: Mode, SSID selection
- Preferences: Laser, BigNum, Reading mode, Refresh rate
- Thermostat: Active, Target, PID parameters, Auto-tune
- Tapo: Enable, IP
- Save and Exit / Exit (without save)

#### 4. Main (`main.py`)
Entry point che:
- Inizializza hardware (I2C, display, sensori)
- Controlla se entrare in setup mode (pulsante FIRE premuto all'avvio)
- Gestisce il passaggio tra app con cleanup memoria
- Avvia l'app principale

## Configurazione

Il file `config.json` contiene tutte le impostazioni:

```json
{
  "pins": { ... },
  "wifi": {
    "mode": "AP|STA|BOTH|Off",
    "known": [{"ssid": "...", "password": "..."}],
    "selected": 0,
    "ap_credentials": {...}
  },
  "preferences": {
    "laser": true|false,
    "bignum": true|false,
    "reading": "OnShoot|Continue",
    "refresh": 500
  },
  "thermostat": {
    "active": true|false,
    "target": 50,
    "p": 1.0,
    "i": 0.0,
    "d": 0.0
  },
  "tapo": {
    "enabled": true|false,
    "ip": "192.168.x.x"
  }
}
```

## Installazione

1. Installa MicroPython sull'ESP32-C3
2. Copia tutti i file dalla cartella `src/` sulla memoria del dispositivo
3. Riavvia il dispositivo

### Upload tramite ampy
```bash
ampy --port /dev/ttyUSB0 put src/boot.py
ampy --port /dev/ttyUSB0 put src/main.py
ampy --port /dev/ttyUSB0 put src/config.py
ampy --port /dev/ttyUSB0 put src/config.json
ampy --port /dev/ttyUSB0 put src/menu.py
ampy --port /dev/ttyUSB0 put src/setup.py
ampy --port /dev/ttyUSB0 mkdir drivers
ampy --port /dev/ttyUSB0 put src/drivers/ssd1306.py drivers/ssd1306.py
```

### Upload tramite Thonny
1. Apri Thonny IDE
2. Connetti all'ESP32-C3
3. Copia tutti i file mantenendo la struttura

## Uso

### Avvio Normale
All'accensione, il dispositivo avvia l'app principale del termometro.

### Modalità Setup
1. Tieni premuto il pulsante **FIRE** durante l'accensione
2. Naviga il menu con i pulsanti direzionali
3. Modifica le impostazioni
4. Seleziona "Save and Exit" per salvare

### Navigazione Menu Setup
- **UP/DOWN**: scorrono le voci del menu
- **RIGHT**: entra in un sottomenu o attiva editing
- **LEFT**: esce dal sottomenu o dall'editing
- In editing:
  - **UP/DOWN**: modificano il valore
  - **LEFT/RIGHT**: per IP, cambiano l'ottetto da modificare

## Gestione Memoria

Il progetto implementa strategie per ottimizzare la memoria limitata di MicroPython:
- Separazione tra app setup e principale
- Cleanup con `del` e `gc.collect()` dopo ogni modulo
- Singleton per la classe Config
- Ricarica configurazione da JSON invece di mantenerla in memoria

## TODO / App Principale

L'app principale del termometro è ancora da implementare. Dovrà includere:
- Lettura dal sensore MLX90614
- Visualizzazione temperatura su display
- Modalità di lettura (OnShoot/Continuous)
- Controllo laser
- Funzionalità termostato con PID
- Connettività WiFi
- Integrazione Tapo per controllo remoto

## Licenza
MIT License
