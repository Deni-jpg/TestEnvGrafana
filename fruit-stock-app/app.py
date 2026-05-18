import random, time, secrets, logging
from flask import Flask, jsonify, session, request as flask_request
from prometheus_client import Counter, Histogram, generate_latest
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.sdk.resources import Resource

# ── OTel tracing ──────────────────────────────────────────────────────────────
_res  = Resource.create({"service.name": "fruit-stock-app", "service.version": "2.0.0"})
_prov = TracerProvider(resource=_res)
_prov.add_span_processor(
    BatchSpanProcessor(OTLPSpanExporter(endpoint="http://otelcol:4318/v1/traces")))
trace.set_tracer_provider(_prov)
tracer = trace.get_tracer("fruit-stock-app")

# ── Structured logging with trace-ID injection ────────────────────────────────
class _TraceCtxFilter(logging.Filter):
    def filter(self, record):
        ctx = trace.get_current_span().get_span_context()
        record.trace_id = format(ctx.trace_id, '032x') if ctx.is_valid else '0' * 32
        record.span_id  = format(ctx.span_id,  '016x') if ctx.is_valid else '0' * 16
        return True

_h = logging.StreamHandler()
_h.setFormatter(logging.Formatter(
    '%(asctime)s level=%(levelname)s service=fruit-stock-app '
    'traceID=%(trace_id)s spanID=%(span_id)s msg="%(message)s"'))
_h.addFilter(_TraceCtxFilter())
logging.root.handlers = [_h]
logging.root.setLevel(logging.INFO)
logger = logging.getLogger("fruit-stock-app")

# ── Flask ─────────────────────────────────────────────────────────────────────
app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
FlaskInstrumentor().instrument_app(app)

# ── Prometheus metrics ─────────────────────────────────────────────────────────
requests_total         = Counter('fruit_app_requests_total',        'Total requests',          ['method', 'endpoint'])
errors_total           = Counter('fruit_app_errors_total',          'HTTP errors',             ['endpoint', 'status'])
request_duration       = Histogram('fruit_app_request_duration_seconds', 'Latency',            ['endpoint'],
                                   buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0))
simulated_errors_total = Counter('fruit_app_simulated_errors_total', 'Simulated errors by type', ['error_type'])

# ── Data ──────────────────────────────────────────────────────────────────────
FRUITS = {
    "maca":     {"name": "Maçã Vermelha", "price": 2.50, "stock": 150, "image": "🍎", "desc": "Maçã fresca e crocante"},
    "banana":   {"name": "Banana",        "price": 1.20, "stock": 200, "image": "🍌", "desc": "Bananas doces"},
    "laranja":  {"name": "Laranja",       "price": 2.00, "stock": 180, "image": "🍊", "desc": "Laranjas suculentas"},
    "morango":  {"name": "Morango",       "price": 3.50, "stock": 100, "image": "🍓", "desc": "Morangos frescos"},
    "uva":      {"name": "Uva Verde",     "price": 2.80, "stock": 120, "image": "🍇", "desc": "Uvas frescas"},
    "melancia": {"name": "Melancia",      "price": 4.50, "stock":  60, "image": "🍉", "desc": "Melancia refrescante"},
}

CSS = "* { margin: 0; padding: 0; box-sizing: border-box; } body { font-family: 'Segoe UI'; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #333; min-height: 100vh; } header { background: white; box-shadow: 0 2px 10px rgba(0,0,0,0.1); padding: 1rem 2rem; display: flex; justify-content: space-between; align-items: center; } header h1 { color: #667eea; } nav { display: flex; gap: 1.5rem; } nav a { text-decoration: none; color: #667eea; font-weight: 500; } .cart-badge { background: #e74c3c; color: white; border-radius: 50%; padding: 0.2rem 0.5rem; font-size: 0.8rem; } .container { max-width: 1200px; margin: 2rem auto; padding: 0 1rem; } .hero { background: white; border-radius: 10px; padding: 2rem; text-align: center; box-shadow: 0 4px 20px rgba(0,0,0,0.1); margin-bottom: 2rem; } .products-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 2rem; } .product-card { background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.1); transition: transform 0.3s; } .product-card:hover { transform: translateY(-5px); } .product-image { font-size: 4rem; text-align: center; padding: 1rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); } .product-info { padding: 1.5rem; } .product-name { font-weight: bold; margin-bottom: 0.5rem; } .product-price { font-size: 1.5rem; color: #e74c3c; font-weight: bold; } .product-stock { color: #27ae60; } .quantity-input { width: 60px; padding: 0.5rem; border: 1px solid #ddd; border-radius: 5px; } .btn { padding: 0.75rem 1.5rem; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; text-decoration: none; display: inline-block; } .btn-primary { background: #667eea; color: white; } .btn-primary:hover { background: #764ba2; } .btn-danger { background: #e74c3c; color: white; } footer { background: white; padding: 2rem; text-align: center; margin-top: 2rem; }"

