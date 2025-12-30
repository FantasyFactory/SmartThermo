// SmartThermo Web Interface
// JavaScript per interazione con API REST

const API_BASE = '';

// Variabili globali
let elements = {};

// === Temperature Functions ===

async function updateTemperatures() {
    try {
        const [objResp, ambResp] = await Promise.all([
            fetch(`${API_BASE}/api/temp`),
            fetch(`${API_BASE}/api/ambient`)
        ]);

        const objData = await objResp.json();
        const ambData = await ambResp.json();

        elements.objTemp.textContent = objData.temperature !== null ?
            objData.temperature.toFixed(1) : '--.-';
        elements.ambTemp.textContent = ambData.temperature !== null ?
            ambData.temperature.toFixed(1) : '--.-';

    } catch (error) {
        console.error('Error fetching temperatures:', error);
        elements.objTemp.textContent = 'ERR';
        elements.ambTemp.textContent = 'ERR';
    }
}

// === Thermostat Functions ===

async function loadThermostat() {
    try {
        const resp = await fetch(`${API_BASE}/api/target`);
        const data = await resp.json();

        elements.thermostatActive.checked = data.active;
        elements.targetTemp.value = data.target;

    } catch (error) {
        console.error('Error loading thermostat:', error);
    }
}

async function saveThermostat() {
    try {
        const data = {
            active: elements.thermostatActive.checked,
            target: parseInt(elements.targetTemp.value)
        };

        const resp = await fetch(`${API_BASE}/api/target`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });

        const result = await resp.json();

        if (result.success) {
            showStatus(elements.wifiStatus, 'Thermostat saved successfully!', 'success');
        } else {
            showStatus(elements.wifiStatus, 'Error saving thermostat', 'error');
        }

    } catch (error) {
        console.error('Error saving thermostat:', error);
        showStatus(elements.wifiStatus, 'Error saving thermostat', 'error');
    }
}

// === WiFi Functions ===

async function scanNetworks() {
    elements.scanBtn.disabled = true;
    elements.scanBtn.textContent = '⏳ Scanning...';

    try {
        const resp = await fetch(`${API_BASE}/api/wifi/scan`);
        const data = await resp.json();

        displayNetworks(data.networks);

    } catch (error) {
        console.error('Error scanning networks:', error);
        showStatus(elements.wifiStatus, 'Error scanning networks', 'error');
    } finally {
        elements.scanBtn.disabled = false;
        elements.scanBtn.textContent = '📡 Scan Networks';
    }
}

function displayNetworks(networks) {
    elements.networkList.innerHTML = '';
    elements.networkList.style.display = 'block';

    if (!networks || networks.length === 0) {
        elements.networkList.innerHTML = '<div style="padding: 20px; text-align: center;">No networks found</div>';
        return;
    }

    networks.forEach(network => {
        const item = document.createElement('div');
        item.className = 'network-item';

        const nameDiv = document.createElement('div');
        nameDiv.className = 'network-name';
        nameDiv.textContent = network.ssid;

        const infoDiv = document.createElement('div');
        infoDiv.className = 'network-info';

        const rssiSpan = document.createElement('span');
        rssiSpan.textContent = `${network.rssi} dBm`;

        const secureSpan = document.createElement('span');
        secureSpan.textContent = network.secure ? '🔒' : '🔓';

        infoDiv.appendChild(rssiSpan);
        infoDiv.appendChild(secureSpan);

        item.appendChild(nameDiv);
        item.appendChild(infoDiv);

        item.onclick = () => selectNetwork(network.ssid, item);

        elements.networkList.appendChild(item);
    });
}

function selectNetwork(ssid, itemElement) {
    // Remove selection from all items
    document.querySelectorAll('.network-item').forEach(el => {
        el.classList.remove('selected');
    });

    // Select this item
    itemElement.classList.add('selected');

    // Show form
    elements.wifiForm.style.display = 'block';
    elements.wifiSsid.value = ssid;
    elements.wifiPassword.value = '';
    elements.wifiPassword.focus();
}

async function testWiFiConnection() {
    const ssid = elements.wifiSsid.value;
    const password = elements.wifiPassword.value;

    if (!ssid) {
        showStatus(elements.wifiStatus, 'Please select a network', 'warning');
        return;
    }

    elements.testWifiBtn.disabled = true;
    elements.testWifiBtn.textContent = '⏳ Testing...';
    showStatus(elements.wifiStatus, 'Testing connection...', 'warning');

    try {
        const resp = await fetch(`${API_BASE}/api/wifi/test`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ssid, password })
        });

        const data = await resp.json();

        if (data.success) {
            showStatus(elements.wifiStatus, 'Connection successful!', 'success');
        } else {
            showStatus(elements.wifiStatus, 'Connection failed! Check password.', 'error');
        }

    } catch (error) {
        console.error('Error testing WiFi:', error);
        showStatus(elements.wifiStatus, 'Error testing connection', 'error');
    } finally {
        elements.testWifiBtn.disabled = false;
        elements.testWifiBtn.textContent = '🔍 Test Connection';
    }
}

