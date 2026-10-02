# Formação IA — instalação na hospedagem de sites Hostinger

Esta é a versão **PHP 8.3+ e MySQL/MariaDB** da área do aluno. O site público continua em HTML, CSS e JavaScript. A versão Python/VPS permanece como alternativa; use apenas um backend para cada instalação. O pacote não contém senhas, contas reais ou dados pessoais.

## 1. Antes de publicar

- Faça um backup dos arquivos e do banco existentes no hPanel. Não apague nem substitua um sistema já instalado sem conferir o conteúdo.
- Em Configuração PHP, selecione PHP 8.3 ou superior. Habilite PDO, pdo_mysql e OpenSSL. Argon2id é usado quando disponível; o fallback é PBKDF2-SHA256 com 600 mil iterações. Confirme a versão do PHP do cron também.
- Garanta SSL ativo e acesso pelo endereço HTTPS. O roteador rejeita HTTP em produção. Não desative essa proteção para contornar erro de configuração.
- O domínio precisa apontar para **esta hospedagem**. Se ainda apontar para GitHub Pages, publicar um ZIP no hPanel não muda o destino do domínio. Confira o destino antes de alterar o DNS. Faça primeiro a instalação e verificação na hospedagem, conforme os recursos de prévia/SSL do seu plano.

## 2. Criar o banco na tela mostrada

Crie um banco exclusivo, por exemplo `formacao`, e um usuário exclusivo, por exemplo `formacao_app`. O hPanel acrescentará seu prefixo; copie os nomes **completos**. Use a opção do painel para gerar uma senha forte e salve-a no seu gerenciador de senhas. Não envie a senha na conversa nem coloque os dados no GitHub. Este usuário não deve ter acesso a bancos de outros projetos.

## 3. Extrair o pacote na pasta do domínio

A estrutura precisa ficar assim:

- `domains/luisfernando.online/public_html/`: páginas, imagens, estilos, scripts, `lf-router.php` e `.htaccess`.
- `domains/luisfernando.online/formacao-private/`: aplicação PHP, configuração, catálogo, aulas, dependências, fila de e-mail e marcas de instalação.

`formacao-private` fica **ao lado de** `public_html`, nunca dentro dela. Não extraia o ZIP inteiro dentro da pasta pública. Não envie o ZIP, backups, banco, arquivos SQL ou configuração privada para `public_html`. Não use implantação automática do repositório completo nessa pasta: ele contém o código do backend e materiais de estudo.

Faça as alterações em uma cópia/backup e só substitua os arquivos do site existente depois de conferir o pacote. Mantenha os nomes `.htaccess` e `lf-router.php`; sem as regras de roteamento, a proteção das páginas privadas não está validada.

## 4. Configuração privada

Copie `formacao-private/config.example.php` para `formacao-private/config.php`. Preencha diretamente no gerenciador de arquivos da hospedagem:

- `origin`: `https://luisfernando.online` (sem barra final).
- `db_host`: o servidor do banco informado pelo painel, normalmente `localhost`.
- `db_name`, `db_user`, `db_password`: dados completos do banco exclusivo.
- `setup_key`: pelo menos **32 caracteres aleatórios**, gerados pelo seu gerenciador de senhas. Não use uma frase simples.
- `admin_totp_secret`: pode ficar vazio; o instalador gera uma chave nova para você.
- `allow_http`: mantenha `false`.

Use permissão 600 no arquivo de configuração e permissões restritas compatíveis com o PHP da conta na pasta privada. Não altere a configuração de outros sites nem use permissões 777. Credenciais não ficam no JavaScript ou em arquivos públicos.

## 5. Instalar e criar o professor

Abra **https://luisfernando.online/instalar** após a configuração e a publicação corretas. Digite a chave de instalação. O sistema cria as tabelas, gera uma chave TOTP e mostra a configuração manual do autenticador, sem enviar essa chave a serviços externos.

No seu aplicativo autenticador, cadastre a chave manualmente: TOTP, seis dígitos, SHA-1 e período de 30 segundos. Guarde uma cópia offline. Preencha seu nome, e-mail, senha de pelo menos 12 caracteres, confirmação e código do aplicativo. Essas credenciais são digitadas por você diretamente na tela HTTPS.

