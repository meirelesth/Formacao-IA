# Formulário de perfil do visitante

Janela opcional na Home, na identidade visual do site. Quatro perguntas de marcar, profissão/área e ideia/sonho opcionais. Dois passos curtos. Inclui curiosidade e hobby, aplicação no trabalho e construção para negócio.

- Fecha por botão, Escape, clique fora ou “Prefiro explorar o site”.
- Ao fechar, não reabre automaticamente na mesma sessão. Ao enviar, não reabre automaticamente naquele navegador.
- CTA dourado na parte inferior: “Não quero responder o formulário / Falar com o especialista Luís Fernando”. Abre WhatsApp (98) 98143-2271 diretamente, sem enviar as respostas.
- O visitante pode reabrir pelo link no rodapé.
- Navegação funciona mesmo sem API ou armazenamento do navegador.
- Não pede nome, telefone nem e-mail do visitante. As respostas podem ser anônimas.
- Sucesso significa registro durável para envio, não confirmação de recebimento na caixa postal.

## Estado de implantação

O formulário agora grava no banco independentemente de SMTP. O botão destacado abre diretamente o WhatsApp. E-mail e agenda/Meet ficam para etapas futuras.

A publicação depende de PHP com PDO MySQL e da configuração privada acessível. Sem banco configurado, a janela não abre automaticamente e a navegação continua funcionando. O recebimento por e-mail não foi ativado nem testado.

## Instalação na Hostinger

1. Fazer backup dos arquivos existentes que serão substituídos.
2. Copiar os arquivos de public_html do pacote para public_html do site, preservando os demais arquivos.
3. Manter formacao-private fora de public_html, no mesmo nível. Se já há config.php, preservar as credenciais existentes.
4. Se não há config.php, copiar o exemplo fornecido para formacao-private/config.php e preencher localmente db_host, db_port, db_name, db_user, db_password e origin.
5. Configurar origin como https://luisfernando.online. PHP 8.1 ou superior, PDO MySQL e permissões CREATE/INSERT/SELECT/UPDATE no banco são necessários. O código usa CREATE TABLE IF NOT EXISTS; não apaga tabelas existentes.
6. Abrir /perfil-visitante.php?config=1. Com banco acessível e formulário habilitado, retorna {"enabled":true}.
7. Abrir a Home em uma sessão nova; conferir janela, fechar, reabrir no rodapé e enviar uma resposta de teste autorizada. Conferir a linha criada em visitor_profiles.

Se usar outro local privado, definir FORMACAO_PRIVATE_DIR no ambiente do PHP com o caminho absoluto correto. Credenciais não devem ficar em arquivos públicos nem no GitHub.

## Consultar as respostas

Página: /respostas-visitantes.html. Mostra as últimas 200 respostas e requer login de administrador do backend PHP existente, por cookie de sessão. A autenticação é verificada no servidor; alunos e visitantes não recebem respostas.

Se a área administrativa ainda não estiver configurada, visualizar a tabela visitor_profiles pelo phpMyAdmin da Hostinger. O campo payload contém as respostas em JSON. A página de consulta depende das tabelas users e sessions do backend existente; a gravação do formulário funciona de forma independente delas.

## Ativação de e-mail no futuro

Não é necessário configurar e-mail para gravar os perfis. Futuramente, definir na configuração privada:

- visitor_survey_enabled: true (padrão, independente de e-mail).
- visitor_survey_email_enabled: true (padrão false, habilitação específica de envio).
- visitor_survey_recipient: endereço escolhido pelo professor.
- SMTP: host, porta, usuário, senha e remetente.

Atualizar também o módulo VisitorProfile.php do backend privado e manter cron.php ativo. O cron envia perfis pendentes somente após a habilitação explícita de e-mail; respostas já registradas podem ser processadas nessa fila. Há cinco tentativas; falhas preservam os dados. Fazer teste de recebimento antes de anunciar o envio como operacional.

## Comportamento e validação

O preenchimento é voluntário. A mensagem de sucesso confirma registro no banco, não entrega por e-mail. Não há agendamento de calendário nesta etapa. Não há coleta de nome, telefone ou e-mail do visitante.

Endpoint principal: perfil-visitante.php. GET ?config=1 informa disponibilidade; POST registra JSON de mesma origem; GET ?responses=1 exige administrador. Validação de opções, limite de tamanho, proteção anti-spam e chave de idempotência são feitos no servidor. Consulta mostra texto de forma segura sem interpretar HTML enviado pelo visitante.

Foram conferidas a sintaxe JavaScript/Python e a integração dos arquivos. Testes visuais e PHP/MySQL precisam ser executados no ambiente de hospedagem ou no fluxo de CI: o ambiente local não possui PHP e a instalação do navegador de teste falhou. Não foi confirmado registro no banco de produção.

A política de retenção e exclusão das respostas deve ser definida pelo responsável pela plataforma. Não inserir dados confidenciais nos campos abertos.
