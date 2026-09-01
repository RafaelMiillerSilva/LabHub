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

    linhas = []
    if getattr(equip, 'modelo', None):
        linhas.append(f"Modelo: {equip.modelo}")
    
    linhas.extend([
        f"Identificação: {equip.identificacao_escola or '—'}",
        f"Patrimônio: {equip.numero_patrimonio or '—'}",
        f"Nº de série: {equip.numero_serie or '—'}",
    ])
    
    if equip.imei:
        linhas.append(f"IMEI 1: {equip.imei}")
    if getattr(equip, 'imei_2', None):
        linhas.append(f"IMEI 2: {equip.imei_2}")

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


def gerar_etiquetas_a4_pdf(equips):
    """
    Gera um buffer PDF contendo as etiquetas dos equipamentos
    organizadas em páginas A4 (até 10 por página).
    """
    A4_W, A4_H = 1240, 1754
    L_W, L_H = 520, 300
    
    margem_x = (A4_W - (2 * L_W)) // 3
    margem_y = (A4_H - (5 * L_H)) // 6

    paginas = []
    pagina_atual = None
    
    for i, equip in enumerate(equips):
        img_etiqueta = gerar_etiqueta_png(equip)
        
        idx_na_pagina = i % 10
        if idx_na_pagina == 0:
            pagina_atual = Image.new('RGB', (A4_W, A4_H), 'white')
            paginas.append(pagina_atual)
            
        linha = idx_na_pagina // 2
        coluna = idx_na_pagina % 2
        
        pos_x = margem_x + coluna * (L_W + margem_x)
        pos_y = margem_y + linha * (L_H + margem_y)
        
        if pagina_atual:
            pagina_atual.paste(img_etiqueta, (pos_x, pos_y))
        
    buffer = io.BytesIO()
    if paginas:
        primeira = paginas[0]
        demais = paginas[1:]
        primeira.save(buffer, 'PDF', resolution=150.0, save_all=True, append_images=demais)
        
    buffer.seek(0)
    return buffer
