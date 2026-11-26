# Plato: clique seguro, notícias frescas e sem repetição

## Intenção
Poder clicar numa notícia com segurança, ouvir só notícias recentes e não ouvir o mesmo fato duas vezes. A coleta não pode ficar presa numa notícia que falha.

## Decidido com o usuário
- Notícia com mais de 4 dias é velha.
- Ritmo: opção A, sempre o mais fresco. O que sobrar e envelhecer é descartado em silêncio. O ritmo de coleta não muda.
- O Plato não repete o que já falou, exceto quando o usuário pergunta ou quando um fato novo se liga a uma notícia já dita.
- Corrigir os problemas apontados na análise.
- Limitar as tentativas numa notícia que falha e passar para outra.

## Desenho (proposto)

### Frescor
- Vale a data de publicação do feed (ou a de atualização, se não houver). Sem data, é descartada.
- Limite em `max_age_days: 4` no `config.json`.
- A idade é conferida na coleta e de novo na entrega.
- A coleta olha todos os itens de cada feed, e não só 15. Escolhe a fonte usada há mais tempo e, nela, a notícia mais nova.
- A fila entrega a publicada mais recentemente primeiro. Continua com 5 lugares.

### Repetição
- O LLM, na mesma chamada da análise, recebe os títulos dos últimos 4 dias (ditos e na fila) e informa se a notícia é o mesmo fato de algum.
- Mesmo fato: marcada como vista, sem nota e sem fala. O ciclo tenta a próxima, com no máximo 3 chamadas ao LLM por ciclo.
- Fato novo sobre assunto já dito: é falada, e o comentário cita a anterior.
- Sem chave do LLM: só link igual ou título quase igual.

### Perguntas
- O histórico passa a guardar 500 notícias.
- O chat recebe as 10 últimas e as que combinam com as palavras da pergunta.

### Tentativas
- Resposta inutilizável ou bloqueada conta contra a notícia. Na terceira, ela é descartada.
- Cota esgotada, rede fora, tempo esgotado ou chave inválida não contam, para uma queda não descartar notícias boas.
- A contagem fica no `history.json`.

### Clique
- Só abre `https`. Recusa IP direto, usuário ou senha no endereço, porta incomum e domínio em punycode. A conferência é feita no pet, na hora de abrir.
- O pergaminho mostra o domínio. Link recusado aparece como "link não aberto".
- Só o clique no pergaminho abre. Duplo clique no personagem não abre o navegador, e resposta do chat não tem link.
- Texto do feed e do LLM é escapado antes de ir para o balão.
- Não garante que o site seja seguro.

### Demais correções
- A API escuta em `127.0.0.1` por padrão. O Docker define `0.0.0.0` dentro do container e continua publicando só no computador.
- `history.json` é gravado num arquivo temporário e trocado de uma vez. Arquivo corrompido é renomeado e preservado.
- A notícia só sai da fila depois que o pet confirma que a mostrou (`GET /next` e depois `POST /ack`).
- Notas: tags sem acento ("politica"), título repetido ganha sufixo, campos do YAML entre aspas.

## Abordagens para detectar repetição
- **Escolhida:** o LLM decide na chamada que já existe. Entende títulos diferentes sobre o mesmo fato; custa alguns tokens a mais e pode errar.
- Comparar palavras dos títulos: de graça, mas confunde continuação com repetição.
- Embeddings: mais preciso na semelhança, porém outra API, mais cota e não separa fato novo de repetido.

## Fora do escopo
Mudar intervalos, ler o artigo inteiro, verificação de links por serviço externo, notas já gravadas.

## Efeitos na primeira execução
As notícias hoje na fila não têm data e serão descartadas.

## Testes
Um teste para cada regra acima, sem rede e sem gastar cota. Aplicar exige `docker compose up -d --build` e reabrir o pet.
