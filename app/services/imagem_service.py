"""
Serviço centralizado de processamento e sanitização de imagens do LabHub.
Evita corrupção de imagens, trata orientação EXIF de fotos de celulares,
gerencia canais de transparência e redimensiona com alta nitidez.
"""

import io
import os
from PIL import Image, ImageFile, ImageOps
from django.core.files.base import ContentFile

# Permite leitura resiliente de JPEGs progressivos ou com pequenos truncamentos de streaming
ImageFile.LOAD_TRUNCATED_IMAGES = True


def processar_imagem(arquivo, max_lado=1920, qualidade=85, formato='JPEG'):
    """
    Abre, corrige rotação EXIF, ajusta transparência e comprime a imagem.
    Lê o stream para um buffer em memória isolado e executa img.load() imediatamente
    para impedir perda ou corrupção de dados por ponteiro consumido.
    Retorna: (bytes_da_imagem, mime_type)
    """
    if hasattr(arquivo, 'seek'):
        try:
            arquivo.seek(0)
        except Exception:
            pass

    if hasattr(arquivo, 'read'):
        conteudo = arquivo.read()
    elif isinstance(arquivo, (bytes, bytearray)):
        conteudo = bytes(arquivo)
    else:
        conteudo = b''

    # Restaura o ponteiro original caso o chamador ainda precise do arquivo
    if hasattr(arquivo, 'seek'):
        try:
            arquivo.seek(0)
        except Exception:
            pass

    if not conteudo:
        raise ValueError("Arquivo de imagem vazio ou inacessível.")

    try:
        stream = io.BytesIO(conteudo)
        img = Image.open(stream)
        img.load()  # Força leitura e decodificação imediata de todos os blocos de pixels
    except Exception as e:
        raise ValueError(f"Não foi possível abrir o arquivo como imagem válida: {e}")

    # Corrige orientação de câmeras de smartphones baseada nos metadados EXIF
    try:
        img = ImageOps.exif_transpose(img)
    except Exception:
        pass

    # Trata transparência (RGBA, LA, P) preenchendo com fundo branco para JPEG
    if formato.upper() in ('JPEG', 'JPG'):
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in getattr(img, 'info', {})):
            img_rgba = img.convert('RGBA')
            bg = Image.new('RGB', img_rgba.size, (255, 255, 255))
            bg.paste(img_rgba, mask=img_rgba.split()[-1])
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

    return dados, mime


def processar_foto_para_storage(arquivo, nome_original='', max_lado=1920, qualidade=85):
    """
    Processa a imagem enviada por upload e retorna um ContentFile sanitizado
    pronto para ser salvo em campos models.ImageField ou models.FileField.
    """
    # Auto-detecta nome original caso não tenha sido explicitamente passado
    if not nome_original and hasattr(arquivo, 'name') and arquivo.name:
        nome_original = arquivo.name

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
