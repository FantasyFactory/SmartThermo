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
├── app.py               # App principale termometro
├── wifi_manager.py      # Gestione WiFi (STA/AP/BOTH)
├── web_server.py        # Web server HTTP con API REST
├── drivers/
│   ├── ssd1306.py       # Driver display OLED
│   └── mlx90614.py      # Driver sensore temperatura IR
└── static/
    ├── index.html       # Interfaccia web
    ├── style.css        # Stili interfaccia
    └── app.js           # JavaScript interfaccia
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

## App Principale

L'app principale (`app.py`) implementa tutte le funzionalità del termometro:

### Funzionalità

#### Lettura Temperature
- **Sensore MLX90614**: lettura temperatura oggetto e ambiente via I2C
- **Modalità OnShoot**: legge temperatura quando si preme il pulsante FIRE
- **Modalità Continue**: lettura continua con refresh configurabile (50-1000ms)
- **Feedback**: beep opzionale alla lettura e controllo laser

#### Display
- **Modalità normale**: mostra entrambe le temperature e target termostato
- **Modalità BigNum**: visualizza solo temperatura oggetto in grande
- **Refresh rate configurabile**: da 50ms a 1000ms

#### Connettività WiFi
- **Modalità Off**: nessuna connessione
- **Modalità STA**: client, connessione a rete WiFi esistente
- **Modalità AP**: access point per configurazione
- **Modalità BOTH**: client + access point simultanei
- **Fallback automatico**: se STA fallisce, passa ad AP

#### Web Server & API REST

Il web server è accessibile all'indirizzo IP del dispositivo (porta 80) e fornisce:

**API Temperature:**
- `GET /api/temp` - Lettura temperatura oggetto
- `GET /api/ambient` - Lettura temperatura ambiente

**API Termostato:**
- `GET /api/target` - Ottiene target e stato termostato
- `POST /api/target` - Imposta target e attiva/disattiva

**API Configurazione:**
- `GET /api/config` - Ottiene configurazione completa
- `POST /api/config` - Aggiorna configurazione

**API WiFi:**
- `GET /api/wifi/scan` - Scansiona reti disponibili
- `POST /api/wifi/test` - Testa connessione a rete
- `POST /api/wifi/save` - Salva configurazione WiFi

**API Status:**
- `GET /api/status` - Status completo del sistema

#### Interfaccia Web

Interfaccia web responsive accessibile via browser:
- **Dashboard temperature**: visualizzazione real-time con auto-refresh
- **Controllo termostato**: attiva/disattiva e imposta target
- **Configurazione WiFi**: scan reti, test connessione, salvataggio
- **Editor configurazione**: modifica diretta del JSON
- **System status**: info WiFi, IP, SSID connesso

### Termostato (Base)

Funzionalità termostato di base implementata:
- Attivazione/disattivazione via config o web
- Impostazione target temperature
- Visualizzazione target su display
- TODO: Implementazione controllo PID completo
- TODO: Integrazione Tapo per controllo remoto

## TODO

Funzionalità da completare:
- **Controllo PID**: implementazione algoritmo PID per termostato
- **Auto-tune PID**: procedura automatica di calibrazione parametri
- **Integrazione Tapo**: controllo smart plug Tapo per attuazione termostato
- **Logging**: salvataggio storico temperature su file
- **Grafici**: visualizzazione trend temperature su interfaccia web

## Licenza
MIT License
