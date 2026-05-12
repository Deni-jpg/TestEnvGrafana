# Observability Stack — Grafana + Prometheus + Loki + Tempo + OTel Collector

## Arquitetura

```
                    ┌─────────────────────────────┐
  Apps / Serviços   │   OpenTelemetry Collector    │
  ──OTLP──────────► │                             │
                    │  receivers:                  │
  Node Exporter     │    otlp (gRPC :4317)         │
  ──scrape──────►   │    otlp (HTTP :4318)         │
                    │    filelog/containers        │
  cAdvisor          │    prometheus (interno)      │
  ──scrape──────►   │                             │
                    │  exporters:                  │
                    │    traces  → Tempo           │
                    │    metrics → Prometheus      │
                    │    logs    → Loki            │
                    └─────────────────────────────┘
                              │
                 ┌────────────┼────────────┐
                 ▼            ▼            ▼
              Tempo      Prometheus       Loki
                 └────────────┴────────────┘
                              │
                           Grafana
                        http://localhost:3000
```

## Serviços

| Serviço           | Porta  | Função                                           |
|-------------------|--------|--------------------------------------------------|
| Grafana           | 3000   | Dashboards e visualização                        |
| Prometheus        | 9090   | Armazenamento de métricas (TSDB)                 |
| Node Exporter     | 9100   | Métricas do sistema (CPU, RAM, disco, rede)      |
| cAdvisor          | 8080   | Métricas dos containers Docker                   |
| Loki              | 3100   | Armazenamento de logs                            |
| Tempo             | 3200   | Armazenamento de traces distribuídos             |
| OTel Collector    | 4317/4318 | Ponto de entrada único para toda a telemetria |

## Porquê OTel Collector em vez de Promtail?

O **Promtail** só recolhe logs. O **OTel Collector** é um pipeline de telemetria completo:
- Recebe **traces, métricas e logs** num único endpoint (OTLP)
- As tuas apps só precisam de enviar para um sítio: `localhost:4317`
- O Collector decide para onde roteia cada tipo de dado
- É o standard da indústria (CNCF), agnóstico de vendor

## Iniciar

```bash
cd observability
docker compose up -d
docker compose ps   # verificar se está tudo healthy
```

Aguardar ~30 segundos e abrir: **http://localhost:3000**

- Login: `admin` / `admin123`
- Dashboard pré-carregado: **Dashboards → Demo → Sistema — CPU, Memória, Disco**

## Enviar traces da tua app

Qualquer app com SDK OpenTelemetry envia para:
- gRPC: `http://localhost:4317`
- HTTP: `http://localhost:4318`

Exemplo com Python:
```bash
pip install opentelemetry-distro opentelemetry-exporter-otlp
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
export OTEL_SERVICE_NAME=minha-app
```

Exemplo com Node.js:
```bash
npm install @opentelemetry/sdk-node @opentelemetry/exporter-trace-otlp-http
# OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
```

## Ver logs do OTel Collector

```bash
docker compose logs otelcol -f
```

## Parar

```bash
docker compose down        # para e remove containers
docker compose down -v     # apaga também os volumes (dados)
```
