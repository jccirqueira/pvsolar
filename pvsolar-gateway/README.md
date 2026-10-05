# pvSolar Gateway

**Enterprise-Grade Solar Inverter Monitoring Gateway**

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

pvSolar Gateway é um gateway profissional de monitoramento de inversores solares com integração MQTT e cloud. Projetado para ambientes industriais, oferece suporte completo a inversores via SunSpec Modbus (IEEE 1547-2018) e protocolos específicos de fabricantes.

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            pvSolar Gateway                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐        │
│  │   SunSpec   │  │   Fronius   │  │   Growatt   │  │  SMA/Huawei │        │
│  │   Modbus    │  │   Modbus    │  │   Modbus    │  │   Modbus    │        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘        │
│         │                │                │                │                │
│         └────────────────┼────────────────┼────────────────┘                │
│                          ▼                                                   │
│                ┌─────────────────┐                                          │
│                │  Data Processor │                                          │
│                │  (Normalization)│                                          │
│                └────────┬────────┘                                          │
│                         │                                                   │
│         ┌───────────────┼───────────────┐                                  │
│         ▼               ▼               ▼                                  │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐                          │
│  │ Edge Store  │ │ MQTT Client │ │  pvbrowser  │                          │
│  │ (SQLite)    │ │ (TLS 1.3)   │ │  Binder     │                          │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘                          │
│         │               │               │                                   │
│         │         ┌─────┴─────┐         │                                   │
│         │         ▼           ▼         │                                   │
│         │  ┌─────────────┐ ┌─────────────┐                                 │
│         │  │  AWS IoT    │ │ Azure IoT   │                                 │
│         │  │  Core       │ │ Hub         │                                 │
│         │  └─────────────┘ └─────────────┘                                 │
│         │                                                                   │
│         └──────────────────────────────────────────────────────────────────│
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## ✨ Features

### Core (Open Source - GPLv3)
- ✅ Suporte SunSpec Modbus (IEEE 1547-2018)
- ✅ Drivers para inversores: Fronius, Growatt, SMA, Huawei
- ✅ MQTT client com TLS 1.2/1.3
- ✅ Edge computing com store-and-forward (SQLite)
- ✅ Dashboard web para monitoramento
- ✅ Configuração via YAML
- ✅ Containerização Docker

### Premium (Comercial)
- 🔒 Suporte OPC UA
- 🔒 Integração AWS IoT Core com mTLS
- 🔒 Integração Azure IoT Hub
- 🔒 Relatórios de performance (PR, PR10, PR100)
- 🔒 Suporte a múltiplos sites
- 🔒 Alertas via Telegram/WhatsApp/SMS
- 🔒 Suporte técnico 24/7
- 🔒 Certificação de conformidade

## 🚀 Quick Start

### Pré-requisitos
- Python 3.9+
- pip

### Instalação

```bash
# Clonar repositório
git clone https://github.com/your-org/pvsolar-gateway.git
cd pvsolar-gateway

# Instalar dependências
pip install -r requirements.txt

# Configurar
cp config/gateway.example.yaml config/gateway.yaml
# Editar config/gateway.yaml

# Executar
python -m pvsolar
```

### Docker

```bash
# Build
docker build -t pvsolar-gateway .

# Executar
docker run -d \
  -v $(pwd)/config:/app/config \
  -p 5000:5000 \
  pvsolar-gateway
```

## 📁 Estrutura do Projeto