async function saveWiFiConfig() {
    const ssid = elements.wifiSsid.value;
    const password = elements.wifiPassword.value;

    if (!ssid) {
        showStatus(elements.wifiStatus, 'Please select a network', 'warning');
        return;
    }

    elements.saveWifiBtn.disabled = true;
    elements.saveWifiBtn.textContent = '⏳ Saving...';

    try {
        const resp = await fetch(`${API_BASE}/api/wifi/save`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ssid, password })
        });

        const data = await resp.json();

        if (data.success) {
            showStatus(elements.wifiStatus,
                'WiFi configuration saved! Restart device to connect.', 'success');
        } else {
            showStatus(elements.wifiStatus, 'Error saving configuration', 'error');
        }

    } catch (error) {
        console.error('Error saving WiFi config:', error);
        showStatus(elements.wifiStatus, 'Error saving configuration', 'error');
    } finally {
        elements.saveWifiBtn.disabled = false;
        elements.saveWifiBtn.textContent = '💾 Save WiFi';
    }
}

// === Config Functions ===

async function loadConfig() {
    try {
        const resp = await fetch(`${API_BASE}/api/config`);
        const data = await resp.json();

        elements.configEditor.value = JSON.stringify(data, null, 2);

    } catch (error) {
        console.error('Error loading config:', error);
        showStatus(elements.wifiStatus, 'Error loading configuration', 'error');
    }
}

async function saveConfig() {
    try {
        const config = JSON.parse(elements.configEditor.value);

        const resp = await fetch(`${API_BASE}/api/config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });

        const data = await resp.json();

        if (data.success) {
            showStatus(elements.wifiStatus, 'Configuration saved!', 'success');
        } else {
            showStatus(elements.wifiStatus, 'Error saving configuration', 'error');
        }

    } catch (error) {
        console.error('Error saving config:', error);
        showStatus(elements.wifiStatus, 'Invalid JSON or error saving', 'error');
    }
}

// === Status Functions ===

async function updateStatus() {
    try {
        const resp = await fetch(`${API_BASE}/api/status`);
        const data = await resp.json();

        // Update WiFi status
        elements.wifiMode.textContent = data.wifi.mode;

        if (data.wifi.sta.connected) {
            elements.ipAddress.textContent = data.wifi.sta.ip;
            elements.connectedSsid.textContent = data.wifi.sta.ssid || '--';
        } else if (data.wifi.ap.active) {
            elements.ipAddress.textContent = data.wifi.ap.ip;
            elements.connectedSsid.textContent = `AP: ${data.wifi.ap.ssid}`;
        } else {
            elements.ipAddress.textContent = '--';
            elements.connectedSsid.textContent = '--';
        }

    } catch (error) {
        console.error('Error updating status:', error);
    }
}

// === Helper Functions ===

function showStatus(element, message, type) {
    element.style.display = 'block';
    element.textContent = message;
    element.className = `status-box status-${type}`;

    // Auto-hide after 5 seconds
    setTimeout(() => {
        element.style.display = 'none';
    }, 5000);
}

// === Initialization ===

window.addEventListener('DOMContentLoaded', () => {
    console.log('SmartThermo Web Interface loading...');

    // Initialize DOM elements
    elements = {
        objTemp: document.getElementById('objTemp'),
        ambTemp: document.getElementById('ambTemp'),
        refreshBtn: document.getElementById('refreshBtn'),
        thermostatActive: document.getElementById('thermostatActive'),
        targetTemp: document.getElementById('targetTemp'),
        saveThermostatBtn: document.getElementById('saveThermostatBtn'),
        scanBtn: document.getElementById('scanBtn'),
        networkList: document.getElementById('networkList'),
        wifiForm: document.getElementById('wifiForm'),
        wifiSsid: document.getElementById('wifiSsid'),
        wifiPassword: document.getElementById('wifiPassword'),
        testWifiBtn: document.getElementById('testWifiBtn'),
        saveWifiBtn: document.getElementById('saveWifiBtn'),
        wifiStatus: document.getElementById('wifiStatus'),
        configEditor: document.getElementById('configEditor'),
        loadConfigBtn: document.getElementById('loadConfigBtn'),
        saveConfigBtn: document.getElementById('saveConfigBtn'),
        wifiMode: document.getElementById('wifiMode'),
        ipAddress: document.getElementById('ipAddress'),
        connectedSsid: document.getElementById('connectedSsid')
    };

    // Verify all elements are loaded
    let missingElements = [];
    for (let key in elements) {
        if (!elements[key]) {
            missingElements.push(key);
        }
    }

    if (missingElements.length > 0) {
        console.error('Missing DOM elements:', missingElements);
        return;
    }

    console.log('All DOM elements loaded successfully');

    // Setup event listeners
    elements.refreshBtn.addEventListener('click', updateTemperatures);
    elements.saveThermostatBtn.addEventListener('click', saveThermostat);
    elements.scanBtn.addEventListener('click', scanNetworks);
    elements.testWifiBtn.addEventListener('click', testWiFiConnection);
    elements.saveWifiBtn.addEventListener('click', saveWiFiConfig);
    elements.loadConfigBtn.addEventListener('click', loadConfig);
    elements.saveConfigBtn.addEventListener('click', saveConfig);

    console.log('Event listeners attached');

    // Initial data load
    updateTemperatures();
    loadThermostat();
    updateStatus();
    loadConfig();

    // Auto-refresh timers
    setInterval(updateTemperatures, 2000);
    setInterval(updateStatus, 10000);

    console.log('SmartThermo Web Interface ready!');
});
