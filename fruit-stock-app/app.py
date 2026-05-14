import random, time, secrets, os
from flask import Flask, jsonify, render_template_string, session, request as flask_request
from prometheus_client import Counter, Histogram, generate_latest

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

# RED Metrics
requests_total = Counter('fruit_app_requests_total', 'Total de requisições', ['method', 'endpoint'])
errors_total = Counter('fruit_app_errors_total', 'Total de erros HTTP', ['endpoint', 'status'])
request_duration = Histogram('fruit_app_request_duration_seconds', 'Latência (s)', ['endpoint'], buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0))

FRUITS = {"maca": {"name": "Maçã Vermelha", "price": 2.50, "stock": 150, "image": "🍎", "desc": "Maçã fresca e crocante"},
          "banana": {"name": "Banana", "price": 1.20, "stock": 200, "image": "🍌", "desc": "Bananas doces"},
          "laranja": {"name": "Laranja", "price": 2.00, "stock": 180, "image": "🍊", "desc": "Laranjas suculentas"},
          "morango": {"name": "Morango", "price": 3.50, "stock": 100, "image": "🍓", "desc": "Morangos frescos"},
          "uva": {"name": "Uva Verde", "price": 2.80, "stock": 120, "image": "🍇", "desc": "Uvas frescas"},
          "melancia": {"name": "Melancia", "price": 4.50, "stock": 60, "image": "🍉", "desc": "Melancia refrescante"}}

CSS = "* { margin: 0; padding: 0; box-sizing: border-box; } body { font-family: 'Segoe UI'; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #333; min-height: 100vh; } header { background: white; box-shadow: 0 2px 10px rgba(0,0,0,0.1); padding: 1rem 2rem; display: flex; justify-content: space-between; align-items: center; } header h1 { color: #667eea; } nav { display: flex; gap: 1.5rem; } nav a { text-decoration: none; color: #667eea; font-weight: 500; } .cart-badge { background: #e74c3c; color: white; border-radius: 50%; padding: 0.2rem 0.5rem; font-size: 0.8rem; } .container { max-width: 1200px; margin: 2rem auto; padding: 0 1rem; } .hero { background: white; border-radius: 10px; padding: 2rem; text-align: center; box-shadow: 0 4px 20px rgba(0,0,0,0.1); margin-bottom: 2rem; } .products-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 2rem; } .product-card { background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 4px 15px rgba(0,0,0,0.1); transition: transform 0.3s; } .product-card:hover { transform: translateY(-5px); } .product-image { font-size: 4rem; text-align: center; padding: 1rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); } .product-info { padding: 1.5rem; } .product-name { font-weight: bold; margin-bottom: 0.5rem; } .product-price { font-size: 1.5rem; color: #e74c3c; font-weight: bold; } .product-stock { color: #27ae60; } .quantity-input { width: 60px; padding: 0.5rem; border: 1px solid #ddd; border-radius: 5px; } .btn { padding: 0.75rem 1.5rem; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; text-decoration: none; display: inline-block; } .btn-primary { background: #667eea; color: white; } .btn-primary:hover { background: #764ba2; } .btn-danger { background: #e74c3c; color: white; } footer { background: white; padding: 2rem; text-align: center; margin-top: 2rem; }"


def _logo_prefix():
    # Use static/logo.png if present in the app folder, otherwise fallback to an emoji
    path = os.path.join(os.path.dirname(__file__), 'static', 'logo.png')
    if os.path.exists(path):
        return '<img src="/static/logo.png" alt="logo" style="height:48px;margin-right:12px;vertical-align:middle">'
    return '🍎'

@app.before_request
def before():
    flask_request.start_time = time.time()

@app.after_request
def after(response):
    duration = time.time() - flask_request.start_time
    requests_total.labels(method=flask_request.method, endpoint=flask_request.path).inc()
    request_duration.labels(endpoint=flask_request.path).observe(duration)
    if response.status_code >= 400:
        errors_total.labels(endpoint=flask_request.path, status=response.status_code).inc()
    # If a logo file exists, replace the header emoji with the logo image in HTML responses
    try:
        if response.content_type and 'text/html' in response.content_type:
            base = os.path.join(os.path.dirname(__file__), 'static')
            png = os.path.join(base, 'logo.png')
            svg = os.path.join(base, 'logo.svg')
            if os.path.exists(png):
                img_tag = b'<img src="/static/logo.png" alt="logo" style="height:48px;margin-right:12px;vertical-align:middle"> FruitStore'
            elif os.path.exists(svg):
                img_tag = b'<img src="/static/logo.svg" alt="logo" style="height:48px;margin-right:12px;vertical-align:middle"> FruitStore'
            else:
                img_tag = None
            if img_tag:
                body = response.get_data()
                body = body.replace('🍎 FruitStore'.encode('utf-8'), img_tag)
                response.set_data(body)
    except Exception:
        pass
    return response

def get_cart():
    if 'cart' not in session:
        session['cart'] = {}
    return session['cart']