# ── Hooks ─────────────────────────────────────────────────────────────────────
@app.before_request
def before():
    flask_request.start_time = time.time()

@app.after_request
def after(response):
    dur = time.time() - flask_request.start_time
    ep  = flask_request.path
    requests_total.labels(method=flask_request.method, endpoint=ep).inc()
    request_duration.labels(endpoint=ep).observe(dur)
    if response.status_code >= 400:
        errors_total.labels(endpoint=ep, status=response.status_code).inc()
        logger.warning(f'method={flask_request.method} path={ep} status={response.status_code} duration_s={dur:.3f}')
    return response

def get_cart():
    if 'cart' not in session:
        session['cart'] = {}
    return session['cart']

# ── Existing routes ───────────────────────────────────────────────────────────
@app.route('/')
def home():
    cart = get_cart()
    cart_count = sum(cart.values())
    cart_badge = f'<span class="cart-badge">{cart_count}</span>' if cart_count > 0 else ''
    items = "".join([f'<div class="product-card"><div class="product-image">{f["image"]}</div><div class="product-info"><div class="product-name">{f["name"]}</div><p style="color:#666;font-size:0.9rem;margin-bottom:1rem">{f["desc"]}</p><div class="product-price">€{f["price"]:.2f}/kg</div><div class="product-stock">Stock: {f["stock"]} kg</div><form action="/add-to-cart/{k}" method="POST" style="display:flex;gap:0.5rem;margin-top:1rem"><input type="number" name="quantity" class="quantity-input" value="1" min="1" max="{f["stock"]}"><button type="submit" class="btn btn-primary">Adicionar</button></form></div></div>' for k, f in FRUITS.items()])
    return f"""<html><head><title>FruitStore</title><style>{CSS}</style></head><body><header><h1>🍎 FruitStore</h1><nav><a href="/">Loja</a><a href="/cart">🛒 Carrinho{cart_badge}</a><a href="/simulate" style="color:#e74c3c">🔴 Erros</a><a href="/stats">📊 Stats</a></nav></header><div class="container"><div class="hero"><h2>Bem-vindo à FruitStore! 🥗</h2><p>Frutas frescas entregues rapidamente</p></div><div class="products-grid">{items}</div></div><footer><p>&copy; 2026 FruitStore | <a href="/api/metrics" style="color:#667eea;">Métricas</a></p></footer></body></html>""", 200

@app.route('/add-to-cart/<k>', methods=['POST'])
def add_cart(k):
    if k not in FRUITS:
        return "Not found", 404
    qty = int(flask_request.form.get('quantity', 1))
    if qty <= 0 or qty > FRUITS[k]['stock']:
        return "Invalid", 400
    cart = get_cart()
    cart[k] = cart.get(k, 0) + qty
    session.modified = True
    return f"<script>window.location.href='/';alert('{qty}kg adicionado!');</script>", 200

