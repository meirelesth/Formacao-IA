# Central de Skills integrada

Acervo importado da pasta Central de Skills do professor: 1.172 entradas do catálogo em 90 categorias e 126 pacotes com SKILL.md. O catálogo conserva os links de origem. As entradas de catálogo não representam pacotes testados ou compatibilidade garantida com Claude web.

Os pacotes conservam scripts, referências, exemplos e dependências compartilhadas presentes no acervo. Os pacotes técnicos podem exigir Claude Code, MCP, terminal e outros serviços. Os arquivos são fornecidos para download e nunca executados pelo site.

## Alunos e administração

Alunos autenticados acessam a Biblioteca de Skills, pesquisam todo o acervo, filtram por categoria e ferramenta e carregam mais resultados. Cada pacote publicado pode ser baixado pela sua rota autenticada. O administrador pesquisa, edita, publica e retira itens e pode baixar o acervo completo. A retirada bloqueia o download individual. O ZIP completo é administrativo e contém o acervo original, inclusive itens retirados da biblioteca.

## Importação e hospedagem

O backend importa os registros uma única vez, ao primeiro acesso autorizado à biblioteca. IDs reservados e uma marca de versão impedem duplicação ou restauração de itens retirados pelo administrador. O banco existente e os cadastros de alunos são preservados.

O pacote Hostinger inclui skills-catalog.json, skills-packages.json e CENTRAL-LICENSE.txt em formacao-private, fora de public_html. O backend Python usa os mesmos dados em server, cujo acesso HTTP é bloqueado. Os arquivos de configuração e credenciais não fazem parte do pacote. A instalação segue docs/HOSTINGER.md.

Na implantação automática do repositório pelo GitHub, o PHP lê o acervo atualizado de server/ dentro do projeto, protegido pelo bloqueio HTTP do .htaccess. Na instalação por ZIP, usa formacao-private. Ambos importam o catálogo no primeiro acesso autenticado e mantêm os downloads protegidos, sem exigir a cópia manual dos arquivos para a pasta privada.

Publicar HTML pelo GitHub não ativa sozinho PHP/MySQL. Para confirmar a implantação, /api/session precisa responder JSON e /healthz precisa responder ok. Um 404 nessas rotas indica que a área privada ainda não está operando nesse domínio.

Em 04/10/2026, 15 skills relacionadas a conteúdo empresarial foram retiradas do catálogo, dos pacotes individuais e do ZIP completo. A lista de IDs excluídos também remove os registros importados anteriormente, preservando as demais skills. Após essa retirada, o acervo continha 1.298 entradas.

## Português do Brasil

Os títulos e descrições do catálogo e os textos dos pacotes são adaptados para PT-BR. Cada SKILL.md contém uma instrução explícita para produzir respostas e materiais em português do Brasil, com interface agents/openai.yaml também em português. Identificadores técnicos, comandos, exemplos de código e arquivos executáveis mantêm sua função e seus nomes. A importação da versão localizada atualiza títulos e descrições dos registros existentes uma única vez, sem alterar a publicação, links de download ou comandos definidos pelo professor.

As entradas de catálogo com fonte externa não contêm um pacote hospedado nesta plataforma. O prompt orienta traduzir a documentação e as instruções para PT-BR antes da instalação, preservando o código e os requisitos. A instalação depende do agente e do acesso à fonte.

A tradução em lote utiliza OPUS-MT (Helsinki-NLP), com revisão de termos e proteção dos trechos técnicos. Referência do modelo: https://huggingface.co/Helsinki-NLP/opus-mt-tc-big-en-pt .

## Seleção de skills em destaque

A biblioteca inclui pacotes em PT-BR de Encontrar skills (Vercel), Automação de navegador (Vercel), Boas práticas de React e Next.js (Vercel), Entrevista para validar ideias (Matt Pocock) e Vídeos e animações com Hyperframes (HeyGen). Design de interfaces, Criação de skills e Planilhas do Excel já estão disponíveis no acervo da Anthropic.

Cada novo pacote registra a fonte e sua revisão em ORIGEM.txt e preserva as licenças presentes na origem. A entrevista inclui sua dependência grilling; a automação inclui o guia core com referências e modelos. Hyperframes inclui o ponto de entrada e suas referências; os fluxos adicionais e o CLI são obtidos sob demanda conforme as instruções da fonte. Conteúdos buscados externamente também devem ser traduzidos para PT-BR antes do uso. Adicionar os pacotes não instala ferramentas no computador do aluno.

Esta importação acrescenta cinco registros, totalizando 1.303 entradas e 131 pacotes. Ela preserva títulos, descrições e publicação editados anteriormente pelo administrador.
