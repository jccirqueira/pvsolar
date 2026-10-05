# pvSolar Gateway - Installation Guide

## Quick Start with Docker (Recommended)

### Prerequisites
- Docker Engine 20.10+
- Docker Compose 2.0+
- 2GB RAM minimum
- Network access to solar inverters

### Installation Steps

1. **Clone the repository**
```bash
git clone https://github.com/your-org/pvsolar-gateway.git
cd pvsolar-gateway/docker
```

2. **Create configuration**
```bash
# Copy example config
cp ../config/gateway.example.yaml ./config/gateway.yaml

# Edit configuration
nano ./config/gateway.yaml
```

3. **Generate certificates (for TLS)**
```bash
# Create certificate directory
mkdir -p certs

# Generate CA certificate
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout certs/ca.key -out certs/ca.crt \
    -subj "/CN=pvSolar CA"

# Generate server certificate
openssl req -nodes -newkey rsa:2048 \
    -keyout certs/server.key -out certs/server.csr \
    -subj "/CN=mqtt.pvsolar.local"

openssl x509 -req -in certs/server.csr -CA certs/ca.crt -CAkey certs/ca.key \
    -CAcreateserial -out certs/server.crt -days 365

# Generate client certificate
openssl req -nodes -newkey rsa:2048 \
    -keyout certs/client.key -out certs/client.csr \
    -subj "/CN=pvsolar-gateway-001"

openssl x509 -req -in certs/client.csr -CA certs/ca.crt -CAkey certs/ca.key \
    -CAcreateserial -out certs/client.crt -days 365
```

4. **Start the stack**
```bash
docker-compose up -d
```

5. **Verify installation**
```bash
# Check services
docker-compose ps

# View logs
docker-compose logs -f pvsolar-gateway

# Access web dashboard
open http://localhost:5000

# Access Grafana
open http://localhost:3000
```

## Manual Installation (Linux)

### Prerequisites
- Python 3.9+
- pip
- SQLite3
- Modbus TCP access to inverters

### Installation Steps

1. **Install system dependencies**
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip python3-venv sqlite3

# CentOS/RHEL
sudo yum install python3 python3-pip sqlite
```

2. **Create virtual environment**
```bash
python3 -m venv venv
source venv/bin/activate
```

3. **Install Python dependencies**
```bash
pip install -r requirements.txt
```

4. **Create directories**
```bash
sudo mkdir -p /etc/pvsolar/certs
sudo mkdir -p /var/lib/pvsolar
sudo mkdir -p /var/log/pvsolar
```

5. **Install configuration**
```bash
sudo cp config/gateway.example.yaml /etc/pvsolar/gateway.yaml
sudo nano /etc/pvsolar/gateway.yaml
```

6. **Create systemd service**
```bash
sudo tee /etc/systemd/system/pvsolar.service << EOF
[Unit]
Description=pvSolar Gateway
After=network.target

[Service]
Type=simple
User=pvsolar
Group=pvsolar
WorkingDirectory=/opt/pvsolar
ExecStart=/opt/pvsolar/venv/bin/python -m pvsolar -c /etc/pvsolar/gateway.yaml
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable pvsolar
sudo systemctl start pvsolar
```

7. **Check status**
```bash
sudo systemctl status pvsolar
sudo journalctl -u pvsolar -f
```

## Configuration

### Gateway Configuration

Edit `/etc/pvsolar/gateway.yaml`:

```yaml
gateway:
  name: "my-solar-site"
  location: "My Location"
  timezone: "America/Sao_Paulo"

mqtt:
  broker: "your-mqtt-broker.com"
  port: 8883
  client_id: "pvsolar-gateway-001"
  tls:
    enabled: true
    ca_cert: "/etc/pvsolar/certs/ca.crt"
    client_cert: "/etc/pvsolar/certs/client.crt"
    client_key: "/etc/pvsolar/certs/client.key"

inverters:
  - id: "inv-001"
    name: "My Inverter"
    driver: "sunspec"  # or fronius, growatt, sma, huawei
    connection:
      host: "192.168.1.100"
      port: 502
      unit_id: 1
```

### Inverter Drivers

| Driver | Protocol | Supported Brands |
|--------|----------|------------------|
| sunspec | SunSpec Modbus | IEEE 1547-2018 compliant |
| fronius | SunSpec + Extensions | Fronius GEN24, Tauro |
| growatt | Modbus RTU/TCP | MIN, MOD, MIX, SPA, SPH |
| sma | SunSpec + SMA Profile | Sunny Boy, Tripower |
| huawei | Modbus RTU/TCP | SUN2000 series |

## Troubleshooting

### Common Issues

1. **Cannot connect to inverter**
```bash
# Test Modbus connection
pymodbusTCP --host 192.168.1.100 --port 502

# Check network
ping 192.168.1.100
```

2. **MQTT connection failed**
```bash
# Test MQTT connection
mosquitto_sub -h broker.com -p 8883 --cafile ca.crt \
    --cert client.crt --key client.key -t "test"

# Check certificates
openssl s_client -connect broker.com:8883
```

3. **Service won't start**
```bash
# Check logs
sudo journalctl -u pvsolar -n 100

# Validate configuration
python -c "from pvsolar.core.config import load_config; load_config('/etc/pvsolar/gateway.yaml')"
```

## Support

- **Documentation:** https://docs.pvsolar.io
- **Issues:** https://github.com/your-org/pvsolar-gateway/issues
- **Email:** support@pvsolar.io