@app.route('/cart')
def cart():
    c = get_cart()
    items = [(k, FRUITS[k], c[k]) for k in c if k in FRUITS]
    total = sum(FRUITS[k]['price'] * c[k] for k in c if k in FRUITS)
    items_html = "".join([f'<div style="display:flex;justify-content:space-between;padding:1rem;border-bottom:1px solid #eee"><div><div style="font-weight:bold">{f["name"]}</div><div>{q} kg</div></div><div style="color:#e74c3c;font-weight:bold">€{f["price"]*q:.2f}</div><form action="/remove/{k}" method="POST" style="display:inline"><button class="btn btn-danger" style="padding:0.5rem 1rem">Remover</button></form></div>' for k, f, q in items])
    return f"""<html><head><title>Carrinho</title><style>{CSS}</style></head><body><header><h1><a href="/" style="text-decoration:none;color:#667eea">🍎 FruitStore</a> - Carrinho</h1><nav><a href="/">Loja</a><a href="/simulate" style="color:#e74c3c">🔴 Erros</a></nav></header><div class="container" style="background:white;border-radius:10px;padding:2rem;box-shadow:0 4px 20px rgba(0,0,0,0.1)"><h2>🛒 Carrinho</h2>{'<div>'+items_html+'<div style="background:#f9f9f9;padding:1rem;border-radius:5px;margin-top:1.5rem"><div style="display:flex;justify-content:space-between;margin-bottom:0.5rem"><span>Subtotal:</span><span>€'+f'{total*0.9:.2f}'+'</span></div><div style="display:flex;justify-content:space-between;margin-bottom:0.5rem"><span>Entrega:</span><span>€3.50</span></div><div style="display:flex;justify-content:space-between;border-top:2px solid #ddd;padding-top:0.5rem;font-weight:bold;font-size:1.2rem"><span>Total:</span><span>€'+f'{total*0.9+3.50:.2f}'+'</span></div></div><div style="display:flex;gap:1rem;margin-top:1.5rem"><a href="/" class="btn" style="background:#95a5a6;color:white;flex:1;text-align:center">← Continuar</a><a href="/checkout" class="btn btn-primary" style="flex:1;text-align:center">Checkout →</a></div></div>' if items else '<div style="text-align:center;padding:3rem;color:#666"><p>Carrinho vazio</p><a href="/" class="btn btn-primary">Voltar</a></div>'}</div></body></html>""", 200

@app.route('/remove/<k>', methods=['POST'])
def remove(k):
    cart = get_cart()
    cart.pop(k, None)
    session.modified = True
    return '<script>window.location.href="/cart";</script>', 200

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    cart = get_cart()
    if not cart:
        return '<script>window.location.href="/cart";</script>', 302
    if flask_request.method == 'POST':
        time.sleep(0.5)
        session.pop('cart', None)
        return f'<html><head><style>{CSS}</style></head><body><div class="container" style="background:white;border-radius:10px;padding:2rem;max-width:500px;margin:50px auto;text-align:center"><h2 style="color:#27ae60">✅ Pedido Confirmado!</h2><p>Obrigado pela sua compra!</p><div style="background:#f9f9f9;padding:1rem;border-radius:5px;margin:1rem 0;font-family:monospace">Pedido #FR{random.randint(10000,99999)}</div><p>Será entregue em 24-48 horas.</p><a href="/" class="btn btn-primary" style="margin-top:1rem">← Voltar</a></div></body></html>', 200
    total = sum(FRUITS[k]['price'] * cart[k] for k in cart if k in FRUITS)
    return f'''<html><head><style>{CSS}</style></head><body><header><h1><a href="/" style="text-decoration:none;color:#667eea">🍎 FruitStore</a></h1></header><div class="container"><div style="background:white;border-radius:10px;padding:2rem;max-width:600px;margin:2rem auto;box-shadow:0 4px 20px rgba(0,0,0,0.1)"><h2>📋 Finalizar Pedido</h2><form method="POST"><div style="margin-bottom:1.5rem"><label style="display:block;font-weight:bold;margin-bottom:0.5rem">Nome</label><input type="text" name="name" required placeholder="João Silva" style="width:100%;padding:0.75rem;border:1px solid #ddd;border-radius:5px"></div><div style="margin-bottom:1.5rem"><label style="display:block;font-weight:bold;margin-bottom:0.5rem">Email</label><input type="email" name="email" required placeholder="joao@example.com" style="width:100%;padding:0.75rem;border:1px solid #ddd;border-radius:5px"></div><div style="margin-bottom:1.5rem"><label style="display:block;font-weight:bold;margin-bottom:0.5rem">Endereço</label><input type="text" name="address" required style="width:100%;padding:0.75rem;border:1px solid #ddd;border-radius:5px"></div><div style="background:#f9f9f9;padding:1rem;border-radius:5px;margin:1.5rem 0"><div style="display:flex;justify-content:space-between;font-weight:bold;font-size:1.2rem">Total a Pagar: <span>€{total*0.9+3.50:.2f}</span></div></div><div style="display:flex;gap:1rem;margin-top:1.5rem"><a href="/cart" class="btn" style="background:#95a5a6;color:white;flex:1;text-align:center">← Voltar</a><button type="submit" class="btn btn-primary" style="flex:1">Confirmar →</button></div></form></div></div></body></html>''', 200

