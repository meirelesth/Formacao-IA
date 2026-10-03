# PagBank · checkout da Formação IA

O checkout público fica em `/checkout.html?curso=basica` e `/checkout.html?curso=avancada`. O cliente informa nome, e-mail, CPF e celular; o servidor define o produto e o preço e abre o checkout hospedado do PagBank. CPF e celular são enviados ao PagBank e não são armazenados na tabela local de pedidos. O servidor mantém nome, e-mail, curso, valor e identificadores necessários para a matrícula.

## Conectar a conta

1. Entre como administrador e abra **PagBank e matrículas online**.
2. Gere o token na sua conta PagBank, seguindo https://developer.pagbank.com.br/docs/token-de-autenticacao. A conta precisa estar habilitada para a API de Checkout.
3. Comece com **Sandbox · testes** e o token desse ambiente. Marque a opção para habilitar o checkout e salve. A página informa que é um teste e não libera cursos.
4. Teste um cartão de sandbox, o fluxo de Pix, o retorno e o webhook. Confira os pedidos no painel. Não use cartões reais em sandbox.
5. Troque para **Produção · vendas reais**, informe o token de produção e salve. Faça uma compra controlada antes de divulgar. Os tokens não são intercambiáveis.

O token nunca aparece na página pública, nas respostas de consulta do painel ou no GitHub. Ele fica em `formacao-private/pagbank.json` com permissão 0600. A hospedagem precisa permitir escrita nessa pasta. Para desativar novas vendas, desmarque a opção e salve; o recebimento de notificações de pedidos existentes continua ativo enquanto houver token configurado. Não troque token ou ambiente enquanto pagamentos estiverem pendentes. Faça backup privado de `payment-key`, `pagbank.json` e do banco; nunca publique esses arquivos.

Alternativa: configure `pagbank_token`, `pagbank_environment` (`sandbox` ou `production`) e `pagbank_enabled` no `config.php` privado. A configuração salva no painel prevalece. A tabela `payment_orders` é criada na primeira operação de pedidos, de maneira idempotente, sem reexecutar o instalador.

## Meios de pagamento e juros

Somente `PIX` e `CREDIT_CARD` são enviados. `INSTALLMENTS_LIMIT` é definido no servidor como `3`. Os preços são R$ 997,00 e R$ 1.699,00; valores enviados pelo navegador são ignorados. O parcelamento segue o padrão do PagBank, com juros exibidos ao comprador. Não é anunciada a condição “sem juros”. Para assumir juros, é necessário definir `INTEREST_FREE_INSTALLMENTS` e conferir as taxas na conta antes de alterar a oferta.

## Confirmação e acesso

URL automática: `https://luisfernando.online/api/payments/webhook`, enviada na criação do checkout para notificações de checkout e pagamento. O retorno à página não aprova pagamento. O webhook verifica a assinatura SHA-256 do corpo original e do token, consulta `/orders/{id}` com autenticação e confere referência, e-mail, item, moeda, valor pago e método. Apenas `PAID` em produção libera acesso. Eventos repetidos mantêm uma única liberação.

O aluno novo recebe o botão de ativação na página de acompanhamento, com link válido por 48 horas e senha mínima de seis caracteres. A conta existente recebe o curso comprado e entra com a própria senha. Contas suspensas exigem revisão administrativa. O básico não inclui automaticamente o avançado e vice-versa. Compras de cursos diferentes no mesmo e-mail preservam os acessos. A página de acompanhamento depende do link privado ou da sessão do navegador e consulta o servidor a cada 20 segundos enquanto visível. Sem webhook confirmado, permanece aguardando; o painel permite conferir os pedidos.

Não há envio automático de e-mail comercial nesta integração. O professor combina a agenda e a matrícula de uma segunda pessoa em dupla. Pedidos reembolsados ou contestados exigem revisão no PagBank e no painel: não suspenda a conta inteira sem conferir outros cursos e compras válidas. O curso pago não é liberado em sandbox.

## Referências oficiais

- https://developer.pagbank.com.br/reference/criar-checkout
- https://developer.pagbank.com.br/docs/checkout
- https://developer.pagbank.com.br/reference/webhooks-checkout
- https://developer.pagbank.com.br/reference/confirmar-autenticidade-da-notificacao
- https://developer.pagbank.com.br/reference/consultar-pedido

## Validação pendente da conta real

Os testes locais e de CI verificam regras, assinatura, valores e proteção de acesso. Sem um token da conta não é possível validar habilitação comercial, taxas, limites, cartões, Pix, formato real dos retornos e entrega do webhook. Execute o roteiro de sandbox antes de habilitar produção.
