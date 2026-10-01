# Área do aluno — implantação da fase 2

## Estado da entrega
- GitHub Pages: site público e prévia pública da área do aluno.
- Servidor Python: autenticação real, sessão com cookie e progresso por aluno preparados e testados localmente.
- Conteúdo: três leituras guiadas e quatro materiais piloto. Não há vídeos, cobrança ou emissão de certificados nesta etapa.
- A página estática não autentica alunos. O login real somente funciona quando o servidor Python é implantado.

## Rodar localmente
Use Python 3.12 ou superior a partir da raiz do repositório.

```bash
python -m server.app create-user --name "Nome do aluno" --email "aluno@example.com"
python -m server.app serve
```

A senha é solicitada no terminal e não deve ser enviada no chat, colocada em arquivos ou passada como argumento.
Abra http://127.0.0.1:8080/entrar.html. O progresso é salvo em data/formacao.sqlite3.

## Produção em VPS
1. Configure um domínio/subdomínio com HTTPS no proxy reverso (Nginx/Caddy).
2. Defina APP_ORIGIN com a origem HTTPS exata, sem caminho e sem barra final.
3. Execute `docker compose up -d --build`.
4. Encaminhe esse domínio para 127.0.0.1:8080, mantendo o serviço vinculado ao loopback.
5. Crie alunos com `docker compose exec formacao python -m server.app create-user --name "Nome" --email "aluno@example.com"`.
6. Faça backup consistente do volume formacao-data usando o recurso de backup do SQLite. Inclua uma rotina de restauração testada.

## Proteções implementadas
- Senhas derivadas com PBKDF2-HMAC-SHA256, salt aleatório e 600.000 iterações.
- Tokens de sessão aleatórios; somente o hash do token é persistido.
- Cookie HttpOnly, SameSite=Lax, Secure quando APP_ORIGIN usa HTTPS, validade de 8 horas.
- Verificação de origem e token CSRF para alterações autenticadas.
- Cinco tentativas de login por combinação de endereço de origem e e-mail em 15 minutos.
- Validação de aulas disponíveis; progresso isolado por usuário.
- Sem cadastro público, credenciais de demonstração ou segredos no frontend.

## Limites desta fase
- Base SQLite adequada a uma implantação única; não há múltiplas instâncias com bancos separados.
- Cadastro de alunos pelo terminal. Recuperação de senha, matrícula, pagamentos e painel administrativo ficam para a próxima etapa.
- Materiais piloto e catálogo são públicos. Conteúdos pagos futuros precisam de autorização no servidor e armazenamento privado antes de serem publicados.
- O limite de tentativas atual não substitui proteção de borda contra ataques distribuídos.
- O processo wsgiref do comando serve é somente para desenvolvimento; produção usa Gunicorn atrás do proxy HTTPS.
- Implantação, DNS e testes de HTTPS da VPS não foram executados nesta entrega.

## Verificação
```bash
python -m unittest server.test_app -v
node --check aluno.js
node --check entrar.js
```
