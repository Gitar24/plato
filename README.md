# Plato

Um filósofo de pixel que mora na sua área de trabalho, comenta as notícias com ironia e responde às suas perguntas. Em tragédias, ele fala sério.

## Índice

1. [Como funciona](#como-funciona)
2. [Primeira instalação](#primeira-instalação)
   - [No Linux (Mint)](#no-linux-mint)
3. [No dia a dia](#no-dia-a-dia)
4. [Ajustes](#ajustes)
5. [Quando algo dá errado](#quando-algo-dá-errado)
6. [Referência](#referência)

Os comandos deste guia são para o PowerShell do Windows. No Linux, veja [No Linux (Mint)](#no-linux-mint); os comandos do `docker compose` são os mesmos. Rode tudo dentro da pasta do projeto:

```powershell
cd plato
```

## Como funciona

```text
  Feeds RSS ──▶  SERVIÇO (Docker)  ──▶  notas no Obsidian
                  │        ▲
     fila e chat  │        │  pergunta ao LLM (Gemini ou Anthropic)
                  ▼        ▼
               PET (Windows/Linux) LLM
```

O serviço (`service/`) lê um feed de cada vez, pede ao LLM um resumo e um comentário, grava a nota e põe a notícia numa fila. Ele atende só neste computador, em `127.0.0.1:8765`.

O pet (`pet/`) olha essa fila a cada poucos segundos e mostra a próxima notícia num pergaminho. As prioritárias chegam com um selo de cera.

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

### No Linux (Mint)

Testado pensando no Linux Mint com Cinnamon, que usa X11. Deve funcionar também no Ubuntu e em outras distribuições com X11.

1. Instale o Docker, o Python e a biblioteca de que o Qt precisa:

   ```bash
   sudo apt install docker.io docker-compose-v2 python3-venv libxcb-cursor0 x11-utils
   ```

   ```bash
   sudo usermod -aG docker $USER
   ```

   Saia da sessão e entre de novo para o grupo `docker` valer.

2. Crie o `.env` e preencha `GEMINI_API_KEY` e `OBSIDIAN_VAULT_PATH` (algo como `/home/voce/Documentos/MeuVault`):

   ```bash
   [ -f .env ] || cp .env.example .env
   ```

   Grave no `.env` o seu usuário e grupo. Assim as notas saem no seu nome, e não como root, e o Obsidian consegue editá-las:

   ```bash
   printf 'PUID=%s\nPGID=%s\n' "$(id -u)" "$(id -g)" >> .env
   ```

3. Ligue o serviço. Crie a pasta `data` antes, senão o Docker a cria como root:

   ```bash
   mkdir -p data && docker compose up -d --build
   ```

4. Prepare o Python do pet:

   ```bash2
   python3 -m venv ~/.local/venvs/plato
   ```

   ```bash
   ~/.local/venvs/plato/bin/pip install -r pet/requirements.txt feedparser APScheduler
   ```

5. Chame o Plato:

   ```bash
   ./run.sh pet
   ```

6. Para ele abrir junto com a sessão:

   ```bash
   ./run.sh autostart
   ```

   Ele aparece em "Aplicativos de inicialização" do Mint, onde dá para desligar.

O "não interromper em tela cheia" usa o `xprop` (do pacote `x11-utils`). Numa sessão Wayland não há como saber se algo está em tela cheia, então use o "Não perturbe". O `run.sh` já abre o pet pelo XWayland para ele conseguir ficar no canto da tela.

No Linux, troque `Invoke-RestMethod` por `curl`, por exemplo `curl http://127.0.0.1:8765/health`, e `.\run.ps1` por `./run.sh`.

## No dia a dia

O serviço volta sozinho quando o Docker inicia, a não ser que você mesmo o tenha parado. Para o pet abrir junto com o Windows, deixe um atalho dele na pasta de inicialização (`shell:startup`). No Linux, use `./run.sh autostart`.

### Conversar com o pet

| Você faz | Ele faz |
|---|---|
| Arrasta | Muda de lugar |
| Clica no pergaminho | Abre a notícia no navegador |
| Dá dois cliques | Abre o bilhete para você escrever uma pergunta |
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
| No Linux, o pet não abre e fala em "xcb" | Rode `sudo apt install libxcb-cursor0`. |
| No Linux, o Obsidian não consegue editar as notas | Elas foram gravadas como root. Ajuste `PUID`/`PGID` no `.env`, rode `sudo chown -R $USER: data <vault>/Noticias` e `docker compose up -d`. |
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

No Linux:

```bash
~/.local/venvs/plato/bin/python -m unittest discover -s tests
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
| `run.ps1` | Abre o pet ou o serviço sem Docker (Windows) |
| `run.sh` | O mesmo no Linux, e `autostart` para abrir com a sessão |
| `docker-compose.yml` | Como o serviço sobe no Docker |
