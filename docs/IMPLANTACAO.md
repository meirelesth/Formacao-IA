# Plataforma de alunos — acesso por convite

## O que esta versão entrega
Home com menu legível e dois botões. Login com e-mail e senha, mostrar senha, recuperação de acesso, convites de uso único, painel do professor, suspensão e reativação, autorização por plano, catálogo e downloads protegidos, progresso persistente separado por aluno. Convites duram 48h; recuperação, 30min; sessões, 8h. A conta do professor é criada no terminal, sem credencial padrão. Não existe cadastro público.

## Publicação atual e ativação real
O domínio público está hospedado no GitHub Pages, que não executa Python. A tela de login pode ser publicada ali, mas a autenticação precisa deste serviço em um servidor. A recomendação é manter a Home e instalar a plataforma em `alunos.luisfernando.online`. Após o serviço passar pelos testes de produção, os botões públicos devem apontar para esse endereço. Não apontar para um subdomínio ainda indisponível.

## Implantação em VPS ou VM Linux
1. Instalar Docker Compose e Caddy e trazer este repositório para o servidor.
2. Criar DNS A/AAAA de `alunos.luisfernando.online` para o servidor. Liberar 80/443; manter 8080 no loopback.
3. Copiar `.env.example` para `.env` e definir `APP_ORIGIN` com a origem HTTPS exata, sem caminho. Proteger `.env` com permissões 600.
4. Executar `docker compose up -d --build`.
5. Criar o professor com `docker compose exec formacao python -m server.app create-admin --name "Luís Fernando" --email "EMAIL_DO_PROFESSOR"`. A senha é solicitada de forma oculta no terminal; não colocar em argumentos ou enviar no chat.
6. Instalar o `Caddyfile` fornecido e recarregar o Caddy. Ele gera e renova o certificado HTTPS.
7. Abrir `https://alunos.luisfernando.online/entrar.html`, entrar como professor e gerar o convite de um aluno de teste.
8. Ativar, entrar, abrir aula, baixar material, salvar progresso, recarregar e sair. Confirmar bloqueio de downloads anônimos, planos não contratados e contas suspensas.
9. Somente então atualizar os botões de `index.html` e `planos.html` para `https://alunos.luisfernando.online/entrar.html`.

## Fluxo da matrícula
Confirmar contratação → cadastrar nome/e-mail e planos no painel → gerar convite → enviar exclusivamente para aquele aluno → aluno define senha → entra na plataforma. Cada aluno B2B e cada participante da dupla deve ter sua própria conta. O professor pode revogar acesso e gerar recuperação no painel. Não entregar a senha do professor a alunos.

## E-mail
Com SMTP STARTTLS configurado no `.env`, os convites e a recuperação são enviados pelo servidor. Sem SMTP, convites e recuperação gerada pelo professor funcionam por compartilhamento manual de link. A recuperação pública apresenta mensagem neutra e orienta procurar o professor. Entrega de e-mail precisa ser testada em produção (SPF, DKIM e DMARC no provedor). Nenhum e-mail real foi enviado durante os testes.

## Banco e backup
SQLite persistente em volume, adequado para uma única implantação. Este projeto não promete alta disponibilidade ou múltiplas réplicas. Faça backup consistente diariamente:

```bash
docker compose exec formacao python -m server.app backup --output /data/backup.sqlite3
docker compose cp formacao:/data/backup.sqlite3 ./backup.sqlite3
```

Copie os backups para outro armazenamento protegido. Para restaurar, pare a aplicação e substitua o arquivo do banco no volume com permissões do usuário 10001. Teste a restauração em uma implantação separada antes de produção. Não publique bancos nem backups no GitHub.

## Segurança
PBKDF2 SHA-256 com 600.000 iterações e salt, sessão aleatória armazenada como hash, cookie HttpOnly/SameSite/Secure, origem e CSRF em alterações, limite de tentativas por IP e por e-mail, links de uso único armazenados como hash, CSP, bloqueio de arquivos do servidor e suspensão que encerra sessões. A aplicação não confia em X-Forwarded-For fornecido por clientes. Ajustar proteção de borda e proxy conforme a infraestrutura; atrás de um proxy o limite por IP pode agregar usuários. Sem proteção de borda, não há mitigação completa de ataques distribuídos.

## Conteúdo
Os cadernos piloto já existiam em repositório público. Autenticação não torna cópias previamente públicas privadas. Para conteúdo comercial inédito: guardar em armazenamento privado fora do repositório público e manter a autorização no backend. O workflow Pages agora publica somente páginas/assets públicos e o portfólio; catálogo e materiais de aula ficam fora da publicação estática.
Videoaulas e emissão automática de certificados não foram implementadas. O certificado continua sendo emitido pelo professor, conforme descrito no curso. O painel registra matrícula, mas não processa pagamentos nem integra checkout.

## Validação
`python -m unittest discover -s server -p 'test_*.py' -v`
`node --check entrar.js` (também acesso.js, admin.js e aluno.js)
Os testes locais não substituem validação de DNS, TLS, SMTP, backup e acessos no servidor real. Não afirmar “100% em produção” antes de executar esses checks.

## Controles adicionais e limites da revisão — 02/10/2026

O administrador precisa de senha e TOTP de seis dígitos. Configure `ADMIN_TOTP_SECRET` antes de criar a conta; sem essa chave o login administrativo permanece bloqueado. Gere a chave **no servidor**, sem publicar no repositório:

```sh
python -c "import secrets,base64; print(base64.b32encode(secrets.token_bytes(20)).decode())"
```

Cadastre a chave no aplicativo autenticador (TOTP SHA-1, seis dígitos, período de 30 segundos), guarde uma cópia offline e salve somente no `.env` com permissão 600. Esta configuração destina-se a uma única conta administrativa do professor. Não compartilhe a conta. Trocar a chave exige invalidar sessões administrativas no banco e recadastrar o autenticador. Não existe recuperação pública do segundo fator.

Sessões expiram após oito horas, ou após 30 minutos sem requisições para alunos e 15 minutos para administração. Códigos TOTP usados não podem ser reutilizados. A recuperação envia e-mail em uma fila limitada em memória, sem esperar SMTP na resposta pública. Reinícios ou falha de SMTP podem interromper a entrega: o professor pode gerar um novo link pelo painel. Isso não é uma fila durável nem garantia de entrega. Não há rastreamento externo nas páginas de acesso. Senhas, tokens e chaves não devem aparecer nos logs.

O SQLite e os backups contêm nomes, e-mails e progresso: precisam de armazenamento restrito, backups **criptografados** fora do servidor e política de retenção. A aplicação não criptografa o arquivo SQLite por conta própria. Nunca copie banco, `.env`, backups ou certificados individuais para o GitHub público. O certificado público é um modelo sem dados pessoais e sem validade; ainda não há assinatura digital criptográfica nem serviço de verificação de certificados emitidos.

A limitação de tentativas usa `REMOTE_ADDR`, sem confiar em cabeçalhos enviados pelo visitante. Atrás do proxy, o limite pode ser compartilhado; configure também limites no proxy antes da abertura aos alunos. Testes de código e navegador não equivalem a teste de invasão independente. A liberação em produção exige validar HTTPS, cabeçalhos, controle de acesso, SMTP real, restauração de backup, atualizações de dependências, monitoramento e resposta a incidentes no servidor efetivamente contratado. O GitHub Pages hospeda apenas a parte pública; não executa este backend.