@app.route('/')
def home():
    cart = get_cart()
    cart_count = sum(cart.values())
    items = "".join([f'<div class="product-card"><div class="product-image">{f["image"]}</div><div class="product-info"><div class="product-name">{f["name"]}</div><p style="color:#666;font-size:0.9rem;margin-bottom:1rem">{f["desc"]}</p><div class="product-price">€{f["price"]:.2f}/kg</div><div class="product-stock">Stock: {f["stock"]} kg</div><form action="/add-to-cart/{k}" method="POST" style="display:flex;gap:0.5rem;margin-top:1rem"><input type="number" name="quantity" class="quantity-input" value="1" min="1" max="{f["stock"]}"><button type="submit" class="btn btn-primary">Adicionar</button></form></div></div>' for k, f in FRUITS.items()])
    return f"""<html><head><title>FruitStore</title><style>{CSS}</style></head><body><header><h1>🍎 FruitStore</h1><nav><a href="/">Loja</a><a href="/cart">🛒 Carrinho{'<span class="cart-badge">'+str(cart_count)+'</span>' if cart_count > 0 else ''}</a><a href="/stats">📊 Stats</a></nav></header><div class="container"><div class="hero"><h2>Bem-vindo à FruitStore! 🥗</h2><p>Frutas frescas entregues rapidamente</p></div><div class="products-grid">{items}</div></div><footer><p>&copy; 2026 FruitStore | <a href="/api/metrics" style="color:#667eea;">Métricas</a></p></footer></body></html>""", 200

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
    return f"""<html><head><title>Carrinho</title><style>{CSS}</style></head><body><header><h1><a href="/" style="text-decoration:none;color:#667eea">🍎 FruitStore</a> - Carrinho</h1><nav><a href="/">Loja</a></nav></header><div class="container" style="background:white;border-radius:10px;padding:2rem;box-shadow:0 4px 20px rgba(0,0,0,0.1)"><h2>🛒 Carrinho</h2>{'<div>'+items_html+'<div style="background:#f9f9f9;padding:1rem;border-radius:5px;margin-top:1.5rem"><div style="display:flex;justify-content:space-between;margin-bottom:0.5rem"><span>Subtotal:</span><span>€'+f'{total*0.9:.2f}'+'</span></div><div style="display:flex;justify-content:space-between;margin-bottom:0.5rem"><span>Entrega:</span><span>€3.50</span></div><div style="display:flex;justify-content:space-between;border-top:2px solid #ddd;padding-top:0.5rem;font-weight:bold;font-size:1.2rem"><span>Total:</span><span>€'+f'{total*0.9+3.50:.2f}'+'</span></div></div><div style="display:flex;gap:1rem;margin-top:1.5rem"><a href="/" class="btn" style="background:#95a5a6;color:white;flex:1;text-align:center">← Continuar</a><a href="/checkout" class="btn btn-primary" style="flex:1;text-align:center">Checkout →</a></div></div>' if items else '<div style="text-align:center;padding:3rem;color:#666"><p>Carrinho vazio</p><a href="/" class="btn btn-primary">Voltar</a></div>'}</div></body></html>""", 200

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
    return f'''<html><head><style>{CSS}</style></head><body><header><h1><a href="/" style="text-decoration:none;color:#667eea">🍎 FruitStore</a> - Stats</h1><nav><a href="/">Loja</a><a href="/cart">🛒</a></nav></header><div class="container"><div style="display:grid;grid-template-columns:repeat(3,1fr);gap:1.5rem;margin-bottom:2rem">
    <div style="background:white;border-radius:10px;padding:1.5rem;box-shadow:0 4px 15px rgba(0,0,0,0.1)"><h3 style="color:#667eea">📊 Requisições</h3><div style="font-size:2rem;font-weight:bold">Grafana →</div><div style="color:#666;font-family:monospace">fruit_app_requests_total</div></div>
    <div style="background:white;border-radius:10px;padding:1.5rem;box-shadow:0 4px 15px rgba(0,0,0,0.1)"><h3 style="color:#667eea">❌ Erros</h3><div style="font-size:2rem;font-weight:bold">Grafana →</div><div style="color:#666;font-family:monospace">fruit_app_errors_total</div></div>
    <div style="background:white;border-radius:10px;padding:1.5rem;box-shadow:0 4px 15px rgba(0,0,0,0.1)"><h3 style="color:#667eea">⏱️ Latência</h3><div style="font-size:2rem;font-weight:bold">Grafana →</div><div style="color:#666;font-family:monospace">fruit_app_request_duration</div></div>
    </div><div style="background:white;border-radius:10px;padding:1.5rem;box-shadow:0 4px 15px rgba(0,0,0,0.1)"><h3>🔍 Monitorização</h3>
    <ul style="list-style:none"><li style="padding:0.75rem"><strong>Grafana:</strong> <a href="http://localhost:3000" target="_blank" style="color:#667eea">http://localhost:3000</a></li>
    <li style="padding:0.75rem"><strong>Prometheus:</strong> <a href="http://localhost:9090" target="_blank" style="color:#667eea">http://localhost:9090</a></li>
    <li style="padding:0.75rem"><strong>Métricas:</strong> <a href="/metrics" target="_blank" style="color:#667eea">/metrics</a></li></ul>
    <a href="/" class="btn btn-primary" style="margin-top:1rem">← Loja</a></div></div></body></html>''', 200

@app.route('/metrics')
def metrics():
    return generate_latest(), 200

@app.route('/api/metrics')
def api_metrics():
    return generate_latest(), 200

@app.route('/api/health')
def health():
    return jsonify({"status": "healthy", "version": "1.0.0"}), 200

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🍎 FruitStore - Loja Online de Frutas Profissional")
    print("="*60)
    print("Iniciando... http://localhost:5000")
    print("Dashboard: http://localhost:3000 (admin/admin)")
    print("="*60 + "\n")
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
