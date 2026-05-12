Observability Stack --- Grafana + Prometheus + Loki + Tempo + OTel Collector
==========================================================================

Arquitetura Simplificada
------------------------

Nesta configuração, o **OpenTelemetry Collector** é o único componente que toca no sistema operacional e nos containers, eliminando a necessidade de agentes externos como Node Exporter ou cAdvisor.

Fragmento do código

```
graph TD
    Apps[Aplicações / Serviços] -- OTLP --> OTel[OTel Collector]
    Host[Métricas do Host] -- Interno --> OTel
    Logs[Logs de Containers] -- Ingestão --> OTel

    OTel -- Métricas --> Prom[Prometheus]
    OTel -- Logs --> Loki[Loki]
    OTel -- Traces --> Tempo[Tempo]

    Prom -- Visualização --> Grafana[Grafana]
    Loki -- Visualização --> Grafana
    Tempo -- Visualização --> Grafana

```

Inventário de Serviços
----------------------

| **Serviço** | **Porta** | **Função** |
| --- | --- | --- |
| **Grafana** | 3000 | Visualização de dados e Dashboards |
| **Prometheus** | 9090 | Banco de dados para métricas (TSDB) |
| **OTel Collector** | 4317/18 | Ponto central: Coleta métricas de host e logs |
| **Loki** | 3100 | Banco de dados para logs |
| **Tempo** | 3200 | Banco de dados para traces distribuídos |

Vantagens desta Configuração
----------------------------

1.  **Agente Único:** Menos containers rodando em background. O OTel Collector resolve métricas de hardware e logs de software.

2.  **Consistência:** Todas as métricas de infraestrutura usam o prefixo `system_` (padrão OTLP), facilitando a criação de alertas universais.

3.  **Segurança:** Apenas um serviço (OTel) precisa de permissões de leitura nos volumes do Docker e `/proc`.

Gestão da Stack
---------------

### Iniciar

Bash

```
docker compose up -d
docker compose ps

```

### Dashboard de Sistema

Certifique-se de usar o Dashboard com queries baseadas em `system_`.

-   **Exemplo de CPU:** `system_cpu_time_seconds_total`

-   **Exemplo de RAM:** `system_memory_usage_bytes`

### Enviar Telemetria da sua App

Aponte o SDK da sua aplicação para:

-   **gRPC (Preferencial):** `http://localhost:4317`

-   **HTTP/JSON:** `http://localhost:4318`

Troubleshooting
---------------

-   **Verificar se as métricas do Host estão sendo geradas:**

    Bash

    ```
    curl http://localhost:8889/metrics | grep system_

    ```

-   **Verificar se os logs estão chegando no Loki:**

    Vá ao **Grafana -> Explore**, selecione o datasource **Loki** e use a query `{job="otel-collector"}` ou `{container_name=~".+"}`.

-   **Limpeza de dados (Reset):**

    Bash

    ```
    docker compose down -v
    ```
