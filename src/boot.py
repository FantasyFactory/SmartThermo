"""
Boot script per SmartThermo
Questo file viene eseguito automaticamente all'avvio di MicroPython
"""
import gc
import sys

# Ottimizza memoria
gc.enable()
gc.collect()

print("=" * 40)
print("SmartThermo Boot")
print("=" * 40)

# Importa e avvia main
try:
    import main
    main.main()
except Exception as e:
    print(f"Boot error: {e}")
    sys.print_exception(e)
