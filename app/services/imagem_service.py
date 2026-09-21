"""
Serviço centralizado de processamento e sanitização de imagens do LabHub.
Evita corrupção de imagens, trata orientação EXIF de fotos de celulares,
gerencia canais de transparência e redimensiona com alta nitidez.
"""

import io
import os
from PIL import Image, ImageOps
from django.core.files.base import ContentFile


def processar_imagem(arquivo, max_lado=1920, qualidade=85, formato='JPEG'):
    """
    Abre, corrige rotação EXIF, ajusta transparência e comprime a imagem.
    Garante seek(0) antes e depois da leitura para evitar corrupção por streams lidos.
    Retorna: (bytes_da_imagem, mime_type)
    """
    if hasattr(arquivo, 'seek'):
        try:
            arquivo.seek(0)
        except Exception:
            pass

    try:
        img = Image.open(arquivo)
    except Exception as e:
        raise ValueError(f"Não foi possível abrir o arquivo como imagem válida: {e}")

    # Corrige orientação de câmeras de smartphones baseada nos metadados EXIF
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    # Trata transparência (RGBA, LA, P) preenchendo com fundo branco para JPEG
    if formato.upper() in ('JPEG', 'JPG'):
        if img.mode in ('RGBA', 'LA', 'P'):
            bg = Image.new('RGB', img.size, (255, 255, 255))
            if img.mode == 'P':
                img = img.convert('RGBA')
            if 'A' in img.getbands():
                bg.paste(img, mask=img.split()[-1])
            else:
                bg.paste(img)
            img = bg
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        mime = 'image/jpeg'
    elif formato.upper() == 'PNG':
        mime = 'image/png'
    elif formato.upper() == 'WEBP':
        mime = 'image/webp'
    else:
        mime = 'image/jpeg'
        formato = 'JPEG'

    # Redimensiona proporcionalmente mantendo alta nitidez se exceder max_lado
    largura, altura = img.size
    if largura > max_lado or altura > max_lado:
        img.thumbnail((max_lado, max_lado), Image.Resampling.LANCZOS)

    buf = io.BytesIO()
    save_kwargs = {'format': formato, 'quality': qualidade}
    if formato.upper() in ('JPEG', 'JPG', 'WEBP'):
        save_kwargs['optimize'] = True

    img.save(buf, **save_kwargs)
    dados = buf.getvalue()

    if hasattr(arquivo, 'seek'):
        try:
            arquivo.seek(0)
        except Exception:
            pass

    return dados, mime


def processar_foto_para_storage(arquivo, nome_original='', max_lado=1920, qualidade=85):
    """
    Processa a imagem enviada por upload e retorna um ContentFile sanitizado
    pronto para ser salvo em campos models.ImageField ou models.FileField.
    """
    dados, _ = processar_imagem(arquivo, max_lado=max_lado, qualidade=qualidade, formato='JPEG')

    base_name = 'foto'
    if nome_original:
        nome_limpo = os.path.basename(nome_original)
        nome_sem_ext, _ = os.path.splitext(nome_limpo)
        # Remove caracteres problemáticos mantendo alfanuméricos e traços
        base_name = "".join(c for c in nome_sem_ext if c.isalnum() or c in ('-', '_')).strip()
        if not base_name:
            base_name = 'foto'

    nome_final = f"{base_name}.jpg"
    return ContentFile(dados, name=nome_final)
