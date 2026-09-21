"""
Serviço de geração de documentos PDF oficiais do LabHub.
Utiliza ReportLab para gerar relatórios detalhados e estruturados com fotos,
tabelas, metadados institucionais e campos de assinatura.
"""

import io
import os
from PIL import Image as PILImage
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    HRFlowable,
    Image as RLImage,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def _calcular_dimensoes_imagem(caminho_ou_buffer, max_w=235, max_h=165):
    """Calcula largura e altura proporcionais para imagem caber no PDF."""
    try:
        if isinstance(caminho_ou_buffer, io.BytesIO):
            caminho_ou_buffer.seek(0)
        im = PILImage.open(caminho_ou_buffer)
        w, h = im.size
        ratio = min(max_w / w, max_h / h, 1.0)
        if isinstance(caminho_ou_buffer, io.BytesIO):
            caminho_ou_buffer.seek(0)
        return w * ratio, h * ratio
    except Exception:
        return max_w, max_h


def gerar_pdf_ocorrencia(ocorrencia, usuario_solicitante):
    """
    Gera um buffer de memória com o PDF completo da ocorrência selecionada.
    Inclui cabeçalho institucional, dados do fato, detalhes da aula/agendamento,
    descrição minuciosa, tabelas de alunos e equipamentos envolvidos,
    galeria de evidências fotográficas embutidas e campos de assinatura.
    Retorna: io.BytesIO pronto para envio em HttpResponse.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=28,
        rightMargin=28,
        topMargin=28,
        bottomMargin=28,
    )

    styles = getSampleStyleSheet()

    # Estilos tipográficos profissionais
    primary_color = colors.HexColor('#1E3A8A')
    accent_color = colors.HexColor('#D97706')
    dark_text = colors.HexColor('#0F172A')
    muted_text = colors.HexColor('#64748B')
    border_color = colors.HexColor('#CBD5E1')
    bg_subtle = colors.HexColor('#F8FAFC')

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=17,
        leading=21,
        textColor=primary_color,
        spaceAfter=3,
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=accent_color,
        spaceAfter=3,
    )

    meta_style = ParagraphStyle(
        'DocMeta',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11.5,
        textColor=muted_text,
    )

    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=13.5,
        textColor=primary_color,
        spaceBefore=10,
        spaceAfter=5,
    )

    body_style = ParagraphStyle(
        'BodyTextCustom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=dark_text,
    )

    body_bold = ParagraphStyle(
        'BodyBoldCustom',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=13,
        textColor=dark_text,
    )

    desc_style = ParagraphStyle(
        'DescTextCustom',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=14.5,
        textColor=dark_text,
    )

    th_style = ParagraphStyle(
        'TableHeader',
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.white,
    )

    td_style = ParagraphStyle(
        'TableCell',
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=dark_text,
    )

    caption_style = ParagraphStyle(
        'PhotoCaption',
        fontName='Helvetica',
        fontSize=7.5,
        leading=10,
        textColor=muted_text,
        alignment=1, # Centralizado
    )

    elements = []

    dt_fato = timezone.localtime(ocorrencia.data_hora_fato) if timezone.is_aware(ocorrencia.data_hora_fato) else ocorrencia.data_hora_fato
    dt_emissao = timezone.localtime(timezone.now())

    # 1. CABEÇALHO INSTITUCIONAL
    header_data = [
        [
            Paragraph("SISTEMA DE GESTÃO DE<br/>LABORATÓRIO", title_style),
            Paragraph(f"OCORRÊNCIA <b>#{ocorrencia.id}</b>", subtitle_style),
        ],
        [
            Paragraph("Documento gerado automaticamente pelo SISTEMA DE GESTÃO DE LABORATÓRIO, Registro permanente para controle de patrimônio escolar.", meta_style),
            Paragraph(f"Emitido em: {dt_emissao:%d/%m/%Y às %H:%M}", meta_style),
        ]
    ]
    t_header = Table(header_data, colWidths=[360, 175])
    t_header.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('ALIGN', (1,0), (1,-1), 'RIGHT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 1),
        ('TOPPADDING', (0,0), (-1,-1), 0),
    ]))
    elements.append(t_header)
    elements.append(Spacer(1, 4))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=primary_color, spaceBefore=4, spaceAfter=8))

    # 2. DADOS PRINCIPAIS DO FATO E PROFESSOR
    elements.append(Paragraph("1. DADOS GERAIS DO FATO", section_heading))
    prof_nome = ocorrencia.professor.get_full_name() or ocorrencia.professor.username

    info_fato_data = [
        [
            Paragraph("<b>Data e Horário do Fato:</b>", body_style),
            Paragraph(f"{dt_fato:%d/%m/%Y às %H:%M}", body_bold),
            Paragraph("<b>Professor Responsável:</b>", body_style),
            Paragraph(prof_nome, body_bold),
        ],
    ]
    t_info_fato = Table(info_fato_data, colWidths=[130, 140, 130, 135])
    t_info_fato.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), bg_subtle),
        ('BOX', (0,0), (-1,-1), 0.5, border_color),
        ('INNERGRID', (0,0), (-1,-1), 0.5, border_color),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('LEFTPADDING', (0,0), (-1,-1), 6),
        ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    elements.append(t_info_fato)

    # 3. VÍNCULO COM AULA / AGENDAMENTO (se existir)
    if ocorrencia.agendamento:
        ag = ocorrencia.agendamento
        elements.append(Paragraph("2. CONTEXTO DA AULA / AGENDAMENTO", section_heading))
        local_str = ag.sala.nome if (ag.tipo == 'SALA' and ag.sala) else "Sala de Aula"
        horarios_aulas = {
            1: '07:00 - 07:50',
            2: '07:50 - 08:40',
            3: '08:40 - 09:30',
            4: '09:45 - 10:35',
            5: '10:35 - 11:25',
            6: '11:25 - 12:15',
            7: '13:25 - 14:15',
            8: '14:15 - 15:05',
            9: '15:05 - 15:55',
        }
        horario = horarios_aulas.get(ag.aula, '')
        aula_rotulo = f"{ag.aula}ª Aula" + (f" ({horario})" if horario else "")

        aula_info_data = [
            [
                Paragraph("<b>Data da Aula:</b>", body_style),
                Paragraph(f"{ag.data:%d/%m/%Y}", body_bold),
                Paragraph("<b>Aula / Horário:</b>", body_style),
                Paragraph(aula_rotulo, body_bold),
            ],
            [
                Paragraph("<b>Turma:</b>", body_style),
                Paragraph(f"{ag.turma.nome} ({ag.turma.get_turno_display()})", body_style),
                Paragraph("<b>Local da Atividade:</b>", body_style),
                Paragraph(local_str, body_style),
            ]
        ]
        t_aula = Table(aula_info_data, colWidths=[130, 140, 130, 135])
        t_aula.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), bg_subtle),
            ('BOX', (0,0), (-1,-1), 0.5, border_color),
            ('INNERGRID', (0,0), (-1,-1), 0.5, border_color),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        elements.append(t_aula)

    # 4. DESCRIÇÃO DOS FATOS E DANOS
    elements.append(Paragraph("3. DESCRIÇÃO DO FATO / DANOS OBSERVADOS", section_heading))
    t_desc = Table([[Paragraph(ocorrencia.descricao.replace('\n', '<br/>'), desc_style)]], colWidths=[535])
    t_desc.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#FFFBEB')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#F59E0B')),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('LEFTPADDING', (0,0), (-1,-1), 10),
        ('RIGHTPADDING', (0,0), (-1,-1), 10),
    ]))
    elements.append(t_desc)

    # 5. ALUNOS ENVOLVIDOS
    num_alunos = ocorrencia.alunos.count()
    elements.append(Paragraph(f"4. ALUNOS ENVOLVIDOS ({num_alunos})", section_heading))
    if num_alunos > 0:
        # Mapeia equipamentos atribuídos na relação da aula, se houver
        atribuicoes = {}
        if ocorrencia.agendamento and ocorrencia.agendamento.relacao:
            for item in ocorrencia.agendamento.relacao.itens.all():
                if item.equipamento:
                    atribuicoes[item.aluno_id] = item.equipamento

        alunos_rows = [
            [
                Paragraph("Nome do Aluno", th_style),
                Paragraph("RA / Registro Escolar", th_style),
                Paragraph("Equipamento na Aula", th_style),
            ]
        ]
        for al in ocorrencia.alunos.all().order_by('nome'):
            eq_atribuido = atribuicoes.get(al.id, "—")
            alunos_rows.append([
                Paragraph(al.nome, td_style),
                Paragraph(al.ra_formatado, td_style),
                Paragraph(eq_atribuido, td_style),
            ])

        t_alunos = Table(alunos_rows, colWidths=[260, 140, 135])
        t_alunos.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), primary_color),
            ('BOX', (0,0), (-1,-1), 0.5, border_color),
            ('INNERGRID', (0,0), (-1,-1), 0.5, border_color),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ]))
        elements.append(t_alunos)
    else:
        elements.append(Paragraph("<i>Nenhum aluno específico registrado nesta ocorrência.</i>", meta_style))

    # 6. EQUIPAMENTOS ENVOLVIDOS
    num_equips = ocorrencia.equipamentos.count()
    elements.append(Paragraph(f"5. EQUIPAMENTOS AFETADOS / ENVOLVIDOS ({num_equips})", section_heading))
    if num_equips > 0:
        equips_rows = [
            [
                Paragraph("Apelido", th_style),
                Paragraph("Categoria", th_style),
                Paragraph("Modelo", th_style),
                Paragraph("Nº Patrimônio / Série", th_style),
                Paragraph("Status Atual", th_style),
            ]
        ]
        for eq in ocorrencia.equipamentos.all().order_by('categoria', 'apelido'):
            pat_serie = eq.numero_patrimonio or eq.numero_serie or "—"
            equips_rows.append([
                Paragraph(f"<b>{eq.apelido}</b>", td_style),
                Paragraph(eq.get_categoria_display(), td_style),
                Paragraph(eq.modelo or "—", td_style),
                Paragraph(pat_serie, td_style),
                Paragraph(eq.get_status_display(), td_style),
            ])

        t_equips = Table(equips_rows, colWidths=[80, 110, 130, 125, 90])
        t_equips.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), primary_color),
            ('BOX', (0,0), (-1,-1), 0.5, border_color),
            ('INNERGRID', (0,0), (-1,-1), 0.5, border_color),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
        ]))
        elements.append(t_equips)
    else:
        elements.append(Paragraph("<i>Nenhum equipamento listado diretamente nesta ocorrência.</i>", meta_style))

    # 7. EVIDÊNCIAS FOTOGRÁFICAS (Fotos embutidas no documento)
    fotos = list(ocorrencia.fotos.all())
    elements.append(Paragraph(f"6. EVIDÊNCIAS FOTOGRÁFICAS ({len(fotos)})", section_heading))
    if fotos:
        foto_celulas = []
        for idx, f in enumerate(fotos, start=1):
            try:
                img_source = None
                if f.foto:
                    try:
                        # Tenta via caminho físico direto
                        if os.path.exists(f.foto.path):
                            img_source = f.foto.path
                    except Exception:
                        pass

                    if not img_source:
                        # Tenta leitura direta do Storage
                        f.foto.seek(0)
                        buf_img = io.BytesIO(f.foto.read())
                        buf_img.seek(0)
                        img_source = buf_img

                if img_source:
                    w, h = _calcular_dimensoes_imagem(img_source, max_w=240, max_h=160)
                    rl_img = RLImage(img_source, width=w, height=h)
                    sub_t = Table([
                        [rl_img],
                        [Paragraph(f"<b>Evidência #{idx}</b> — {f.criado_em:%d/%m/%Y %H:%M}", caption_style)]
                    ], colWidths=[255])
                    sub_t.setStyle(TableStyle([
                        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                        ('TOPPADDING', (0,0), (-1,-1), 3),
                        ('BOTTOMPADDING', (0,0), (-1,-1), 3),
                        ('BOX', (0,0), (-1,-1), 0.5, border_color),
                        ('BACKGROUND', (0,0), (-1,-1), bg_subtle),
                    ]))
                    foto_celulas.append(sub_t)
            except Exception:
                continue

        # Organiza as fotos em grade de 2 colunas
        grade_fotos = []
        for i in range(0, len(foto_celulas), 2):
            linha = [foto_celulas[i]]
            if i + 1 < len(foto_celulas):
                linha.append(foto_celulas[i + 1])
            else:
                linha.append("") # Célula vazia para alinhar
            grade_fotos.append(linha)

        if grade_fotos:
            t_grade = Table(grade_fotos, colWidths=[265, 265])
            t_grade.setStyle(TableStyle([
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('BOTTOMPADDING', (0,0), (-1,-1), 8),
                ('LEFTPADDING', (0,0), (-1,-1), 0),
                ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ]))
            elements.append(t_grade)
    else:
        elements.append(Paragraph("<i>Nenhuma foto ou imagem anexada a esta ocorrência.</i>", meta_style))

    # 8. TERMO DE CIÊNCIA E ASSINATURA
    elements.append(Spacer(1, 15))
    assinaturas_data = [
        [
            Paragraph("____________________________________________________<br/><b>Coordenação</b>", ParagraphStyle('AssCoord', parent=styles['Normal'], alignment=1, fontSize=9, leading=14)),
        ]
    ]
    t_ass = Table(assinaturas_data, colWidths=[530])
    t_ass.setStyle(TableStyle([
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
        ('TOPPADDING', (0,0), (-1,-1), 12),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    elements.append(KeepTogether([
        HRFlowable(width="100%", thickness=0.5, color=border_color, spaceBefore=10, spaceAfter=14),
        t_ass,
        Spacer(1, 10),
        Paragraph("Documento gerado automaticamente pelo SISTEMA DE GESTÃO DE LABORATÓRIO, Registro permanente para controle de patrimônio escolar.", ParagraphStyle('Foot', parent=styles['Normal'], alignment=1, fontSize=7.5, leading=10, textColor=muted_text)),
    ]))

    doc.build(elements)
    buffer.seek(0)
    return buffer
