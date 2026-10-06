# LibreChat cockpit PoC

Objetivo: validar o LibreChat apenas como **interface/cockpit**, sem conceder acesso direto ao BigQuery.

## Boundary obrigatório

```text
LibreChat
  ↓ OpenAI-compatible/MCP/tool call
AgroLog Gateway
  ↓ permissões controladas
serviços/dados autorizados
```

Neste PoC, o AgroLog Gateway real é substituído por `mock_gateway.py`.

## Teste sem credenciais

1. Execute:

```bash
python experiments/radar_poc_suite/librechat/mock_gateway.py
```

2. Verifique:

```text
GET http://127.0.0.1:8765/healthz
GET http://127.0.0.1:8765/v1/models
```

3. Em uma instalação isolada do LibreChat, configure um endpoint OpenAI-compatible apontando para:

```text
http://127.0.0.1:8765/v1
```

A sintaxe exata de configuração do LibreChat deve ser retirada da documentação oficial da versão usada no momento do teste; este repositório não congela configuração de terceiros antes do PoC real.

## Critérios

- nenhuma credencial BigQuery no LibreChat;
- nenhuma credencial GCP no container/interface;
- usuário/grupo/RBAC devem ser testados antes de qualquer dado interno;
- logs não devem conter segredos;
- o cockpit precisa conseguir ser removido sem alterar o Gateway;
- qualquer ferramenta exposta ao cockpit deve estar allowlisted no Gateway.

## Fora de escopo

- autenticação de produção;
- SSO;
- dados reais;
- escrita em sistemas internos;
- acesso direto ao banco;
- instalação de Open WebUI em paralelo.
