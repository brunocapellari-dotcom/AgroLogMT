# AgroLog ZERO_COST — histórico, qualidade e recuperação local

Este pacote acrescenta **auditoria de histórico somente leitura** e **backup/restauração autenticados**, sem GitHub Actions, GCP, cloud paga ou alteração dos coletores homologados.

## 1. Auditoria de dados históricos

Após coleta e materialização reais:

```bash
.venv-zero-cost/bin/python scripts/audit_zero_cost_history.py --db .agrolog-zero-cost/analytics/agrolog.duckdb --out outputs/zero-cost-historical-quality.json
```

No Windows, substituir o Python acima por `.venv-zero-cost\\Scripts\\python.exe`. Ajustar o caminho `--db` para o `root` real da configuração do operador.

O relatório apresenta contagem e cobertura temporal por tabela, nulidade de datas de referência/coleta, rastreabilidade por hash, inconsistências de disponibilidade point-in-time, publicação posterior à coleta e duplicatas por registro/snapshot quando as colunas existem. Um CHECK PASS prova somente as verificações executadas, **não** comprova histórico completo, comercialização observada, frescor das fontes nem validade científica de previsão.

## 2. Backup offline e seguro

**Interromper coletores e demais processos que gravem no diretório ZERO_COST antes do backup.** Em produção, registrar a janela de parada no log operacional. Não executar backup simultaneamente com coleta ou geração de Parquet.

O destino precisa estar em **disco/volume criptografado, diferente do volume operacional, com acesso restrito**. O script **não cifra os dados**; o argumento de confirmação responsabiliza o operador por essa verificação externa. Os artefatos podem conter dados comercialmente sensíveis. O script bloqueia alguns nomes conhecidos de arquivos de credenciais, mas isso não substitui uma inspeção da fonte.

Criar uma chave aleatória de no mínimo 32 bytes, em hexadecimal, armazená-la fora do repositório (cofre de segredos ou gerenciador de senhas), e carregá-la apenas na sessão do operador como `AGROLOG_BACKUP_HMAC_KEY`. Essa chave autentica os manifestos do backup; **não é uma chave de criptografia de arquivos**. Sem a mesma chave não é possível verificar ou restaurar.

```bash
.venv-zero-cost/bin/python scripts/zero_cost_recovery.py backup \
  --root .agrolog-zero-cost \
  --output-dir maritime_ui/public/data \
  --destination /CAMINHO/DO/VOLUME-CRIPTOGRAFADO/agrolog-backup-001 \
  --quiesced --encrypted-destination-confirmed
```

O script copia o banco DuckDB, Parquet, RAW, estado e produtos locais do perfil ZERO_COST; guarda manifesto, tamanho e SHA-256 de cada arquivo; assina o manifesto com HMAC; revalida tudo antes de promover a pasta de staging. Se encontrar fonte modificada, symlink, material com nomes de credencial conhecidos ou dados inconsistentes, falha sem publicar o backup. O banco é aberto em modo read-only durante a cópia para detectar locks ativos, mas isso **não garante consistência dos demais arquivos se outro processo ignorar a parada operacional**.

## 3. Verificar e restaurar sem destruir produção

```bash
.venv-zero-cost/bin/python scripts/zero_cost_recovery.py verify --snapshot /CAMINHO/DO/BACKUP
.venv-zero-cost/bin/python scripts/zero_cost_recovery.py restore \
  --snapshot /CAMINHO/DO/BACKUP \
  --root /CAMINHO/NOVO/runtime-restaurado \
  --output-dir /CAMINHO/NOVO/output-restaurado
```

A restauração **recusa destinos já existentes**. Depois de restaurar, executar a auditoria histórica contra o banco recuperado, conferir o produto comercial, testar o pipeline em modo apropriado e comparar os hashes. Apenas uma cópia concluída não é prova de desastre recuperável; o ensaio efetivo deve ser documentado.

## 4. Estado de release

Este código é candidato de melhoria, não GO_LIVE_PASS. O desenvolvimento remoto pode ocorrer sem runner. **Faltam:** testes Python reais no SHA da PR, auditoria com o DuckDB histórico do operador, backup em volume criptografado e restore drill completo com o runtime parado. Os resultados devem ser registrados como evidência de release, sem afirmar automaticamente que toda a série histórica está completa ou livre de vieses.
