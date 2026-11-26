# Fluxo seguro: plano

**Spec:** `docs/superpowers/specs/2026-11-26-fluxo-seguro-design.md`

Execução direta na sessão, com teste antes do código. Sem commits até o usuário pedir.

1. `service/store.py`: gravação atômica, arquivo corrompido preservado, histórico de 500, falhas por notícia, fila com `peek_pending(max_age)` e `ack(id)`, busca para o chat. Testes em `tests/test_service.py`.
2. `service/llm.py` e `service/app.py`: `Unusable` para resposta inutilizável (conta tentativa; erro de rede não conta), limite de 3, `duplicate_of`, idade máxima, alternância de fontes, `/ack`, `HOST`. Testes no mesmo arquivo.
3. `service/vault.py`: tag sem acento, nome único, YAML entre aspas.
4. `pet/safety.py` e `pet/main.py`: `safe_link(url)`, domínio visível, texto escapado, clique só no pergaminho, confirmação com `/ack`. Testes em `tests/test_safety.py`.
5. README, `config.json`, Dockerfile e compose. Reconstruir o serviço mantendo o `.env`, os dados e o vault atuais, e abrir o pet.

## Riscos a revisar
- Queda do LLM não pode descartar notícias.
- Pet não pode repetir uma notícia se o `/ack` falhar.
- Endereços disfarçados (`https://banco.com@mal.com`, IP numérico, barra invertida) não podem abrir.