@app.route('/stats')
def stats():
    return f'''<html><head><style>{CSS}</style></head><body><header><h1><a href="/" style="text-decoration:none;color:#667eea">🍎 FruitStore</a> - Stats</h1><nav><a href="/">Loja</a><a href="/cart">🛒</a><a href="/simulate" style="color:#e74c3c">🔴 Erros</a></nav></header><div class="container"><div style="display:grid;grid-template-columns:repeat(3,1fr);gap:1.5rem;margin-bottom:2rem">
    <div style="background:white;border-radius:10px;padding:1.5rem;box-shadow:0 4px 15px rgba(0,0,0,0.1)"><h3 style="color:#667eea">📊 Requisições</h3><div style="font-size:2rem;font-weight:bold">Grafana →</div><div style="color:#666;font-family:monospace">fruit_app_requests_total</div></div>
    <div style="background:white;border-radius:10px;padding:1.5rem;box-shadow:0 4px 15px rgba(0,0,0,0.1)"><h3 style="color:#667eea">❌ Erros</h3><div style="font-size:2rem;font-weight:bold">Grafana →</div><div style="color:#666;font-family:monospace">fruit_app_errors_total</div></div>
    <div style="background:white;border-radius:10px;padding:1.5rem;box-shadow:0 4px 15px rgba(0,0,0,0.1)"><h3 style="color:#667eea">⏱️ Latência</h3><div style="font-size:2rem;font-weight:bold">Grafana →</div><div style="color:#666;font-family:monospace">fruit_app_request_duration</div></div>
    </div><div style="background:white;border-radius:10px;padding:1.5rem;box-shadow:0 4px 15px rgba(0,0,0,0.1)"><h3>🔍 Monitorização</h3>
    <ul style="list-style:none"><li style="padding:0.75rem"><strong>Grafana:</strong> <a href="http://localhost:3000" target="_blank" style="color:#667eea">http://localhost:3000</a></li>
    <li style="padding:0.75rem"><strong>Prometheus:</strong> <a href="http://localhost:9090" target="_blank" style="color:#667eea">http://localhost:9090</a></li>
    <li style="padding:0.75rem"><strong>Métricas:</strong> <a href="/metrics" target="_blank" style="color:#667eea">/metrics</a></li>
    <li style="padding:0.75rem"><strong>Error Sim:</strong> <a href="/simulate" style="color:#e74c3c">/simulate</a></li></ul>
    <a href="/" class="btn btn-primary" style="margin-top:1rem">← Loja</a></div></div></body></html>''', 200

