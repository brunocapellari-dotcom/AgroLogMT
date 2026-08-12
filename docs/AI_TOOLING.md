# Ferramentas de IA e Extensões

Este documento é o registro canônico de ferramentas externas, skills e extensões avaliadas para o AgroLog MT. Ele complementa `docs/REPOSITORY_GOVERNANCE.md` e não substitui a arquitetura do projeto.

## Regra de incorporação

- Não copiar repositórios externos inteiros para dentro do AgroLog MT sem necessidade técnica comprovada.
- Não instalar skills automaticamente a partir de listas ou catálogos.
- Toda ferramenta externa deve ser avaliada quanto a segurança, manutenção, licença, sobreposição funcional, acesso a credenciais e impacto no fluxo atual.
- Quando uma ferramenta apenas orientar o comportamento do Claude/Codex, preferir configuração/instrução do agente em vez de duplicar código no repositório.
- Dependências externas aprovadas devem ser registradas aqui com função e status.

## Estado atual

### Aprovado para adoção controlada

**Superpowers**
- Função: disciplina de planejamento, implementação, teste, depuração e revisão antes de concluir mudanças.
- Uso pretendido: Claude Code e, quando compatível, outros agentes de desenvolvimento.
- Regra: não substitui `CLAUDE.md`, governança do repositório, testes próprios nem revisão humana/agêntica.
- Status: aprovado para instalação/configuração controlada no ambiente Claude; não vendorizado no repositório.

### Piloto posterior

**Claude Mem**
- Função: memória entre sessões.
- Risco principal: recuperar contexto antigo ou duplicar informação já canônica no GitHub.
- Regra: o GitHub continua sendo a fonte de verdade. Memória nunca prevalece sobre arquivos canônicos atuais.
- Status: testar somente depois do fluxo GitHub + Claude estar estável.

**Auditoria / doctor do ambiente Claude**
- Função: identificar skills, hooks, plugins e configurações desnecessárias ou quebradas.
- Status: conceito aprovado; implementação específica deve ser validada antes de instalar.

**Code review multiagente**
- Função: revisão independente de alterações antes de merge.
- Status: incorporar após estabilização do pipeline principal.

### Futuro operacional

**Strix**
- Função: testes de segurança/pentest controlado.
- Regra: apenas em ambiente isolado e autorizado; não executar livremente contra produção.
- Status: futuro.

**Evolution API**
- Função: integração de WhatsApp para alertas/atendimento quando houver produto operacional.
- Status: futuro; fora do núcleo atual de dados.

### Não incorporar ao núcleo agora

- Agent Reach: superfície de ataque e dependência de sessões/cookies locais desnecessárias ao núcleo.
- OmniRoute e roteadores de centenas de modelos: aumentam variabilidade e complexidade do ambiente neste estágio.
- Listas de centenas de APIs/modelos grátis: não são arquitetura de produção.
- Task Observer/autoevolução de skills: não permitir alteração autônoma da governança ou das skills sem revisão.
- Obsidian/segundo cérebro paralelo: evitar nova fonte de verdade; GitHub + Drive + BigQuery cumprem responsabilidades distintas.
- Skills de design: adiar até existir demanda real de frontend.
- Otimizadores de token/contexto não validados: somente testar quando houver problema medido.

## Princípio operacional

Ferramenta nova entra apenas se resolver uma necessidade concreta sem criar uma segunda fonte de verdade, duplicar uma capacidade já existente ou ampliar desnecessariamente a superfície de segurança do AgroLog MT.
