# Ecossistema pvSolar

[![CI](https://github.com/jccirqueira/pvsolar/actions/workflows/ci.yml/badge.svg)](https://github.com/jccirqueira/pvsolar/actions/workflows/ci.yml)
[![Licença GPLv3](https://img.shields.io/badge/licen%C3%A7a-GPLv3-blue.svg)](LICENSE)

Suíte completa de monitoramento, SCADA e analytics para usinas solares — 13
projetos interligados, com API REST, autenticação multi-tenant, agendamento,
relatórios PDF/Excel, alertas multi-canal, gêmeo digital e deploy
containerizado pronto para VPS com HTTPS automático.

**Qualidade:** 1135 testes automatizados (12 suítes pytest + jest), cobertura de
código com piso por projeto (gate na CI), lint contínuo (ruff + ESLint na CI e
pre-commit local), validadores estruturais de compose/documentação, CI com
build real das 13 imagens Docker + **smoke-test E2E** (stack completa sobe no
ar da CI com probes HTTP e healthchecks) e Dependabot semanal.

---

## Serviços

| Serviço | Porta | Descrição |
|---|---|---|
| pvsolar-gateway | 8000 (9090 metrics) | Ingestão MQTT + normalização de telemetria |
| pvsolar-analytics | 8001 | ML / anomaly detection em séries temporais |
| pvsolar-reports | 8002 | Relatórios PDF/Excel com agendamento e e-mail |
| pvsolar-fleet | 8003 | Gestão de frota de usinas + benchmarking |
| pvsolar-alert | 8004 | Alertas multi-canal (e-mail, webhook, escalonamento) |
| pvsolar-grid | 8005 | Integração com rede elétrica / mercados |
| pvsolar-twin | 8006 | Gêmeo digital (simulação de geração) |
| pvsolar-auth | 8007 | Autenticação, usuários, tenantes, chaves de API |
| pvsolar-backup | 8008 | Backup/restauração agendado |
| pvsolar-scheduler | 8009 | Agendador de tarefas do ecossistema |
| pvsolar-exporter | 8010 | Exportador de métricas (Prometheus push/gateway) |
| pvsolar-scada | 5000 (TCP) | HMI/SCADA — protocolo TCP do pvBrowser |
| pvsolar-web | 3001 | Frontend Next.js 14 + Tailwind |

Infraestrutura do stack Docker: **PostgreSQL 17** (5432), **Mosquitto** (1883),
**Caddy** (80/443 — porta única de entrada com roteamento por caminho).

---

## Início rápido

### Docker (recomendado — produção/VPS)

```bash
cp .env.example .env      # opcional: todos os valores têm default
docker compose up -d --build
# acesso: http://localhost  (Caddy)
# login:  admin / admin123 (criado automaticamente no 1º start)
```

Com `DOMAIN=seu-dominio.com` no `.env`, o Caddy emite HTTPS (Let's Encrypt)
automaticamente na primeira subida.

### Local (Windows — desenvolvimento)

Siga o **[Guia Completo de Instalação](Guia%20Completo%20de%20Instalacao%20do%20Ecossistema%20pvSolar.html)**
(Passos 1–5): estrutura → testes → config → PostgreSQL → execução.

```powershell
# exemplo: subir um servico
cd pvsolar-auth
venv\Scripts\activate
uvicorn src.api.app:app --host 0.0.0.0 --port 8007
```

---

## Testes

| Stack | Comando | Total |
|---|---|---|
| 12 projetos Python | `python -m pytest tests/ -q` (em cada projeto) | 1085 |
| pvsolar-web | `npm test` | 50 |
| **Total** | | **1135** |

A CI roda tudo com cobertura: `pytest --cov=src` falha abaixo do piso do
`.coveragerc` de cada projeto (ratchet — nunca regredir, meta ≥80%) e o jest
aplica `coverageThreshold` global (≥90% stmts).

Validadores estruturais (raiz do repositório):

```bash
pip install pyyaml
python docker/validate_compose.py    # compose, builds, portas, initdb
python docker/validate_guide.py      # HTML do guia (tags, âncoras, comandos)
python docker/validate_manuals.py    # 13 manuals (tags, âncoras, entrypoints)
```

---

## Lint

Config única em `ruff.toml` (raiz) para os 12 projetos Python; ESLint com
`next/core-web-vitals` no web. A CI roda ambos no job **Lint**.

```bash
ruff check .                     # Python (zero violações)
cd pvsolar-web && npm run lint   # ESLint

# hooks opcionais em cada commit:
pip install pre-commit && pre-commit install
```

---

## Estrutura

```
PvBrowser/
├── docker-compose.yml        # stack única: 16 serviços
├── .env.example              # variáveis de ambiente documentadas
├── ruff.toml                 # config única de lint Python
├── .pre-commit-config.yaml   # hooks locais (ruff + higiene)
├── docker/
│   ├── initdb/               # criação dos 5 bancos na 1ª subida
│   ├── Caddyfile             # roteamento /auth/*, /gateway/*, ...
│   ├── config/               # variantes de config p/ rede interna
│   ├── mosquitto.conf
│   └── validate_*.py         # validadores (compose, guia, manuals)
├── .github/
│   ├── workflows/ci.yml      # CI: lint + validadores + testes + build/smoke
│   └── dependabot.yml        # atualizações semanais (pip, npm, actions)
├── Guia Completo ... .html   # guia de instalação completo
└── pvsolar-*/                # 13 projetos (Resumo.txt + Manual.html cada)
```

Cada projeto contém `Resumo.txt` (visão técnica) e `Manual.html` (manual
profissional com API, configuração e troubleshooting).

---

## Persistência

- **Auth** e **Scheduler** persistem em PostgreSQL (write-through + hydration
  no startup); sem banco configurado funcionam em memória.
- **Config** segue precedência: variável `PVSOLAR_CONFIG` → `config/<nome>.yaml`
  → defaults do código.
- Testes rodam em SQLite por padrão (sem dependência externa).

---

## CI

`.github/workflows/ci.yml` roda em cada push/PR:

1. **Validadores** — compose + guia + 13 manuals;
2. **pytest** — matriz com os 12 projetos Python (Windows runner, ambiente
   validado);
3. **jest** — pvsolar-web (Node 20);
4. **Docker build** — `docker compose config` + build das 14 imagens
   (validação real dos Dockerfiles).

---

## Licença

GPLv3 — ver `Resumo.txt` de cada projeto.
