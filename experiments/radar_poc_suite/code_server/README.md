# code-server PoC

Objetivo: permitir acesso ao ambiente de desenvolvimento pelo navegador sem transformar code-server em componente do runtime do AgroLog.

## Regras obrigatórias

- usar `config.yaml.example` com bind em `127.0.0.1`;
- nunca expor diretamente `0.0.0.0:8080` à internet;
- senha/token somente por secret runtime, nunca no GitHub;
- acesso remoto somente atrás de IAP/VPN/Zero Trust/reverse proxy autenticado equivalente;
- usar HTTPS na camada externa;
- manter credenciais GCP/GitHub com permissões mínimas;
- registrar acesso quando a infraestrutura escolhida permitir;
- não montar diretórios de segredos desnecessários;
- não tornar code-server requisito para Cloud Run, Gateway, coletores ou BigQuery.

## PoC local

1. Instale code-server seguindo a documentação oficial da versão corrente.
2. Copie `config.yaml.example` para uma localização local fora do GitHub.
3. Defina `PASSWORD` por mecanismo seguro do sistema/sessão.
4. Inicie o serviço somente em localhost.
5. Para acesso remoto, coloque uma camada autenticada na frente; não altere o bind para público apenas por conveniência.

## Critério de promoção

Só adotar se resolver uma necessidade concreta de acesso ao notebook/VM e se o benefício superar a superfície adicional de ataque. Caso contrário, permanecer fora da arquitetura operacional.
