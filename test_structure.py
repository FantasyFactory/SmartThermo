"""
Script di test per validare la struttura del progetto
Esegui questo script per verificare che tutti i moduli siano corretti
"""

def test_imports():
    """Test che tutti i moduli si importino correttamente"""
    print("Testing imports...")

    try:
        # Test config
        import sys
        sys.path.insert(0, 'src')

        from config import Config
        print("✓ Config imported")

        from menu import Menu, MenuItem
        print("✓ Menu imported")

        from drivers.ssd1306 import SSD1306_I2C
        print("✓ SSD1306 driver imported")

        print("\n✓ All imports successful!")
        return True

    except ImportError as e:
        print(f"✗ Import failed: {e}")
        return False


def test_config():
    """Test della classe Config"""
    print("\nTesting Config class...")

    try:
        from config import Config

        # Test singleton
        config1 = Config()
        config2 = Config()
        assert config1 is config2, "Config should be singleton"
        print("✓ Singleton pattern works")

        # Test accesso ai PIN
        assert hasattr(config1, 'PIN_SDA'), "Config should have PIN_SDA"
        assert config1.PIN_SDA == 5, "PIN_SDA should be 5"
        print("✓ Pin access works")

        # Test get/set
        config1.set('test.value', 42)
        assert config1.get('test.value') == 42, "Get/Set should work"
        print("✓ Get/Set works")

        print("✓ Config tests passed!")
        return True

    except Exception as e:
        print(f"✗ Config test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_menu_structure():
    """Test della struttura del menu"""
    print("\nTesting Menu structure...")

    try:
        from menu import MenuItem

        # Test creazione voci
        item_label = MenuItem(MenuItem.TYPE_LABEL, "Test Label")
        assert item_label.type == MenuItem.TYPE_LABEL
        print("✓ Label item created")

        item_bool = MenuItem(MenuItem.TYPE_BOOL, "Test Bool", value=True)
        assert item_bool.get_current_value() == True
        print("✓ Bool item created")

        item_int = MenuItem(MenuItem.TYPE_INT, "Test Int", value=50, min_val=0, max_val=100, step=10)
        assert item_int.min_val == 0
        assert item_int.max_val == 100
        print("✓ Int item created")

        item_level = MenuItem(MenuItem.TYPE_LEVEL, "Test Level", items=[item_label, item_bool])
        assert len(item_level.items) == 2
        print("✓ Level item created")

        print("✓ Menu structure tests passed!")
        return True

    except Exception as e:
        print(f"✗ Menu structure test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_file_structure():
    """Test che tutti i file necessari esistano"""
    print("\nTesting file structure...")

    import os

    files_to_check = [
        'src/boot.py',
        'src/main.py',
        'src/config.py',
        'src/config.json',
        'src/menu.py',
        'src/setup.py',
        'src/drivers/ssd1306.py'
    ]

    all_exist = True
    for filepath in files_to_check:
        if os.path.exists(filepath):
            print(f"✓ {filepath}")
        else:
            print(f"✗ {filepath} - NOT FOUND")
            all_exist = False

    if all_exist:
        print("✓ All files present!")

    return all_exist


def main():
    """Esegue tutti i test"""
    print("=" * 50)
    print("SmartThermo - Structure Test")
    print("=" * 50)

    results = []

    results.append(("File Structure", test_file_structure()))
    results.append(("Imports", test_imports()))
    results.append(("Config", test_config()))
    results.append(("Menu Structure", test_menu_structure()))

    print("\n" + "=" * 50)
    print("Test Results:")
    print("=" * 50)

    for name, result in results:
        status = "PASS" if result else "FAIL"
        symbol = "✓" if result else "✗"
        print(f"{symbol} {name}: {status}")

    all_passed = all(r[1] for r in results)

    print("=" * 50)
    if all_passed:
        print("✓ ALL TESTS PASSED!")
    else:
        print("✗ SOME TESTS FAILED")
    print("=" * 50)

    return all_passed


if __name__ == '__main__':
    import sys
    success = main()
    sys.exit(0 if success else 1)
