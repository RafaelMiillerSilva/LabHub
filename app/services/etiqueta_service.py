"""
Serviço para geração de etiquetas de identificação de equipamentos (PNG e ZIP).
"""

import io
import zipfile
from PIL import Image, ImageDraw, ImageFont


def _obter_fonte(tam, negrito=False):
    nomes = (
        ['DejaVuSans-Bold.ttf', 'arialbd.ttf']
        if negrito
        else ['DejaVuSans.ttf', 'arial.ttf']
    )
    for nome in nomes:
        try:
            return ImageFont.truetype(nome, tam)
        except Exception:
            continue
    return ImageFont.load_default()


def gerar_etiqueta_png(equip):
    """
    Gera a imagem PNG da etiqueta do equipamento.
    """
    W, H = 520, 300
    AZUL = (30, 60, 114)
    img = Image.new('RGB', (W, H), 'white')
    d = ImageDraw.Draw(img)

    d.rectangle([4, 4, W - 5, H - 5], outline=AZUL, width=4)
    d.rectangle([4, 4, W - 5, 58], fill=AZUL)
    d.text((20, 16), equip.apelido or '—', fill='white', font=_obter_fonte(30, True))
    d.text((W - 200, 22), equip.get_categoria_display(), fill='white', font=_obter_fonte(18, True))

    linhas = [
        f"Identificação: {equip.identificacao_escola or '—'}",
        f"Patrimônio: {equip.numero_patrimonio or '—'}",
        f"Nº de série: {equip.numero_serie or '—'}",
    ]
    if equip.fixo and equip.sala:
        linhas.append(f"Sala: {equip.sala.nome}")
    if equip.imei:
        linhas.append(f"IMEI: {equip.imei}")

    fonte = _obter_fonte(20)
    y = 78
    for ln in linhas:
        d.text((24, y), ln, fill=(35, 35, 35), font=fonte)
        y += 34

    return img


def gerar_etiquetas_zip(equips):
    """
    Gera um buffer ZIP contendo as etiquetas PNG dos equipamentos informados.
    """
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for equip in equips:
            img = gerar_etiqueta_png(equip)
            png_bytes = io.BytesIO()
            img.save(png_bytes, 'PNG')
            zf.writestr(f'etiqueta_{equip.apelido}.png', png_bytes.getvalue())
    buffer.seek(0)
    return buffer
