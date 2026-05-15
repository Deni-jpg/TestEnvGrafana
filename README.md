<p align="center">
  <img src="logo.png" alt="Os Cigarrilhas" width="280"/>
</p>

<h1 align="center">Observability Test Environment</h1>

<p align="center">
  A complete observability stack running on Docker, built to monitor a demo Flask application (Fruit Stock App) with metrics, logs, traces and email alerting.
</p>

---

## What's inside

This project spins up **8 containers** that work together to collect, store, visualize and alert on telemetry data:

```
┌──────────────────┐        ┌──────────────────────────┐
│  Fruit Stock App │─OTLP──►│  OpenTelemetry Collector │
│     (Flask)      │        │                          │
│    :5000         │        │  traces  → Tempo         │
└──────────────────┘        │  metrics → Prometheus    │
                            │  logs    → Loki          │
┌──────────────────┐        └──────────────────────────┘
│    cAdvisor      │──scrape──► Prometheus
│    :8081         │               │
└──────────────────┘               │ alert rules
                                   ▼
                             Alertmanager ──► Email
                                :9093
                                   │
                                Grafana
                                 :3000
```

| Service | Port | What it does |
|---------|------|--------------|
| **Grafana** | 3000 | Dashboards and data visualization |
| **Prometheus** | 9090 | Metrics storage and alert evaluation |
| **Alertmanager** | 9093 | Alert routing and email notifications |
| **Loki** | 3100 | Log aggregation |
| **Tempo** | 3200 | Distributed tracing |
| **OTel Collector** | 4317 / 4318 | Telemetry pipeline (receives OTLP, routes to backends) |
| **cAdvisor** | 8081 | Container-level metrics (CPU, memory, network) |
| **Fruit Stock App** | 5000 | Demo Flask app with Prometheus instrumentation |

---

## Quick start

```bash
git clone https://github.com/Deni-jpg/TestEnvGrafana.git
cd TestEnvGrafana
git switch alertmanager
docker compose up -d
```

Open **http://localhost:3000** and log in with `admin` / `admin`.

Two dashboards are pre-loaded under **Dashboards → Demo**:
- **System Overview** — system metrics, container stats, logs
- **Website Metrics** — request rate, error rate and duration for the Fruit Stock App

---

## How the alert pipeline works

Alerting follows a three-step flow:

1. **Prometheus** evaluates rules defined in `prometheus/alert_rules.yml` every 15 seconds
2. When a condition is met, Prometheus fires the alert to **Alertmanager**
3. Alertmanager groups, deduplicates and sends an **email** via Gmail SMTP

### Configured alerts

| Alert | Fires when | Severity |
|-------|-----------|----------|
| FruitAppDown | The app stops responding for 30s | critical |
| HighErrorRate | Error rate > 0.1/s for 2 minutes | warning |
| HighLatency | p95 latency > 1s for 2 minutes | warning |

### Setting up email notifications

1. Enable [2-Step Verification](https://myaccount.google.com/signinoptions/two-step-verification) on your Google account
2. Create an [App Password](https://myaccount.google.com/apppasswords)
3. Edit `alertmanager/alertmanager.yml`:
```yaml
smtp_auth_username: 'your-email@gmail.com'
smtp_auth_password: 'xxxx xxxx xxxx xxxx'
```
4. Change the `to:` field in both receivers to your destination email

---

## The demo app

The **Fruit Stock App** is a simple Flask e-commerce page that sells fruits. It exposes Prometheus metrics at `/metrics` using the RED method:

- `fruit_app_requests_total` — total requests by method and endpoint
- `fruit_app_errors_total` — HTTP errors by endpoint and status code
- `fruit_app_request_duration_seconds` — request latency histogram

Visit **http://localhost:5000** to interact with the store and generate telemetry.

---

## Project structure

```
├── docker-compose.yml
├── prometheus/
│   ├── prometheus.yml          # scrape targets + alerting config
│   └── alert_rules.yml         # alert conditions
├── alertmanager/
│   └── alertmanager.yml        # email routing + SMTP config
├── otelcol/
│   └── otelcol.yml             # OTel pipelines (traces/metrics/logs)
├── loki/
│   └── loki.yml
├── tempo/
│   └── tempo.yml
├── grafana/
│   ├── provisioning/           # auto-configured datasources
│   └── dashboards/             # pre-loaded dashboards
└── fruit-stock-app/
    ├── Dockerfile
    └── app.py                  # Flask app with Prometheus metrics
```

---

## Useful links after startup

| What | URL |
|------|-----|
| Grafana | http://localhost:3000 |
| Prometheus targets | http://localhost:9090/targets |
| Prometheus alerts | http://localhost:9090/alerts |
| Alertmanager | http://localhost:9093 |
| Fruit Stock App | http://localhost:5000 |
| App metrics | http://localhost:5000/metrics |
| cAdvisor | http://localhost:8081 |

---

## Cleanup

```bash
docker compose down       # stop everything
docker compose down -v    # stop and delete all stored data
```
