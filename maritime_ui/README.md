# AgroLog Maritime Intelligence UI

Interface operacional da Maritime V1, construída com MapLibre + deck.gl e alimentada exclusivamente pelos endpoints `/v1/maritime/*` do AgroLog Gateway.

## Desenvolvimento local

1. execute o Gateway em `http://localhost:8080`;
2. nesta pasta, rode `npm install` e `npm run dev`;
3. abra a URL exibida pelo Vite.

Em desenvolvimento, a UI usa `http://localhost:8080` como Gateway por padrão. O endereço pode ser sobrescrito com `VITE_AGROLOG_GATEWAY_URL` ou pelo parâmetro `?api=`.

## Produção

O `gateway/Dockerfile` compila esta pasta e copia `dist/` para a imagem Python. O FastAPI serve a UI em:

`/maritime/`

A UI usa a mesma origem do Gateway em produção. O serviço Cloud Run continua com `--no-allow-unauthenticated`; para teste interativo sem alterar a política de acesso:

```bash
gcloud run services proxy agrolog-gateway --region southamerica-east1 --port 8080
```

Depois abra `http://localhost:8080/maritime/`.

## Regras da V1

- O mapa não contém coordenadas portuárias hardcoded ou aproximadas.
- O enquadramento por porto é calculado a partir das posições AIS realmente retornadas.
- `PROGRAMMED`, AIS observado e realizado permanecem evidências distintas.
- O replay é reconstruído do histórico próprio `shipping_ais_positions`.
- O mapa-base padrão é apenas um estilo de desenvolvimento e pode ser substituído por `VITE_MAP_STYLE_URL` ou `?style=` sem alterar a camada analítica.
- A ausência de DWT/carga realizada não é preenchida por estimativa silenciosa.
