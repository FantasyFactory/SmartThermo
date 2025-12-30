"""
Sistema di menu navigabile generico per GUI
Supporta diversi tipi di voci: Label, Level, Action, Int, Float, IP, List, Bool
"""
import gc
from machine import Pin
import time

class MenuItem:
    """Classe base per una voce di menu"""

    # Tipi di voci di menu
    TYPE_LABEL = 'label'
    TYPE_LEVEL = 'level'
    TYPE_ACTION = 'action'
    TYPE_INT = 'int'
    TYPE_FLOAT = 'float'
    TYPE_IP = 'ip'
    TYPE_LIST = 'list'
    TYPE_BOOL = 'bool'

    def __init__(self, item_type, label, **kwargs):
        """
        Inizializza una voce di menu

        Args:
            item_type: Tipo di voce (LABEL, LEVEL, ACTION, INT, FLOAT, IP, LIST, BOOL)
            label: Etichetta da visualizzare
            **kwargs: Parametri specifici per tipo
                - items: lista di sottovoci (per LEVEL)
                - action: callback da eseguire (per ACTION)
                - value: valore corrente (per INT, FLOAT, BOOL, LIST)
                - min_val: valore minimo (per INT, FLOAT)
                - max_val: valore massimo (per INT, FLOAT)
                - step: incremento (per INT, FLOAT)
                - choices: lista di scelte (per LIST)
                - get_value: funzione per ottenere valore corrente
                - set_value: funzione per impostare valore
        """
        self.type = item_type
        self.label = label
        self.items = kwargs.get('items', [])
        self.action = kwargs.get('action', None)
        self.min_val = kwargs.get('min_val', 0)
        self.max_val = kwargs.get('max_val', 100)
        self.step = kwargs.get('step', 1)
        self.choices = kwargs.get('choices', [])
        self.get_value = kwargs.get('get_value', None)
        self.set_value = kwargs.get('set_value', None)

        # Valore interno (usato se non ci sono get/set_value)
        self._value = kwargs.get('value', None)

    def get_current_value(self):
        """Ottiene il valore corrente"""
        if self.get_value:
            return self.get_value()
        return self._value

    def set_current_value(self, value):
        """Imposta il valore corrente"""
        if self.set_value:
            self.set_value(value)
        else:
            self._value = value