# ── Error Simulation ───────────────────────────────────────────────────────────
@app.route('/simulate')
def simulate_page():
    return f"""<html>
<head>
<title>Error Simulator — FruitStore</title>
<style>{CSS}</style>
<script>
async function fireError(type) {{
  const btn = document.getElementById('btn-' + type);
  const res = document.getElementById('res-' + type);
  btn.disabled = true;
  btn.textContent = '⏳ Gerando...';
  res.style.display = 'block';
  res.innerHTML = '<em style="color:#999">A chamar endpoint...</em>';
  try {{
    const r = await fetch('/simulate/' + type);
    const d = await r.json();
    const col = r.status >= 500 ? '#c0392b' : '#d35400';
    res.style.cssText = 'display:block;margin-top:1rem;padding:1rem;border-radius:8px;background:#fff5f5;border-left:4px solid '+col+';';
    res.innerHTML =
      '<strong style="color:'+col+'">HTTP ' + r.status + ' — ' + d.error + '</strong><br>' +
      '<span style="color:#555;font-size:0.9rem">' + d.details + '</span><br>' +
      '<span style="color:#27ae60;font-size:0.85rem">✓ Métrica incrementada · Log com traceID enviado · Trace exportado para Tempo</span>';
  }} catch(e) {{
    res.style.cssText = 'display:block;margin-top:1rem;padding:1rem;border-radius:8px;background:#fff5f5;border-left:4px solid #e74c3c;';
    res.innerHTML = '<span style="color:red">Erro de conexão: ' + e.message + '</span>';
  }} finally {{
    btn.disabled = false;
    btn.textContent = 'Gerar Erro';
  }}
}}
</script>
</head>
<body>
<header>
  <h1>🍎 FruitStore</h1>
  <nav><a href="/">Loja</a><a href="/cart">🛒</a><a href="/simulate" style="color:#e74c3c;font-weight:700">🔴 Erros</a><a href="/stats">📊 Stats</a></nav>
</header>
<div class="container">
  <div style="background:white;border-radius:12px;padding:2rem;box-shadow:0 4px 20px rgba(0,0,0,0.1)">

    <h2 style="margin-bottom:0.5rem">🔴 Error Simulator</h2>
    <p style="color:#666;margin-bottom:2rem">Gera erros reais com traces OpenTelemetry. Cada botão regista métricas em Prometheus, logs estruturados em Loki e traces em Tempo — visíveis no Grafana.</p>

    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:1.5rem;margin-bottom:2rem">

      <div style="border:2px solid #e74c3c;border-radius:10px;padding:1.5rem">
        <h3 style="color:#e74c3c;margin-bottom:0.5rem">🗄️ Database Timeout</h3>
        <p style="color:#555;font-size:0.9rem;margin-bottom:0.75rem">Query SQL que excede o timeout do connection pool. Simula latência de 2–3.5s antes do erro.</p>
        <div style="background:#fff5f5;padding:0.6rem 0.8rem;border-radius:5px;font-family:monospace;font-size:0.75rem;color:#c0392b;margin-bottom:1rem">
          error_type=database_timeout<br>HTTP 500 · span: db.query
        </div>
        <button id="btn-db-error" onclick="fireError('db-error')" class="btn btn-danger" style="width:100%">Gerar Erro</button>
        <div id="res-db-error" style="display:none"></div>
      </div>

      <div style="border:2px solid #e67e22;border-radius:10px;padding:1.5rem">
        <h3 style="color:#e67e22;margin-bottom:0.5rem">💳 Payment Gateway</h3>
        <p style="color:#555;font-size:0.9rem;margin-bottom:0.75rem">Gateway de pagamento Stripe indisponível. Serviço externo retorna 503 Service Unavailable.</p>
        <div style="background:#fff9f0;padding:0.6rem 0.8rem;border-radius:5px;font-family:monospace;font-size:0.75rem;color:#d35400;margin-bottom:1rem">
          error_type=payment_gateway<br>HTTP 503 · span: payment.charge
        </div>
        <button id="btn-payment-error" onclick="fireError('payment-error')" class="btn" style="width:100%;background:#e67e22;color:white">Gerar Erro</button>
        <div id="res-payment-error" style="display:none"></div>
      </div>

      <div style="border:2px solid #8e44ad;border-radius:10px;padding:1.5rem">
        <h3 style="color:#8e44ad;margin-bottom:0.5rem">💥 Logic Exception</h3>
        <p style="color:#555;font-size:0.9rem;margin-bottom:0.75rem">ZeroDivisionError em calculate_discount() quando o carrinho está vazio. Guard clause em falta.</p>
        <div style="background:#f9f5ff;padding:0.6rem 0.8rem;border-radius:5px;font-family:monospace;font-size:0.75rem;color:#6c3483;margin-bottom:1rem">
          error_type=unhandled_exception<br>HTTP 500 · span: checkout.calculate_discount
        </div>
        <button id="btn-logic-error" onclick="fireError('logic-error')" class="btn" style="width:100%;background:#8e44ad;color:white">Gerar Erro</button>
        <div id="res-logic-error" style="display:none"></div>
      </div>

    </div>

    <div style="background:#f0f4ff;border-radius:10px;padding:1.5rem">
      <h3 style="color:#667eea;margin-bottom:1rem">📊 Root Cause Analysis — Como usar</h3>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:1rem">
        <div>
          <strong>1. Métricas</strong>
          <p style="color:#555;font-size:0.85rem;margin-top:0.3rem">Grafana → <em>DevOps RCA</em><br><code>fruit_app_simulated_errors_total</code></p>
        </div>
        <div>
          <strong>2. Logs → Traces</strong>
          <p style="color:#555;font-size:0.85rem;margin-top:0.3rem">Explore → Loki<br>filtra <code>level=ERROR</code> → clica em <strong>TraceID</strong></p>
        </div>
        <div>
          <strong>3. Trace Detail</strong>
          <p style="color:#555;font-size:0.85rem;margin-top:0.3rem">Tempo mostra spans, atributos, stack trace e service graph</p>
        </div>
      </div>
      <div style="margin-top:1.2rem">
        <a href="http://localhost:3000" target="_blank" class="btn btn-primary" style="margin-right:0.75rem">Abrir Grafana →</a>
        <a href="/metrics" target="_blank" class="btn" style="background:#95a5a6;color:white">Ver Métricas</a>
      </div>
    </div>

  </div>
</div>
</body></html>""", 200


