# Financeiro pessoal

Aplicação independente do login de alunos, planejada para `https://luisfernando.online/fin/`. Dados, sessões e auditoria ficam no volume privado da VPS. O frontend acompanha a identidade LF; nenhum dado da planilha deve ser enviado ao GitHub.

## Operação

Da raiz do repositório: `docker compose -f financeiro/compose.yaml up -d --build`.

Criar a única conta, digitando a senha em terminal interativo: `docker compose -f financeiro/compose.yaml exec financeiro python -m financeiro.manage owner`. A senha é armazenada somente como hash scrypt. Não existem senha padrão ou cadastro público.

Importar o arquivo privado processado: `docker compose -f financeiro/compose.yaml exec financeiro python -m financeiro.manage import --file /data/importacao-ftm.json`. O extrator `import_ftm.py` lê a planilha sem alterá-la. A importação usa identificadores de célula e não duplica registros quando repetida.

Backup consistente: `python -m financeiro.manage backup --file /data/backup.sqlite3`. Manter cópia protegida fora da VPS. Para restaurar, parar apenas o serviço financeiro, restaurar o banco e voltar o serviço. Nenhum backup fica em pasta pública.

## Regras financeiras

- Dinheiro em centavos inteiros. Parcelas dividem o valor total sem perder centavos; repetições de receitas/despesas repetem o valor mensal.
- Receita e despesa são organizadas por competência. Os valores recebidos/pagos na visão do mês são relativos à competência, sem representar fluxo bancário por data ou saldo bancário.
- Compra no cartão aparece uma vez na fatura. Pagamento de fatura não adiciona outra despesa.
- Importados aguardam revisão, com origem por célula. “OK” preserva a indicação de quitado, sem inventar uma data; outras situações ficam descritas na observação.
- Totais e fórmulas da planilha não viram lançamentos. Valores vazios e zeros são preservados no original e não criam obrigações fictícias.
- Faturas históricas são saldos de abertura. Não adicionar suas compras novamente no mesmo cartão/mês. Os blocos adicionais da planilha precisam de revisão para descobrir eventual inclusão na fatura.
- Sessões duram no máximo oito horas, com expiração após 30 minutos inativos. Cookie exclusivo de `/fin`, proteção de origem e CSRF, limitação de tentativas, controle de versão em alterações e trilha de auditoria.
- O aplicativo instala um ícone no celular, mas não armazena os dados financeiros em cache offline.

## Publicação no domínio

A VPS tem o financeiro em `127.0.0.1:8090`. O site público atualmente usa hospedagem separada. A integração de `/fin` precisa de proxy HTTPS configurado na hospedagem do domínio, sem alterar seus DNS ou o serviço n8n existente. O container sozinho não publica o caminho no domínio. Esta etapa deve ser validada antes de dizer que o endereço está pronto.
