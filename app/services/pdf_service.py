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
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def _calcular_dimensoes_imagem(caminho_ou_buffer, max_w=515, max_h=350):
    """Calcula largura e altura proporcionais para imagem caber em tamanho grande no PDF."""
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

    # 7. EVIDÊNCIAS FOTOGRÁFICAS (Fotos embutidas em tamanho grande)
    fotos = list(ocorrencia.fotos.all())
    elements.append(Paragraph(f"6. EVIDÊNCIAS FOTOGRÁFICAS ({len(fotos)})", section_heading))
    if fotos:
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
                    w, h = _calcular_dimensoes_imagem(img_source, max_w=515, max_h=350)
                    rl_img = RLImage(img_source, width=w, height=h)
                    dt_foto = timezone.localtime(f.criado_em) if timezone.is_aware(f.criado_em) else f.criado_em
                    sub_t = Table([
                        [rl_img],
                        [Paragraph(f"<b>Evidência #{idx}</b> — Registrada em {dt_foto:%d/%m/%Y às %H:%M}", caption_style)]
                    ], colWidths=[530])
                    sub_t.setStyle(TableStyle([
                        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
                        ('TOPPADDING', (0,0), (-1,-1), 8),
                        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
                        ('BOX', (0,0), (-1,-1), 0.5, border_color),
                        ('BACKGROUND', (0,0), (-1,-1), bg_subtle),
                    ]))
                    elements.append(KeepTogether([sub_t, Spacer(1, 14)]))
            except Exception:
                continue
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


