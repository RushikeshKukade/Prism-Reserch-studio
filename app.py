"""Local HTTP interface; Python 3.10+, standard library only."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, unquote, parse_qs
from engine import DATA, EXAMPLES, answer
from analytics import quality_report, change_bridge, saved_evaluation
from market import current_market, answer_current, market_summary, start_refresh, refresh_status, read_cache
from universe import get_universe, get_universes
from trading_universe import build_universe
from ai_brief import generate_brief, status as ai_status

STATIC = Path(__file__).parent / 'static'


def research_answer(question):
    import time
    started = time.perf_counter()
    current = answer_current(question)
    if current is not None:
        current['latency_ms'] = round((time.perf_counter() - started) * 1000, 3)
    return current if current is not None else answer(question)


class Handler(BaseHTTPRequestHandler):
    def respond(self, payload, status=200, content_type='application/json; charset=utf-8'):
        data = payload if isinstance(payload, bytes) else json.dumps(payload, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self'; script-src 'self'; connect-src 'self'; img-src 'self' data:; frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = unquote(urlsplit(self.path).path)
        if path == '/api/ai/status':
            return self.respond(ai_status())
        if path == '/api/current':
            return self.respond(market_summary())
        if path == '/api/universe':
            try:
                return self.respond(get_universe(parse_qs(urlsplit(self.path).query).get('index', ['nifty500'])[0]))
            except ValueError as error:
                return self.respond({'error': str(error)}, 400)
        if path == '/api/trading-universe':
            query = parse_qs(urlsplit(self.path).query)
            try:
                data = build_universe(get_universe(query.get('index', ['nifty200'])[0]), market_summary(),
                    min_history=int(query.get('min_history', ['200'])[0]),
                    min_price=float(query.get('min_price', ['0'])[0]),
                    min_turnover_crore=float(query.get('min_turnover_crore', ['0'])[0]))
                return self.respond(data)
            except ValueError as error:
                return self.respond({'error': str(error)}, 400)
        if path == '/api/refresh-status':
            return self.respond(refresh_status())
        if path.startswith('/api/history/'):
            key=path.rsplit('/',1)[-1]
            row=next((r for r in read_cache()['series'] if r['id']==key),None)
            return self.respond(row if row else {'error':'No cached history for this company'},200 if row else 404)
        if path == '/api/meta':
            return self.respond({'data': DATA, 'examples': EXAMPLES, 'universe': get_universe(), 'universes': get_universes()})
        if path == '/api/quality':
            from datetime import datetime, timezone, timedelta
            return self.respond(quality_report(as_of=datetime.now(timezone(timedelta(hours=5, minutes=30))).date()))
        if path.startswith('/api/changes/'):
            try:
                return self.respond(change_bridge(path.rsplit('/', 1)[-1]))
            except ValueError:
                return self.respond({'error':'Unknown company'}, 404)
        if path == '/api/evaluation':
            return self.respond(saved_evaluation())
        if path == '/health':
            return self.respond({'status': 'ok'})
        assets = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'), '/studio.js': ('studio.js', 'text/javascript'), '/style.css': ('style.css', 'text/css')}
        if path not in assets:
            return self.respond({'error': 'Not found'}, 404)
        name, mime = assets[path]
        self.respond((STATIC / name).read_bytes(), content_type=mime + '; charset=utf-8')

    def do_POST(self):
        if self.path not in ('/api/ask','/api/brief','/api/current/refresh'):
            return self.respond({'error': 'Not found'}, 404)
        # No cross-origin requests or remote binding; intended for local demo only.
        origin = self.headers.get('Origin')
        if origin and origin != 'http://' + self.headers.get('Host', ''):
            return self.respond({'error': 'Origin not allowed'}, 403)
        if self.path == '/api/brief':
            host = self.headers.get('Host', '')
            allowed_hosts = {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}
            if host not in allowed_hosts or origin != 'http://' + host:
                return self.respond({'error': 'Same-origin localhost browser request required'}, 403)
        if self.path == '/api/current/refresh':
            return self.respond({'job':start_refresh()},202)
        try:
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 8192:
                return self.respond({'error': 'Invalid request size'}, 413)
            body = json.loads(self.rfile.read(size))
            if not isinstance(body, dict) or not isinstance(body.get('question'), str):
                return self.respond({'error': 'question must be a string'}, 400)
            if not 1 <= len(body['question'].strip()) <= 1000:
                return self.respond({'error': 'Use a question between 1 and 1000 characters'}, 400)
        except (ValueError, UnicodeDecodeError):
            return self.respond({'error': 'Invalid JSON'}, 400)
        result = research_answer(body['question'])
        if self.path == '/api/brief':
            return self.respond(generate_brief(body['question'], result))
        self.respond(result)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'Prism India Research | http://127.0.0.1:{args.port}', flush=True)
    print('Press Ctrl+C to stop. No API key or package installation required.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