class Menu:
    """Sistema di menu navigabile"""

    def __init__(self, display, config, root_items):
        """
        Inizializza il menu

        Args:
            display: istanza del display OLED
            config: istanza della configurazione (per accesso ai PIN)
            root_items: lista di MenuItem radice
        """
        self.display = display
        self.config = config
        self.root_items = root_items
        self.current_items = root_items
        self.current_index = 0
        self.level_stack = []  # Stack per tenere traccia dei livelli
        self.editing = False  # Flag per modalità editing
        self.edit_index = 0  # Indice per editing (es. cifra IP)

        # Inizializza i pulsanti
        self._init_buttons()

        # Parametri di visualizzazione
        self.visible_items = 5  # Numero di voci visibili
        self.scroll_offset = 0  # Offset per scrolling

    def _init_buttons(self):
        """Inizializza i pulsanti di navigazione"""
        self.btn_up = Pin(self.config.PIN_UP, Pin.IN, Pin.PULL_UP)
        self.btn_down = Pin(self.config.PIN_DOWN, Pin.IN, Pin.PULL_UP)
        self.btn_left = Pin(self.config.PIN_LEFT, Pin.IN, Pin.PULL_UP)
        self.btn_right = Pin(self.config.PIN_RIGHT, Pin.IN, Pin.PULL_UP)

        # Variabili per debouncing
        self.last_btn_time = 0
        self.debounce_ms = 200

    def _read_button(self, btn):
        """Legge un pulsante con debouncing"""
        now = time.ticks_ms()
        if time.ticks_diff(now, self.last_btn_time) < self.debounce_ms:
            return False

        if btn.value() == 0:  # Pulsante premuto (pull-up)
            self.last_btn_time = now
            return True
        return False

    def handle_input(self):
        """Gestisce l'input dai pulsanti e ritorna True se c'è stato un cambiamento"""
        changed = False

        if self._read_button(self.btn_up):
            changed = self._handle_up()
        elif self._read_button(self.btn_down):
            changed = self._handle_down()
        elif self._read_button(self.btn_left):
            changed = self._handle_left()
        elif self._read_button(self.btn_right):
            changed = self._handle_right()

        return changed

    def _handle_up(self):
        """Gestisce pulsante UP"""
        current_item = self.current_items[self.current_index]

        if self.editing:
            # Modalità editing: incrementa valore
            if current_item.type == MenuItem.TYPE_INT:
                val = current_item.get_current_value()
                val = min(val + current_item.step, current_item.max_val)
                current_item.set_current_value(val)
                return True
            elif current_item.type == MenuItem.TYPE_FLOAT:
                val = current_item.get_current_value()
                val = min(val + current_item.step, current_item.max_val)
                current_item.set_current_value(val)
                return True
            elif current_item.type == MenuItem.TYPE_BOOL:
                current_item.set_current_value(True)
                return True
            elif current_item.type == MenuItem.TYPE_LIST:
                choices = current_item.choices
                val = current_item.get_current_value()
                try:
                    idx = choices.index(val)
                    idx = (idx - 1) % len(choices)
                    current_item.set_current_value(choices[idx])
                except ValueError:
                    current_item.set_current_value(choices[0] if choices else None)
                return True
            elif current_item.type == MenuItem.TYPE_IP:
                # Incrementa la cifra corrente dell'IP
                ip = current_item.get_current_value()
                octets = [int(x) for x in ip.split('.')]
                octets[self.edit_index] = min(octets[self.edit_index] + 1, 255)
                current_item.set_current_value('.'.join(map(str, octets)))
                return True
        else:
            # Modalità navigazione: scorre su
            if self.current_index > 0:
                self.current_index -= 1
                # Aggiusta scroll offset
                if self.current_index < self.scroll_offset:
                    self.scroll_offset = self.current_index
                return True
        return False

    def _handle_down(self):
        """Gestisce pulsante DOWN"""
        current_item = self.current_items[self.current_index]

        if self.editing:
            # Modalità editing: decrementa valore
            if current_item.type == MenuItem.TYPE_INT:
                val = current_item.get_current_value()
                val = max(val - current_item.step, current_item.min_val)
                current_item.set_current_value(val)
                return True
            elif current_item.type == MenuItem.TYPE_FLOAT:
                val = current_item.get_current_value()
                val = max(val - current_item.step, current_item.min_val)
                current_item.set_current_value(val)
                return True
            elif current_item.type == MenuItem.TYPE_BOOL:
                current_item.set_current_value(False)
                return True
            elif current_item.type == MenuItem.TYPE_LIST:
                choices = current_item.choices
                val = current_item.get_current_value()
                try:
                    idx = choices.index(val)
                    idx = (idx + 1) % len(choices)
                    current_item.set_current_value(choices[idx])
                except ValueError:
                    current_item.set_current_value(choices[0] if choices else None)
                return True
            elif current_item.type == MenuItem.TYPE_IP:
                # Decrementa la cifra corrente dell'IP
                ip = current_item.get_current_value()
                octets = [int(x) for x in ip.split('.')]
                octets[self.edit_index] = max(octets[self.edit_index] - 1, 0)
                current_item.set_current_value('.'.join(map(str, octets)))
                return True
        else:
            # Modalità navigazione: scorre giù
            if self.current_index < len(self.current_items) - 1:
                self.current_index += 1
                # Aggiusta scroll offset
                if self.current_index >= self.scroll_offset + self.visible_items:
                    self.scroll_offset = self.current_index - self.visible_items + 1
                return True
        return False

    def _handle_left(self):
        """Gestisce pulsante LEFT"""
        current_item = self.current_items[self.current_index]

        if self.editing:
            # Modalità editing
            if current_item.type == MenuItem.TYPE_IP:
                # Passa alla cifra precedente dell'IP
                self.edit_index = (self.edit_index - 1) % 4
                return True
            else:
                # Esci da modalità editing
                self.editing = False
                self.edit_index = 0
                return True
        else:
            # Esci dal livello corrente
            if self.level_stack:
                self.current_items, self.current_index, self.scroll_offset = self.level_stack.pop()
                return True
        return False

    def _handle_right(self):
        """Gestisce pulsante RIGHT"""
        current_item = self.current_items[self.current_index]

        if self.editing:
            # Modalità editing
            if current_item.type == MenuItem.TYPE_IP:
                # Passa alla cifra successiva dell'IP
                self.edit_index = (self.edit_index + 1) % 4
                return True
        else:
            # Gestisce azione in base al tipo
            if current_item.type == MenuItem.TYPE_LEVEL:
                # Entra nel sottolivello
                if current_item.items:
                    self.level_stack.append((self.current_items, self.current_index, self.scroll_offset))
                    self.current_items = current_item.items
                    self.current_index = 0
                    self.scroll_offset = 0
                    return True
            elif current_item.type == MenuItem.TYPE_ACTION:
                # Esegue l'azione
                if current_item.action:
                    current_item.action()
                return True
            elif current_item.type in [MenuItem.TYPE_INT, MenuItem.TYPE_FLOAT,
                                       MenuItem.TYPE_BOOL, MenuItem.TYPE_LIST, MenuItem.TYPE_IP]:
                # Entra in modalità editing
                self.editing = True
                self.edit_index = 0
                return True
        return False

    def render(self):
        """Renderizza il menu sul display"""
        self.display.fill(0)

        # Calcola quali voci visualizzare
        start_idx = self.scroll_offset
        end_idx = min(start_idx + self.visible_items, len(self.current_items))

        y = 0
        for i in range(start_idx, end_idx):
            item = self.current_items[i]

            # Indicatore di selezione
            prefix = '>' if i == self.current_index else ' '

            # Costruisce la stringa da visualizzare
            text = f"{prefix}{item.label}"

            # Aggiunge il valore per i tipi editabili
            if item.type == MenuItem.TYPE_BOOL:
                val = item.get_current_value()
                text += f": {'ON' if val else 'OFF'}"
            elif item.type == MenuItem.TYPE_INT:
                val = item.get_current_value()
                text += f": {val}"
            elif item.type == MenuItem.TYPE_FLOAT:
                val = item.get_current_value()
                text += f": {val:.2f}"
            elif item.type == MenuItem.TYPE_LIST:
                val = item.get_current_value()
                text += f": {val}"
            elif item.type == MenuItem.TYPE_IP:
                val = item.get_current_value()
                if self.editing and i == self.current_index:
                    # Evidenzia la cifra in editing
                    octets = val.split('.')
                    highlighted = octets[self.edit_index]
                    octets[self.edit_index] = f"[{highlighted}]"
                    text += f": {'.'.join(octets)}"
                else:
                    text += f": {val}"
            elif item.type == MenuItem.TYPE_LEVEL:
                text += " >"

            # Indicatore di editing
            if self.editing and i == self.current_index and item.type != MenuItem.TYPE_IP:
                text = "*" + text[1:]

            # Disegna il testo (troncato se troppo lungo)
            if len(text) > 21:
                text = text[:21]

            self.display.text(text, 0, y, 1)
            y += 12

        self.display.show()

    def run(self):
        """Loop principale del menu. Ritorna quando si esce dal menu."""
        self.render()

        while True:
            if self.handle_input():
                self.render()
                gc.collect()

            # Verifica se siamo usciti completamente dal menu
            if not self.level_stack and self.current_items == []:
                break

            time.sleep_ms(50)  # Piccola pausa per non saturare la CPU

    def cleanup(self):
        """Libera le risorse"""
        del self.btn_up
        del self.btn_down
        del self.btn_left
        del self.btn_right
        gc.collect()