```
pvsolar-gateway/
├── src/
│   ├── core/                    # Core do gateway
│   │   ├── __init__.py
│   │   ├── gateway.py          # Gateway principal
│   │   ├── config.py           # Gerenciamento de configuração
│   │   └── metrics.py          # Métricas e saúde
│   ├── mqtt/
│   │   ├── __init__.py
│   │   ├── client.py           # Cliente MQTT com TLS
│   │   └── security.py         # Certificados e autenticação
│   ├── drivers/
│   │   ├── sunspec/            # Driver SunSpec Modbus
│   │   ├── fronius/            # Driver Fronius específico
│   │   ├── growatt/            # Driver Growatt específico
│   │   ├── sma/                # Driver SMA específico
│   │   └── huawei/             # Driver Huawei específico
│   ├── cloud/
│   │   ├── aws/                # AWS IoT Core
│   │   ├── azure/              # Azure IoT Hub
│   │   └── mqtt-local/         # MQTT broker local
│   ├── edge/
│   │   ├── __init__.py
│   │   ├── store.py            # SQLite store-and-forward
│   │   └── processor.py        # Processamento edge
│   ├── pvbinder/
│   │   ├── __init__.py
│   │   └── bridge.py           # Integração com pvbrowser
│   └── web/
│       ├── app.py              # Dashboard Flask/FastAPI
│       ├── css/
│       └── js/
├── config/
│   ├── gateway.yaml            # Configuração local (dev)
│   └── gateway.example.yaml    # Configuração de exemplo
├── examples/
│   └── pvbrowser_example.py    # Integração com o protocolo pvBrowser
├── tests/
├── docker/
├── requirements.txt
├── Resumo.txt
├── Manual.html
├── INSTALL.md
└── LICENSE
```

## 🔧 Configuração

### gateway.yaml

```yaml
# pvSolar Gateway Configuration
gateway:
  name: "solar-site-001"
  location: "São Paulo, Brazil"
  timezone: "America/Sao_Paulo"

# MQTT Configuration
mqtt:
  broker: "localhost"
  port: 8883
  use_tls: true
  ca_cert: "/etc/pvsolar/certs/ca.crt"
  client_cert: "/etc/pvsolar/certs/client.crt"
  client_key: "/etc/pvsolar/certs/client.key"
  client_id: "pvsolar-gateway-001"
  topics:
    publish: "pvsolar/{site_id}/telemetry"
    command: "pvsolar/{site_id}/command"
    status: "pvsolar/{site_id}/status"
  qos: 1
  retain: true
  heartbeat_interval: 30

# Inverters
inverters:
  - id: "inv-001"
    name: "Fronius GEN24 8.0"
    driver: "fronius"
    connection:
      type: "modbus_tcp"
      host: "192.168.1.100"
      port: 502
      unit_id: 1
    polling_interval: 5
    registers:
      - name: "ac_power"
        address: 40083
        type: "uint32"
        scale: 0.001
        unit: "kW"
      - name: "ac_voltage_l1"
        address: 40079
        type: "uint16"
        scale: 0.1
        unit: "V"
      - name: "daily_energy"
        address: 40089
        type: "uint32"
        scale: 0.001
        unit: "kWh"

  - id: "inv-002"
    name: "Growatt MIN 5000TL-X"
    driver: "growatt"
    connection:
      type: "modbus_tcp"
      host: "192.168.1.101"
      port: 502
      unit_id: 1
    polling_interval: 5

# Cloud Integration (Premium)
cloud:
  aws_iot:
    enabled: false
    endpoint: "xxxxxxxxx.iot.us-east-1.amazonaws.com"
    cert_path: "/etc/pvsolar/certs/aws/"
    thing_name: "pvsolar-gateway-001"

  azure_iot:
    enabled: false
    connection_string: "HostName=xxx;DeviceId=xxx;SharedAccessKey=xxx"

  mqtt_local:
    enabled: true
    broker: "localhost"
    port: 1883

# Edge Computing
edge:
  store_and_forward:
    enabled: true
    database: "/var/lib/pvsolar/edge.db"
    max_buffer_hours: 72
    sync_interval: 30

  processing:
    enabled: true
    aggregation: "1min"
    calculators:
      - "performance_ratio"
      - "availability"
      - "energy_forecast"

# pvbrowser Integration
pvbrowser:
  enabled: true
  socket_port: 5050
  shared_memory: true

# Web Dashboard
web:
  enabled: true
  port: 5000
  auth:
    enabled: true
    username: "admin"
    password_hash: "bcrypt_hash_here"

# Alerts (Premium)
alerts:
  enabled: false
  channels:
    telegram:
      bot_token: ""
      chat_id: ""
    whatsapp:
      enabled: false
    sms:
      enabled: false

# Logging
logging:
  level: "INFO"
  file: "/var/log/pvsolar/gateway.log"
  max_size_mb: 100
  backup_count: 10
```