Após concluir, o instalador apaga a chave de instalação da configuração e fica indisponível. Aguarde o próximo código do autenticador e entre em `/entrar.html`. Alunos não precisam de autenticador; a conta administrativa do professor exige senha e TOTP. Não há conta administrativa ou senha padrão no pacote. A chave TOTP destina-se à única conta administrativa do professor; não compartilhe essa conta.

## 6. Convites e recuperação

O professor libera os planos e gera convites pelo painel. Envie cada link **somente ao aluno da matrícula**, por um canal apropriado. O convite é uma credencial temporária; o nome/e-mail do aluno não aparecem no link. Convites expiram em 48 horas. Links de recuperação expiram em 30 minutos e são de uso único. A suspensão/redefinição invalida sessões do aluno.

O envio dos convites nesta versão é **manual** pelo professor. Configure sempre um cron PHP a cada cinco minutos para `formacao-private/cron.php`, mesmo sem SMTP, para limpar registros expirados. Para recuperação de senha automática, preencha o SMTP privado com as informações do seu serviço de e-mail e configure um cron PHP a cada cinco minutos para o caminho absoluto de `formacao-private/cron.php`. A recuperação coloca tanto endereços conhecidos quanto desconhecidos na mesma fila; o cron verifica a matrícula e envia somente para contas ativas. Ele usa TLS e valida certificados SMTP. Sem SMTP configurado, o professor gera e compartilha um link pelo painel. O envio real ainda precisa ser testado na hospedagem.

## 7. Validação obrigatória antes de cadastrar alunos reais

1. `/healthz` deve retornar `{"ok":true}` pela conexão HTTPS.
2. `/api/session`, sem login, deve retornar `authenticated:false`.
3. `/catalogo.json` e um arquivo real de aula, sem login, devem retornar 401.
4. `/admin.html`, sem conta administrativa, deve redirecionar ao login.
5. `/formacao-private/config.php`, `/hostinger/schema.sql`, `/.env`, `/server/app.py` e arquivos de backup devem ser inacessíveis. Não deixe cópias com nomes alternativos na pasta pública.
6. `/instalar` deve ficar indisponível após a primeira instalação.
7. Faça uma matrícula **fictícia** pelo painel: convide, ative, entre, teste plano básico, progresso, suspensão, recuperação e saída. Não reutilize dados de alunos reais nesses testes.
8. Teste HTTPS, cookie Secure/HttpOnly/SameSite, bloqueio de origem externa, MFA, cron/SMTP real e restauração de backup. Os testes automatizados em ambiente de desenvolvimento não validam a configuração do seu plano Hostinger.

## Dados e limites de segurança

Nome, e-mail, matrícula e progresso são armazenados no MySQL privado. Senhas são hashes; tokens de sessão/convite/recuperação são armazenados apenas como hashes. Sessões expiram após oito horas ou por inatividade: 30 minutos para aluno e 15 minutos para administrador. A aplicação não confia em X-Forwarded-For enviado pelo visitante para limitar tentativas. Se o servidor fornecer um endereço compartilhado atrás de proxy, confirme os limites/WAF com a hospedagem.

Use backups criptografados, retenção definida e cópia fora da hospedagem. O código não criptografa sozinho o arquivo/banco MySQL: a proteção de disco, backup, conta de hospedagem e acesso administrativo precisa ser verificada no provedor. O cron remove sessões e tokens expirados e limita o histórico de auditoria a 180 dias. A fila pública de recuperação tem limite de 1.000 solicitações e descarte após 24 horas; se estiver cheia, o professor pode gerar o link pelo painel. Os dados de alunos não são publicados no site nem no GitHub. O certificado público é apenas um modelo sem validade; não existe, nesta entrega, assinatura criptográfica ou verificador público de certificados emitidos.

Não há promessa de segurança absoluta, conformidade legal certificada ou entrega garantida de e-mail. Antes da operação real, confirme aviso de privacidade, procedimentos de atendimento ao titular, retenção dos registros, atualizações e resposta a incidentes. A implantação e a validação em produção ainda dependem da configuração desta hospedagem.
