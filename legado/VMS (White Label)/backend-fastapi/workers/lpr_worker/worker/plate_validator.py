"""Plate validator — Validação e correção OCR de placas Mercosul.

T2.2.1 — Módulo PlateValidator com regex Mercosul e correção OCR posicional.
"""
import re


class PlateValidator:
    """Valida e corrige placas Mercosul (formato antigo e novo).

    Formatos suportados pelo regex:
    - Antigo:        ABC1234  — 3 letras + 4 dígitos
    - Mercosul novo: ABC1D23  — 3 letras + 1 dígito + 1 letra + 2 dígitos

    Correção OCR por posição:
    - Posições 0-2   (obrigatório letra):  0→O, 1→I, 8→B, 5→S
    - Posições 3,5,6 (obrigatório dígito): O→0, I→1, B→8, S→5
    - Posição 4      (letra OU dígito):    tenta ambas as direções sem alterar
                                           o que já for válido
    """

    MERCOSUL_REGEX = r'^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$'

    # Conversões OCR em cada direção
    _DIGIT_TO_LETTER: dict[str, str] = {'0': 'O', '1': 'I', '8': 'B', '5': 'S'}
    _LETTER_TO_DIGIT: dict[str, str] = {'O': '0', 'I': '1', 'B': '8', 'S': '5'}

    def validate(self, raw: str) -> tuple[bool, str]:
        """Retorna (is_valid, corrected_plate).

        Normaliza para maiúsculo, remove caracteres não alfanuméricos,
        aplica correção OCR posicional e valida contra o regex Mercosul.
        Se is_valid=False, corrected_plate contém a melhor tentativa mesmo assim.
        """
        text = re.sub(r'[^A-Z0-9]', '', raw.upper())

        if len(text) != 7:
            return False, raw.strip().upper()

        chars = list(text)

        # Posições 0-2: devem ser letras — converte dígitos OCR para letras
        for i in range(3):
            chars[i] = self._DIGIT_TO_LETTER.get(chars[i], chars[i])

        # Posições 3, 5, 6: devem ser dígitos — converte letras OCR para dígitos
        for i in (3, 5, 6):
            chars[i] = self._LETTER_TO_DIGIT.get(chars[i], chars[i])

        # Posição 4: pode ser letra (Mercosul novo) ou dígito (formato antigo)
        # Testa: como está → versão dígito → versão letra (sem duplicatas, ordem preservada)
        p4_candidates = dict.fromkeys([
            chars[4],
            self._LETTER_TO_DIGIT.get(chars[4], chars[4]),
            self._DIGIT_TO_LETTER.get(chars[4], chars[4]),
        ])
        for p4 in p4_candidates:
            plate = ''.join(chars[:4]) + p4 + ''.join(chars[5:])
            if re.match(self.MERCOSUL_REGEX, plate):
                return True, plate

        # Retorna melhor tentativa corrigida mesmo que inválida
        return False, ''.join(chars)


# ── Testes unitários ──────────────────────────────────────────────────────────

if __name__ == '__main__':
    import sys

    _validator = PlateValidator()
    _passed = 0
    _failed = 0

    def _check(desc: str, raw: str, exp_valid: bool, exp_plate: str) -> None:
        global _passed, _failed
        valid, plate = _validator.validate(raw)
        ok = valid == exp_valid and plate == exp_plate
        tag = 'PASS' if ok else 'FAIL'
        print(f'  {tag}  {desc}')
        if not ok:
            _failed += 1
            print(f'         input    = {raw!r}')
            print(f'         expected = ({exp_valid!r}, {exp_plate!r})')
            print(f'         got      = ({valid!r}, {plate!r})')
        else:
            _passed += 1

    print('PlateValidator — testes unitários\n')

    # ── Placas válidas sem correção ───────────────────────────────────────────
    print('[ Placas válidas — sem correção ]')
    _check('formato antigo, sem correção',       'ABC1234',   True,  'ABC1234')
    _check('Mercosul novo, sem correção',        'ABC1D23',   True,  'ABC1D23')
    _check('Mercosul novo, dígito na pos 4',     'ABC1023',   True,  'ABC1023')

    # ── Normalização de entrada ───────────────────────────────────────────────
    print('\n[ Normalização ]')
    _check('entrada minúscula',                  'abc1234',   True,  'ABC1234')
    _check('espaços removidos',                  'ABC 1234',  True,  'ABC1234')
    _check('hífen removido',                     'ABC-1234',  True,  'ABC1234')

    # ── Correção OCR nas posições de letras (0-2) ─────────────────────────────
    print('\n[ Correção OCR — posições 0-2 (devem ser letras) ]')
    _check('pos 0: 0→O  (antigo)',               '0BC1234',   True,  'OBC1234')
    _check('pos 1: 1→I',                         'A1C1234',   True,  'AIC1234')
    _check('pos 2: 8→B',                         'AB81234',   True,  'ABB1234')
    _check('pos 2: 5→S  (Mercosul novo)',         'AB51D23',   True,  'ABS1D23')

    # ── Correção OCR nas posições de dígitos (3, 5, 6) ────────────────────────
    print('\n[ Correção OCR — posições 3, 5, 6 (devem ser dígitos) ]')
    _check('pos 3: O→0  (antigo)',               'ABCO234',   True,  'ABC0234')
    _check('pos 3: I→1  (Mercosul novo)',         'ABCID23',   True,  'ABC1D23')
    _check('pos 5: I→1',                         'ABC12I4',   True,  'ABC1214')
    _check('pos 6: S→5',                         'ABC123S',   True,  'ABC1235')
    _check('pos 6: B→8',                         'ABC123B',   True,  'ABC1238')

    # ── Múltiplas correções ───────────────────────────────────────────────────
    print('\n[ Múltiplas correções ]')
    _check('pos 0 (0→O) + pos 3 (O→0)',          '0BCO234',   True,  'OBC0234')
    _check('Mercosul novo + pos 0 (0→O)',         '0BC1D23',   True,  'OBC1D23')
    _check('pos 3 (O→0) + pos 6 (S→5)',          'ABCO23S',   True,  'ABC0235')
    _check('pos 0 + pos 3 + pos 5 (I→1)',        '0BCO2I4',   True,  'OBC0214')

    # ── Placas inválidas ──────────────────────────────────────────────────────
    print('\n[ Placas inválidas ]')
    _check('comprimento 6 (curta)',               'ABC123',    False, 'ABC123')
    _check('comprimento 8 (longa)',               'ABC12345',  False, 'ABC12345')
    _check('pos 3 e 5 não corrigíveis (D, F)',    'ABCDEF7',   False, 'ABCDEF7')
    _check('pos 1 não corrigível (2)',            'A2C1234',   False, 'A2C1234')
    _check('entrada vazia',                       '',          False, '')

    # ── Resumo ────────────────────────────────────────────────────────────────
    total = _passed + _failed
    print(f'\nResultado: {_passed}/{total} passaram, {_failed} falharam')
    if _failed:
        sys.exit(1)
