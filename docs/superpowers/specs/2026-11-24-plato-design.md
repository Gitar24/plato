# Plato: novo visual e nova personalidade

## Intenção
O pet passa a ser o Plato, um filósofo irônico e cínico, com visual mais simples.

## Aprovado
- Balão e caixa de pergunta: fundo preto, texto branco, borda cinza fina, fonte comum, sem `pet@news:~$`. A caixa mostra "Pergunte ao Plato...".
- Mascote: mesmo corpo azul; olhos de 6 para 3 pixels de largura; pernas de 7 para 3.
- Animação: a cada poucos segundos olha para um lado, para o outro e volta ao centro.
- Personalidade: filósofo irônico e cínico, em português claro, sem gírias; reflexão curta, às vezes com pergunta; tom respeitoso em tragédias (sem ironia).
- Nome Plato na personalidade, na caixa de pergunta e na saudação.

## Abordagens
- **Escolhida:** olhos desenhados pelo código em `pet/main.py` sobre um sprite sem olhos. Uma imagem só; posição dos olhos é um número.
- Quadros em PNG separados: mais arquivos para manter a cada ajuste de desenho.

## Fora do escopo
Intervalos, feeds, fila, e as notícias já enfileiradas (mantêm o texto antigo).

## Restrições
- O sprite atual é preservado como cópia.
- Mudança em `service/` exige `docker compose up -d --build`; o pet precisa ser reaberto.
