# Central de Skills integrada

Acervo importado da pasta Central de Skills do professor: 1.172 entradas do catálogo em 90 categorias e 141 pacotes com SKILL.md. O catálogo conserva os links de origem. As entradas de catálogo não representam pacotes testados ou compatibilidade garantida com Claude web.

Os pacotes conservam scripts, referências, exemplos e dependências compartilhadas presentes no acervo. Os pacotes técnicos podem exigir Claude Code, MCP, terminal e outros serviços. Os arquivos são fornecidos para download e nunca executados pelo site.

## Alunos e administração

Alunos autenticados acessam a Biblioteca de Skills, pesquisam todo o acervo, filtram por categoria e ferramenta e carregam mais resultados. Cada pacote publicado pode ser baixado pela sua rota autenticada. O administrador pesquisa, edita, publica e retira itens e pode baixar o acervo completo. A retirada bloqueia o download individual. O ZIP completo é administrativo e contém o acervo original, inclusive itens retirados da biblioteca.

## Importação e hospedagem

O backend importa os registros uma única vez, ao primeiro acesso autorizado à biblioteca. IDs reservados e uma marca de versão impedem duplicação ou restauração de itens retirados pelo administrador. O banco existente e os cadastros de alunos são preservados.

O pacote Hostinger inclui skills-catalog.json, skills-packages.json e CENTRAL-LICENSE.txt em formacao-private, fora de public_html. O backend Python usa os mesmos dados em server, cujo acesso HTTP é bloqueado. Os arquivos de configuração e credenciais não fazem parte do pacote. A instalação segue docs/HOSTINGER.md.

Na implantação automática do repositório pelo GitHub, o PHP lê o acervo atualizado de server/ dentro do projeto, protegido pelo bloqueio HTTP do .htaccess. Na instalação por ZIP, usa formacao-private. Ambos importam o catálogo no primeiro acesso autenticado e mantêm os downloads protegidos, sem exigir a cópia manual dos arquivos para a pasta privada.

Publicar HTML pelo GitHub não ativa sozinho PHP/MySQL. Para confirmar a implantação, /api/session precisa responder JSON e /healthz precisa responder ok. Um 404 nessas rotas indica que a área privada ainda não está operando nesse domínio.
