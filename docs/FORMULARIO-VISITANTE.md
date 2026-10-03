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

**Preparado, desativado até definir o destinatário e validar SMTP.** Não foi enviado e-mail real nem confirmada entrega. Com backend indisponível ou configuração incompleta, a janela não abre para visitantes.

## Ativação na Hostinger

Atualizar o backend PHP do pacote e os arquivos públicos. Em `formacao-private/config.php` (fora de `public_html`), configurar:

```php
'visitor_survey_enabled' => true,
'visitor_survey_recipient' => 'ENDERECO_ESCOLHIDO_PELO_PROFESSOR',
```

Configurar também os campos SMTP existentes: host, porta, usuário, senha e remetente. Não registrar valores reais de credenciais no GitHub.

Manter o cron existente de `formacao-private/cron.php` ativo. Ele processa a fila de perfis além da recuperação de senha. A tabela `visitor_profiles` é criada automaticamente no primeiro envio ou no cron quando habilitado, para compatibilidade com instalações existentes.

Antes de anunciar o envio como operacional: fazer um envio de teste autorizado, conferir o registro na tabela e verificar a chegada ao e-mail escolhido. Se o SMTP falhar, a resposta é preservada e há até cinco tentativas com intervalo de cinco minutos; o estado final é `failed`, sem apagar as respostas.

Endpoint de disponibilidade: `GET /api/visitor-profile/config`. Deve retornar `{"enabled":true}` após configuração. Endpoint de resposta: `POST /api/visitor-profile`; JSON, mesma origem, limite de requisição e validação de opções no servidor. Há limite de cinco solicitações por IP em 15 minutos e chave de idempotência para evitar registros repetidos em tentativas do mesmo envio.

O backend Python legado mantém o questionário desativado; a implementação de envio é a de PHP/MySQL da Hostinger. SMTP e cron não são configurados por um commit no GitHub.

## Manutenção das respostas

Respostas ficam no banco privado, fora da área pública. Acesso por ferramentas administrativas autorizadas. A política de retenção e eventual exclusão deve ser definida pelo responsável pela plataforma. Não incluir informações confidenciais no campo aberto.