## 📊 Protocolos Suportados

### SunSpec Modbus (IEEE 1547-2018)
- Common Model (ID 1)
- Inverter Model (ID 101-113)
- MPPT Model (ID 160)
- Storage Model (ID 124)

### Fabricantes Específicos
| Fabricante | Modelos | Protocolo | Status |
|------------|---------|-----------|--------|
| Fronius | GEN24, Tauro, SnapINverter | SunSpec + Extensões | ✅ |
| Growatt | MIN, MOD, MIX, SPA, SPH | Modbus RTU/TCP | ✅ |
| SMA | Sunny Boy, Sunny Tripower | SunSpec + SMA Profile | ✅ |
| Huawei | SUN2000 | Modbus RTU/TCP | ✅ |

## 🛡️ Segurança

- TLS 1.2/1.3 para todas as conexões MQTT
- mTLS (mutual TLS) para autenticação de dispositivos
- ACLs por tópico MQTT
- Certificados X.509 por dispositivo
- Armazenamento seguro de credenciais
- Rate limiting e detecção de anomalias

## 📈 Métricas

O gateway expõe métricas via Prometheus:
- `pvsolar_inverter_power_watts` - Potência atual
- `pvsolar_inverter_energy_total_wh` - Energia total
- `pvsolar_inverter_efficiency` - Eficiência
- `pvsolar_mqtt_messages_sent` - Mensagens MQTT enviadas
- `pvsolar_edge_buffer_size` - Tamanho do buffer edge

## 🧪 Testes

```bash
# Suíte completa (403 testes) com cobertura
python -m pytest tests/ -q --cov=src --cov-report=term
```

O piso de cobertura é o do `.coveragerc` (ratchet — nunca regredir).

## 📦 Deploy

O gateway é implantado como parte do stack do ecossistema (compose da raiz —
16 serviços com Caddy/HTTPS):

```bash
# na raiz do repositório
docker compose up -d --build
```

Para VM/VPS, siga o
[Guia Completo de Instalação](../Guia%20Completo%20de%20Instalacao%20do%20Ecossistema%20pvSolar.html)
(seções Docker e VPS) e o [INSTALL.md](INSTALL.md) deste projeto.

## 📚 Documentação

- [Resumo.txt](Resumo.txt) — visão técnica: arquitetura, módulos, problemas resolvidos e testes
- [Manual.html](Manual.html) — manual profissional: API, configuração e troubleshooting
- [INSTALL.md](INSTALL.md) — instalação e implantação do serviço
- [Guia do ecossistema](../Guia%20Completo%20de%20Instalacao%20do%20Ecossistema%20pvSolar.html) — stack completa (13 projetos)
- [README raiz](../README.md) — visão geral do ecossistema pvSolar

## 🤝 Contribuição

Contribuições são bem-vindas: rode a suíte completa
(`python -m pytest tests/ -q`) e o lint (`ruff check .`), depois abra um
Pull Request contra `main` — a CI exige todos os checks verdes.

## 📄 Licença

**GPLv3** — [LICENSE](LICENSE)

## 📞 Suporte

- **Community:** [GitHub Issues](https://github.com/your-org/pvsolar-gateway/issues)
- **Premium Support:** support@pvsolar.io
- **Documentation:** [docs.pvsolar.io](https://docs.pvsolar.io)

## 🙏 Agradecimentos

- [pvbrowser](https://pvbrowser.de/) - Framework SCADA open source
- [SunSpec Alliance](https://sunspec.org/) - Padrões Modbus para energias renováveis
- [Eclipse Mosquitto](https://mosquitto.org/) - Broker MQTT
- [Fronius](https://www.fronius.com/) - Documentação Modbus
- [Growatt](https://www.growatt.com/) - Documentação Modbus

---

** pvSolar Gateway ** - Monitoramento Solar Profissional para Ambientes Industriais