def gerar_pdf_relacoes(agendamentos_qs, usuario):
    """
    Gera um buffer de memória com o PDF completo da relação inteira de alunos e equipamentos.
    Cada relação possui:
    - Cabeçalho institucional do SISTEMA DE GESTÃO DE LABORATÓRIO;
    - Bloco de informações da aula (data, turma, aula/horário, professor, espaço/dispositivos, status);
    - Tabela completa de todos os alunos da turma (#, Nome, RA, Aparelho Atribuído, Assinatura/Visto);
    - Faixa de resumo de totais (alunos, atribuídos, pendentes);
    - Bloco com campos de assinatura do Professor Responsável e Coordenação;
    - Quebra de página automática entre múltiplas relações distintas.
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

    primary_color = colors.HexColor('#1E3A8A')
    accent_color = colors.HexColor('#D97706')
    dark_text = colors.HexColor('#0F172A')
    muted_text = colors.HexColor('#64748B')
    border_color = colors.HexColor('#CBD5E1')
    bg_subtle = colors.HexColor('#F8FAFC')
    header_row_bg = colors.HexColor('#1E3A8A')

    title_style = ParagraphStyle(
        'RelDocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=15,
        leading=18,
        textColor=primary_color,
        spaceAfter=2,
    )

    badge_rel_style = ParagraphStyle(
        'RelDocBadge',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=accent_color,
        alignment=2,  # Direita
    )

    meta_style = ParagraphStyle(
        'RelDocMeta',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=muted_text,
    )

    meta_right_style = ParagraphStyle(
        'RelDocMetaRight',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=muted_text,
        alignment=2,  # Direita
    )

    section_heading = ParagraphStyle(
        'RelSectionHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=9.5,
        leading=12.5,
        textColor=primary_color,
        spaceBefore=8,
        spaceAfter=4,
    )

    body_style = ParagraphStyle(
        'RelBodyText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=dark_text,
    )

    body_bold = ParagraphStyle(
        'RelBodyBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=12,
        textColor=dark_text,
    )

    th_style = ParagraphStyle(
        'RelThStyle',
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10.5,
        textColor=colors.white,
    )

    th_center = ParagraphStyle(
        'RelThCenter',
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10.5,
        textColor=colors.white,
        alignment=1,
    )

    td_style = ParagraphStyle(
        'RelTdStyle',
        fontName='Helvetica',
        fontSize=8,
        leading=10.5,
        textColor=dark_text,
    )

    td_bold = ParagraphStyle(
        'RelTdBold',
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10.5,
        textColor=dark_text,
    )

    td_center = ParagraphStyle(
        'RelTdCenter',
        fontName='Helvetica',
        fontSize=8,
        leading=10.5,
        textColor=dark_text,
        alignment=1,
    )

    td_primary = ParagraphStyle(
        'RelTdPrimary',
        fontName='Helvetica-Bold',
        fontSize=8,
        leading=10.5,
        textColor=primary_color,
    )

    sig_style = ParagraphStyle(
        'RelSigStyle',
        parent=styles['Normal'],
        alignment=1,
        fontSize=8.5,
        leading=12,
        textColor=dark_text,
    )

    horarios_aulas = {
        1: ('07:00', '07:50'),
        2: ('07:50', '08:40'),
        3: ('08:40', '09:30'),
        4: ('09:45', '10:35'),
        5: ('10:35', '11:25'),
        6: ('11:25', '12:15'),
        7: ('13:25', '14:15'),
        8: ('14:15', '15:05'),
        9: ('15:05', '15:55'),
    }

    # Agrupa agendamentos por relação (ex.: aulas consecutivas vinculadas à mesma relação)
    grupos = []
    relacoes_vistas = set()
    ags_avulsos_vistos = set()

    for ag in agendamentos_qs:
        if ag.relacao_id:
            if ag.relacao_id in relacoes_vistas:
                continue
            relacoes_vistas.add(ag.relacao_id)
            ags_rel = list(ag.relacao.agendamentos.select_related('sala', 'turma', 'professor').prefetch_related('itens').order_by('aula'))
            if not ags_rel:
                ags_rel = [ag]
            grupos.append({
                'rel': ag.relacao,
                'ag_principal': ags_rel[0],
                'agendamentos': ags_rel,
            })
        else:
            if ag.id in ags_avulsos_vistos:
                continue
            ags_avulsos_vistos.add(ag.id)
            grupos.append({
                'rel': None,
                'ag_principal': ag,
                'agendamentos': [ag],
            })

    elements = []
    dt_emissao = timezone.localtime(timezone.now())

    for idx_grupo, grupo in enumerate(grupos):
        if idx_grupo > 0:
            elements.append(PageBreak())

        rel = grupo['rel']
        ag_princ = grupo['ag_principal']
        ags = grupo['agendamentos']
        turma = ag_princ.turma
        prof = ag_princ.professor
        data_aula = ag_princ.data

        # Formatação de horários e aulas
        if rel and hasattr(rel, 'aulas_formatadas'):
            aulas_rotulo = rel.aulas_formatadas()
        else:
            aulas_nums = [a.aula for a in ags]
            if len(aulas_nums) == 1:
                aulas_rotulo = f"{aulas_nums[0]}ª Aula"
            elif len(aulas_nums) == 2:
                aulas_rotulo = f"{aulas_nums[0]}ª e {aulas_nums[1]}ª Aula"
            else:
                aulas_rotulo = f"{', '.join(str(n) for n in aulas_nums[:-1])} e {aulas_nums[-1]}ª Aula"

        if ags:
            ini_h = horarios_aulas.get(ags[0].aula, ('', ''))[0]
            fim_h = horarios_aulas.get(ags[-1].aula, ('', ''))[1]
            if ini_h and fim_h:
                horario_completo = f"{aulas_rotulo} ({ini_h} às {fim_h})"
            else:
                horario_completo = aulas_rotulo
        else:
            horario_completo = aulas_rotulo

        # Espaços e equipamentos solicitados
        espacos_list = []
        for a in ags:
            if a.tipo == 'SALA' and a.sala:
                if a.sala.nome not in espacos_list:
                    espacos_list.append(a.sala.nome)
            elif a.tipo == 'DISPOSITIVO':
                itens_disp = [f"{it.get_categoria_display()} ({it.quantidade})" for it in a.itens.all()]
                if itens_disp:
                    desc = "Dispositivos Móveis (" + ", ".join(itens_disp) + ")"
                else:
                    desc = "Dispositivos Móveis (Sala de Aula)"
                if desc not in espacos_list:
                    espacos_list.append(desc)
        espaco_str = ", ".join(espacos_list) if espacos_list else "Sala de Aula"

        # Status da relação
        if rel and rel.esta_preenchida:
            if rel.preenchido_em:
                dt_p = timezone.localtime(rel.preenchido_em) if timezone.is_aware(rel.preenchido_em) else rel.preenchido_em
                status_str = f"✓ Preenchida em {dt_p:%d/%m/%Y às %H:%M}"
            else:
                status_str = "✓ Preenchida"
        else:
            status_str = "⏳ Pendente de Preenchimento"

        prof_nome = prof.get_full_name() or prof.username if prof else "Professor(a) Responsável"
        turma_str = f"{turma.nome} ({turma.get_turno_display()})" if turma else "Turma não informada"

        # 1. Cabeçalho Institucional
        header_data = [
            [
                Paragraph("<b>SISTEMA DE GESTÃO DE LABORATÓRIO</b>", title_style),
                Paragraph("<b>RELAÇÃO DE ALUNOS E EQUIPAMENTOS</b>", badge_rel_style),
            ],
            [
                Paragraph("Documento gerado automaticamente pelo SISTEMA DE GESTÃO DE LABORATÓRIO, Registro permanente para controle de patrimônio escolar.", meta_style),
                Paragraph(f"Emitido em: {dt_emissao:%d/%m/%Y às %H:%M}", meta_right_style),
            ],
        ]
        t_header = Table(header_data, colWidths=[360, 179])
        t_header.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('BOTTOMPADDING', (0,0), (-1,-1), 1),
            ('TOPPADDING', (0,0), (-1,-1), 0),
        ]))
        elements.append(t_header)
        elements.append(HRFlowable(width="100%", thickness=1.5, color=primary_color, spaceBefore=4, spaceAfter=6))

        # 2. Informações Gerais do Agendamento / Relação
        info_data = [
            [
                Paragraph("<b>Data da Aula:</b>", body_style),
                Paragraph(f"{data_aula:%d/%m/%Y}", body_bold),
                Paragraph("<b>Aula / Horário:</b>", body_style),
                Paragraph(horario_completo, body_bold),
            ],
            [
                Paragraph("<b>Turma:</b>", body_style),
                Paragraph(turma_str, body_bold),
                Paragraph("<b>Professor(a):</b>", body_style),
                Paragraph(prof_nome, body_bold),
            ],
            [
                Paragraph("<b>Espaço / Equip.:</b>", body_style),
                Paragraph(espaco_str, body_style),
                Paragraph("<b>Status da Relação:</b>", body_style),
                Paragraph(status_str, body_style),
            ],
        ]
        if ag_princ.observacao and ag_princ.observacao.strip():
            info_data.append([
                Paragraph("<b>Observações:</b>", body_style),
                Paragraph(ag_princ.observacao.strip(), body_style),
                Paragraph("", body_style),
                Paragraph("", body_style),
            ])

        t_info = Table(info_data, colWidths=[105, 165, 105, 164])
        t_info_style = [
            ('BACKGROUND', (0,0), (-1,-1), bg_subtle),
            ('BOX', (0,0), (-1,-1), 0.5, border_color),
            ('INNERGRID', (0,0), (-1,-1), 0.5, border_color),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]
        if ag_princ.observacao and ag_princ.observacao.strip():
            t_info_style.append(('SPAN', (1, 3), (3, 3)))
        t_info.setStyle(TableStyle(t_info_style))
        elements.append(t_info)

        # 3. Tabela de Alunos e Equipamentos Atribuídos
        elements.append(Paragraph("RELAÇÃO DE ALUNOS E EQUIPAMENTOS ATRIBUÍDOS", section_heading))

        alunos_list = list(turma.alunos.all().order_by('nome')) if turma else []
        if rel:
            itens_map = {item.aluno_id: item.equipamento for item in rel.itens.all() if item.equipamento and item.equipamento.strip()}
        else:
            itens_rel = list(ag_princ.relacoes.all())
            itens_map = {item.aluno_id: item.equipamento for item in itens_rel if item.equipamento and item.equipamento.strip()}

        col_widths = [28, 215, 80, 116, 100]
        table_rows = [
            [
                Paragraph("<b>#</b>", th_center),
                Paragraph("<b>Nome do Aluno</b>", th_style),
                Paragraph("<b>RA</b>", th_center),
                Paragraph("<b>Aparelho / Patrimônio</b>", th_style),
                Paragraph("<b>Assinatura / Visto</b>", th_center),
            ]
        ]

        if alunos_list:
            for idx, aluno in enumerate(alunos_list, 1):
                equip = itens_map.get(aluno.id, '')
                if equip:
                    equip_cell = Paragraph(f"<b>{equip}</b>", td_primary)
                else:
                    equip_cell = Paragraph('<font color="#94A3B8"><i>Sem aparelho</i></font>', td_style)

                ra_fmt = aluno.ra_formatado if hasattr(aluno, 'ra_formatado') else aluno.ra
                visto_cell = Paragraph('<font color="#CBD5E1">___________________</font>', td_center)

                table_rows.append([
                    Paragraph(str(idx), td_center),
                    Paragraph(aluno.nome, td_bold),
                    Paragraph(ra_fmt or '—', td_center),
                    equip_cell,
                    visto_cell,
                ])
        else:
            table_rows.append([
                Paragraph("—", td_center),
                Paragraph("<i>Nenhum aluno cadastrado nesta turma.</i>", td_style),
                Paragraph("—", td_center),
                Paragraph("—", td_style),
                Paragraph("—", td_center),
            ])

        t_alunos = Table(table_rows, colWidths=col_widths, repeatRows=1)
        t_alunos_style = [
            ('BACKGROUND', (0,0), (-1,0), header_row_bg),
            ('BOX', (0,0), (-1,-1), 0.5, border_color),
            ('INNERGRID', (0,0), (-1,-1), 0.5, border_color),
            ('TOPPADDING', (0,0), (-1,-1), 3),
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
            ('LEFTPADDING', (0,0), (-1,-1), 4),
            ('RIGHTPADDING', (0,0), (-1,-1), 4),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]
        for r_idx in range(1, len(table_rows)):
            bg_color = bg_subtle if r_idx % 2 == 1 else colors.white
            t_alunos_style.append(('BACKGROUND', (0, r_idx), (-1, r_idx), bg_color))

        t_alunos.setStyle(TableStyle(t_alunos_style))
        elements.append(t_alunos)
        elements.append(Spacer(1, 6))

        # 4. Resumo de Totais
        total_alunos = len(alunos_list)
        total_com_aparelho = sum(1 for a in alunos_list if a.id in itens_map)
        total_sem_aparelho = total_alunos - total_com_aparelho

        resumo_p = Paragraph(
            f"<b>Total de Alunos:</b> {total_alunos}&nbsp;&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;&nbsp;"
            f"<b>Aparelhos Atribuídos:</b> {total_com_aparelho}&nbsp;&nbsp;&nbsp;&nbsp;|&nbsp;&nbsp;&nbsp;&nbsp;"
            f"<b>Alunos sem Aparelho:</b> {total_sem_aparelho}",
            ParagraphStyle('RelResumo', parent=styles['Normal'], fontSize=8.5, leading=11, textColor=dark_text, alignment=1)
        )
        t_resumo = Table([[resumo_p]], colWidths=[539])
        t_resumo.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,-1), bg_subtle),
            ('BOX', (0,0), (-1,-1), 0.5, border_color),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ]))
        elements.append(t_resumo)

        # 5. Assinaturas (Protegido por KeepTogether para não quebrar no fim da página)
        sig_data = [
            [
                Paragraph(f"____________________________________________<br/><b>Professor(a) Responsável</b><br/><font size=7.5 color='#64748B'>{prof_nome}</font>", sig_style),
                Paragraph("____________________________________________<br/><b>Coordenação</b><br/><font size=7.5 color='#64748B'>Responsável pelo Laboratório</font>", sig_style),
            ]
        ]
        t_sig = Table(sig_data, colWidths=[269, 270])
        t_sig.setStyle(TableStyle([
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'BOTTOM'),
            ('TOPPADDING', (0,0), (-1,-1), 16),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))

        elements.append(KeepTogether([
            Spacer(1, 10),
            t_sig,
        ]))

    def _adicionar_rodape_relacao(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor('#94A3B8'))
        canvas.drawString(28, 15, 'LabHub — Sistema de Gestão de Laboratório')
        canvas.drawRightString(567, 15, f'Página {canvas.getPageNumber()}')
        canvas.restoreState()

    doc.build(elements, onFirstPage=_adicionar_rodape_relacao, onLaterPages=_adicionar_rodape_relacao)
    buffer.seek(0)
    return buffer
