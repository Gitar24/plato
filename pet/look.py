"""Olhos, pernas e monóculo do Plato. Não usa Qt, então é fácil de testar."""

EYES = ((16, 8), (44, 8))  # canto de cima, à esquerda, de cada olho no desenho
EYE_W, EYE_H = 4, 8
LOOK = 3  # o quanto os olhos andam para o lado


def eye_offset(seconds):
    """A cada 6 s: olha para a frente por 3, para a esquerda por 1, para a direita por 1 e volta."""
    t = seconds % 6
    if 3 <= t < 4:
        return -LOOK
    if 4 <= t < 5:
        return LOOK
    return 0

LEGS_X = (12, 20, 40, 48)  # onde começa cada perna
LEG_TOP, LEG_W, LEG_H, LEG_LIFT = 32, 4, 8, 3


def leg_lengths(seconds):
    """As pernas se revezam em pares a cada meio segundo."""
    phase = int(seconds * 2) % 2
    return [LEG_H - (LEG_LIFT if i % 2 != phase else 0) for i in range(len(LEGS_X))]


def monocle_on(seconds):
    """O monóculo aparece por 10 s a cada 40 s."""
    return seconds % 40 >= 30
