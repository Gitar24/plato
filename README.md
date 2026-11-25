# Plato

Um filósofo de pixel que mora na sua área de trabalho, comenta as notícias com ironia e responde às suas perguntas. Em tragédias, ele fala sério.

## Índice

1. [Como funciona](#como-funciona)
2. [Primeira instalação](#primeira-instalação)
3. [No dia a dia](#no-dia-a-dia)
4. [Ajustes](#ajustes)
5. [Quando algo dá errado](#quando-algo-dá-errado)
6. [Referência](#referência)

Todos os comandos são para o PowerShell, dentro da pasta do projeto:

```powershell
cd plato
```

## Como funciona

```text
  Feeds RSS ──▶  SERVIÇO (Docker)  ──▶  notas no Obsidian
                  │        ▲
     fila e chat  │        │  pergunta ao LLM (Gemini ou Anthropic)
                  ▼        ▼
               PET (Windows)       LLM
```

O serviço (`service/`) lê um feed de cada vez, pede ao LLM um resumo e um comentário, grava a nota e põe a notícia numa fila. Ele atende só neste computador, em `127.0.0.1:8765`.

O pet (`pet/`) olha essa fila a cada poucos segundos e mostra a próxima notícia num balão.

Algumas coisas que ele faz sozinho:

- Não repete notícia. O que já foi visto fica em `data/history.json`.
- Não interrompe. Com algo em tela cheia, ou com "Não perturbe" ligado, a notícia espera na fila.
- Pausa a coleta quando há 5 notícias esperando.
- Adianta a próxima busca quando a notícia é prioritária: tem a ver com notas anteriores, o LLM a marcou como importante ou o título tem uma das `priority_keywords`.
- Liga as notas relacionadas com `[[links]]`, em `<vault>/Noticias/`.

## Primeira instalação

Você precisa do Docker Desktop, do Python e de uma chave do LLM ([chave do Gemini](https://aistudio.google.com/apikey)).

1. Crie o `.env` (se ele já existir, nada é sobrescrito):

   ```powershell
   if (-not (Test-Path .env)) { copy .env.example .env }
   ```

2. Abra o `.env` e preencha `GEMINI_API_KEY` e `OBSIDIAN_VAULT_PATH`.

3. Ligue o serviço:

   ```powershell
   docker compose up -d --build
   ```

4. Prepare o Python do pet:

   ```powershell
   python -m venv $env:USERPROFILE\.local\venvs\plato
   ```

   ```powershell
   & $env:USERPROFILE\.local\venvs\plato\Scripts\pip.exe install -r pet\requirements.txt feedparser APScheduler
   ```

5. Chame o Plato:

   ```powershell
   .\run.ps1 pet
   ```

## No dia a dia

O serviço volta sozinho quando o Docker inicia, a não ser que você mesmo o tenha parado. Para o pet abrir junto com o Windows, deixe um atalho dele na pasta de inicialização (`shell:startup`).

### Conversar com o pet

| Você faz | Ele faz |
|---|---|
| Arrasta | Muda de lugar |
| Clica no balão | Abre a notícia no navegador |
| Dá dois cliques | Abre a caixa de perguntas |
| Clica com o botão direito | Mostra o menu: "Conversar", "Não perturbe" e "Sair" |

### Cuidar do serviço

| Para | Comando |
|---|---|
| Ligar (e aplicar mudanças do `.env`) | `docker compose up -d` |
| Aplicar mudanças no código de `service\` | `docker compose up -d --build` |
| Ver se está de pé | `docker compose ps` |
| Acompanhar os logs (`Ctrl+C` sai) | `docker compose logs -f --tail 50` |
| Reiniciar, sem reler o `.env` | `docker compose restart` |
| Desligar | `docker compose stop` |
| Desligar e remover o container | `docker compose down` |

O histórico e as notas continuam no lugar mesmo depois do `down`.

## Ajustes

| Quero mudar | Onde | Para valer |
|---|---|---|
| Chaves e pasta do vault | `.env` | `docker compose up -d` |
| Modo (`production` ou `test`) | `NEWS_MODE` no `.env` | `docker compose up -d` |
| Intervalos, feeds, palavras de prioridade | `config\config.json` | Sozinho, no próximo ciclo |
| Modelo e provedor do LLM | `llm` no `config\config.json` | Sozinho |
| Tamanho da fila | `max_pending` no `config\config.json` | Sozinho, no próximo ciclo |
| Personalidade | `persona` no `config\config.json`, ou `DEFAULT_PERSONA` em `service\llm.py` | O JSON vale sozinho; o código pede `--build` |

### Modos

| Modo | Intervalo normal | Depois de notícia prioritária |
|---|---|---|
| `production` | 15 min | 7 min |
| `test` | 60 s | 30 s |

O `NEWS_MODE` do `.env` vale mais que o campo `mode` do JSON. Para o JSON mandar, apague o `NEWS_MODE` e rode `docker compose up -d` uma vez.

O modo `test` gasta a cota do LLM bem depressa.

### Sem a chave do LLM

A coleta continua, usando o resumo do próprio feed e ligando as notas por palavras em comum. O chat não funciona.

## Quando algo dá errado

Comece por aqui:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/health
```

A resposta mostra o `mode` que está rodando de verdade e quantas notícias esperam (`pending`).

| Sintoma | O que fazer |
|---|---|
| Mudei o `.env` e nada aconteceu | Rode `docker compose up -d`. O `restart` não relê o arquivo. |
| O pet não fala nada | Veja o `/health`. Ele também fica quieto com tela cheia ou "Não perturbe". |
| "coleta pausada" nos logs | A fila encheu. Abra o pet para ele falar o que está esperando. |
| O chat não responde | Confira a chave no `.env` e procure `[llm] erro` nos logs. |
| Erro 429 nos logs | A cota do LLM acabou. Espere renovar, aumente os intervalos ou troque de modelo. |

## Referência

### API local

| Comando | O que faz |
|---|---|
| `Invoke-RestMethod http://127.0.0.1:8765/health` | Só consulta o estado |
| `Invoke-RestMethod http://127.0.0.1:8765/next` | Entrega a notícia mais antiga e a tira da fila. O pet não vai mais falar essa. |

Para conversar sem o pet (gasta cota do LLM):

```powershell
$body = [Text.Encoding]::UTF8.GetBytes((@{ message = "Quais as novidades?" } | ConvertTo-Json))
(Invoke-RestMethod http://127.0.0.1:8765/chat -Method Post -ContentType "application/json" -Body $body).reply
```

### Rodar o serviço sem Docker

Os dois usam a porta 8765, então pare o do Docker antes:

```powershell
docker compose stop
```

```powershell
.\run.ps1 service
```

`Ctrl+C` encerra. Esse modo usa o Python de `.local\venvs\plato` e lê o `.env` da pasta.

### Testes

```powershell
& $env:USERPROFILE\.local\venvs\plato\Scripts\python.exe -m unittest discover -s tests
```

### Pastas

| Caminho | O que tem |
|---|---|
| `service\` | Coleta, análise, notas e API |
| `pet\` | O personagem |
| `config\config.json` | Ajustes |
| `data\` | Histórico e fila |
| `tests\` | Testes |
| `docs\` | Plano e desenho do Plato |
| `run.ps1` | Abre o pet ou o serviço sem Docker |
| `docker-compose.yml` | Como o serviço sobe no Docker |