@app.route('/simulate/db-error')
def simulate_db_error():
    with tracer.start_as_current_span("db.query") as span:
        span.set_attribute("db.system", "postgresql")
        span.set_attribute("db.operation", "SELECT")
        span.set_attribute("db.statement", "SELECT * FROM orders WHERE user_id = ?")
        span.set_attribute("error.type", "database_timeout")
        delay = round(random.uniform(2.0, 3.5), 2)
        time.sleep(delay)
        err = TimeoutError(f"Connection pool exhausted after {delay}s")
        span.record_exception(err)
        span.set_status(trace.StatusCode.ERROR, str(err))
        logger.error(
            f'db=postgresql operation=SELECT query_duration_s={delay} '
            f'error=connection_pool_exhausted threshold_s=2.0')
        simulated_errors_total.labels(error_type="database_timeout").inc()
        return jsonify({
            "error": "Database Timeout",
            "error_type": "database_timeout",
            "details": f"Query exceeded {delay}s — connection pool exhausted. Trace registered in Tempo.",
        }), 500


@app.route('/simulate/payment-error')
def simulate_payment_error():
    with tracer.start_as_current_span("payment.charge") as span:
        span.set_attribute("rpc.service", "stripe")
        span.set_attribute("http.url", "https://api.stripe.com/v1/charges")
        span.set_attribute("http.method", "POST")
        span.set_attribute("error.type", "payment_gateway_failure")
        err = ConnectionError("Stripe API returned 503 Service Unavailable")
        span.record_exception(err)
        span.set_status(trace.StatusCode.ERROR, str(err))
        logger.error(
            'gateway=stripe endpoint=/v1/charges status_code=503 '
            'error=service_unavailable retry_after=30s')
        simulated_errors_total.labels(error_type="payment_gateway").inc()
        return jsonify({
            "error": "Payment Gateway Unavailable",
            "error_type": "payment_gateway",
            "details": "Stripe API returned 503 — Service Unavailable. Retry-After: 30s.",
        }), 503


@app.route('/simulate/logic-error')
def simulate_logic_error():
    with tracer.start_as_current_span("checkout.calculate_discount") as span:
        span.set_attribute("error.type", "unhandled_exception")
        span.set_attribute("checkout.cart_items", 0)
        try:
            items: list = []
            total = sum(item['price'] for item in items)
            _ = 100 / total
        except ZeroDivisionError as e:
            span.record_exception(e)
            span.set_status(trace.StatusCode.ERROR, str(e))
            logger.error(
                f'function=calculate_discount error=ZeroDivisionError '
                f'exception="{e}" hint=cart_is_empty')
            simulated_errors_total.labels(error_type="unhandled_exception").inc()
            return jsonify({
                "error": "Unhandled Exception",
                "error_type": "unhandled_exception",
                "details": "ZeroDivisionError in calculate_discount() — cart is empty. Missing guard clause.",
                "traceback": [
                    "File app.py in calculate_discount()",
                    "ZeroDivisionError: division by zero",
                ],
            }), 500

# ── Metrics & Health ──────────────────────────────────────────────────────────
@app.route('/metrics')
@app.route('/api/metrics')
def metrics_endpoint():
    return generate_latest(), 200

@app.route('/api/health')
def health():
    return jsonify({"status": "healthy", "version": "2.0.0"}), 200

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🍎 FruitStore v2 — Observability + Error Simulation")
    print("="*60)
    print("App:      http://localhost:5000")
    print("Erros:    http://localhost:5000/simulate")
    print("Grafana:  http://localhost:3000 (admin/admin)")
    print("="*60 + "\n")
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

#teste