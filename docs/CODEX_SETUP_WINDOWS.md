# Codex no notebook Windows — passo a passo

## Objetivo

Instalar o Codex CLI no mesmo notebook do Claude Code e permitir que Claude invoque Codex via MCP como revisor independente do AgroLog MT.

## 1. Instalar

Com Node.js/npm disponível:

```powershell
npm install -g @openai/codex
codex --version
```

Se npm não estiver disponível, usar o instalador oficial do Codex para Windows conforme a documentação da OpenAI.

## 2. Autenticar

Execute:

```powershell
codex
```

Na primeira execução, concluir o login com a conta ChatGPT no fluxo interativo apresentado pelo Codex.

## 3. Abrir o repositório

```powershell
cd C:\AgroLogMT
```

## 4. Verificar MCP

O repositório possui `.mcp.json` com o servidor `codex` apontando para `codex mcp-server`.

```powershell
claude mcp list
claude mcp get codex
```

Se a configuração de projeto precisar ser recriada:

```powershell
claude mcp add codex --scope project -- codex mcp-server
claude mcp list
```

## 5. Teste sem alterações

No Claude Code, solicitar que Claude leia `CLAUDE.md` e `docs/MULTI_AGENT_WORKFLOW.md`, chame Codex via MCP para revisar a arquitetura e retorne a análise sem alterar arquivos.

## 6. Teste com alteração pequena

Solicitar uma mudança documental pequena. Fluxo esperado:

plano Claude → revisão Codex → edição Claude → testes/diff → revisão final Codex.

Não fazer push no primeiro teste.

## 7. Aprovação

Considerar a integração aprovada quando:
- Claude listar o servidor `codex`;
- Codex responder dentro do fluxo do Claude;
- Claude distinguir sua análise da revisão Codex;
- uma mudança pequena completar o ciclo de revisão sem duplicação.

## Referências

Consultar somente documentação oficial OpenAI Codex e Anthropic Claude Code/MCP para comandos e atualizações de instalação.
