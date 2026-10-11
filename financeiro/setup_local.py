"""Owner activation over a private SSH tunnel, never through the public gateway."""
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs
from financeiro.app import Application
app=Application()
PAGE='''<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Ativar financeiro privado</title><body style="font:16px system-ui;max-width:440px;margin:70px auto;padding:24px"><h1>Ative seu financeiro</h1><p>Crie a senha exclusiva do seu controle pessoal. Ela será gravada somente como hash na VPS.</p><form method="post"><p><label>Senha (mínimo 12 caracteres)<br><input type="password" name="password" minlength="12" autocomplete="new-password" required style="padding:12px;width:90%"></label></p><p><label>Confirmar senha<br><input type="password" name="confirm" minlength="12" autocomplete="new-password" required style="padding:12px;width:90%"></label></p><button style="padding:14px">Ativar meu acesso</button></form></body></html>'''
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def send(self,body,status=200):
        self.send_response(status);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Cache-Control','no-store');self.send_header('X-Frame-Options','DENY');self.end_headers();self.wfile.write(body.encode())
    def do_GET(self):
        with app.db() as db:owner=db.execute('SELECT 1 FROM owner').fetchone()
        self.send('<h1>O acesso já foi ativado.</h1>' if owner else PAGE)
    def do_POST(self):
        if self.headers.get('Origin')!='http://127.0.0.1:18091':self.send('Origem não autorizada.',403);return
        length=int(self.headers.get('Content-Length',0))
        if length>4096:self.send('Solicitação inválida.',413);return
        fields=parse_qs(self.rfile.read(length).decode());password=fields.get('password',[''])[0]
        if password!=fields.get('confirm',[''])[0] or len(password)<12:self.send('Use uma senha com 12 caracteres e confirme o mesmo valor.',400);return
        try:app.owner('Luís Fernando',password)
        except Exception:self.send('A conta já está ativada ou não foi possível concluir.',409);return
        self.send('<h1>Acesso privado ativado.</h1><p>Você já pode entrar no seu financeiro com a senha escolhida.</p>');threading.Thread(target=self.server.shutdown,daemon=True).start()
HTTPServer(('0.0.0.0',8091),Handler).serve_forever()
