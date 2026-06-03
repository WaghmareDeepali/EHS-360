import os
import datetime
from io import BytesIO
from collections import defaultdict
from html import escape

from django.conf import settings
from django.http import HttpResponse

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch, mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import InspectionFinding, InspectionResponse, InspectionSubmission, TemplateQuestion


class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.darkgrey)
        self.drawRightString(200 * mm, 15 * mm, f"Page {self._pageNumber} of {page_count}")


def _text(value, default='N/A'):
    if value in (None, ''):
        return default
    return escape(str(value)).replace('\n', '<br/>')


def _date(value, fmt='%d/%m/%Y'):
    return value.strftime(fmt) if value else 'N/A'


def _datetime(value, fmt='%d/%m/%Y %H:%M'):
    return value.strftime(fmt) if value else 'N/A'


def _join_queryset(queryset, attr='name', default='N/A'):
    values = [getattr(item, attr) for item in queryset if getattr(item, attr, None)]
    return ', '.join(values) if values else default


def _bullet_items(values, styles):
    items = [value for value in values if value]
    if not items:
        return [Paragraph("N/A", styles['Value'])]
    return [Paragraph(f"&#8226; {_text(item)}", styles['Value']) for item in items]


def _build_photo_flowable(photo_path, styles, max_width, max_height):
    if not photo_path or not os.path.exists(photo_path):
        return Paragraph("No evidence photo provided.", styles['Value'])

    try:
        image = Image(photo_path)
        image_width, image_height = image.imageWidth, image.imageHeight
        aspect_ratio = image_height / float(image_width)

        draw_width = max_width
        draw_height = draw_width * aspect_ratio
        if draw_height > max_height:
            draw_height = max_height
            draw_width = draw_height / aspect_ratio

        image.drawWidth = draw_width
        image.drawHeight = draw_height
        return image
    except Exception:
        return Paragraph(f"Error loading image:<br/>{escape(os.path.basename(photo_path))}", styles['Value'])


def generate_inspection_pdf(schedule):
    buffer = BytesIO()

    header_height = 1.6 * inch
    left_margin = 15 * mm
    right_margin = 15 * mm

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=right_margin,
        leftMargin=left_margin,
        topMargin=header_height + 22 * mm,
        bottomMargin=25 * mm
    )

    story = []
    drawable_width = A4[0] - left_margin - right_margin

    try:
        font_path = os.path.join(settings.BASE_DIR, 'static', 'fonts', 'DejaVuSans.ttf')
        pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))
    except Exception:
        pass

    primary_text_color = colors.HexColor('#212529')
    secondary_text_color = colors.HexColor('#495057')
    header_bg_color = colors.HexColor('#F8F9FA')
    border_color = colors.HexColor('#DEE2E6')

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='HeaderTitle', fontSize=10, fontName='Helvetica-Bold', alignment=TA_CENTER, textColor=primary_text_color))
    styles.add(ParagraphStyle(name='HeaderInfo', fontSize=9, fontName='Helvetica', alignment=TA_LEFT, textColor=secondary_text_color, leading=12))
    styles.add(ParagraphStyle(name='ReportTitle', fontSize=11, fontName='Helvetica-Bold', alignment=TA_LEFT, textColor=primary_text_color, spaceBefore=6))
    styles.add(ParagraphStyle(name='SectionHeader', fontSize=10, fontName='Helvetica-Bold', textColor=primary_text_color, spaceBefore=10, spaceAfter=4, alignment=TA_LEFT))
    styles.add(ParagraphStyle(name='Label', fontSize=9, fontName='Helvetica-Bold', textColor=primary_text_color, alignment=TA_LEFT))
    styles.add(ParagraphStyle(name='Value', fontSize=9, fontName='Helvetica', textColor=secondary_text_color, alignment=TA_LEFT, leading=12))
    styles.add(ParagraphStyle(name='FooterText', fontSize=8, fontName='Helvetica', textColor=colors.darkgrey, alignment=TA_CENTER))

    logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'logo.jpg')
    logo_img = Image(logo_path, width=2.2 * inch, height=header_height) if os.path.exists(logo_path) else Paragraph("<b>COMPANY LOGO</b>", styles['HeaderTitle'])

    header_data = [
        [logo_img, Paragraph("<b>INSPECTION MANAGEMENT SYSTEM</b>", styles['HeaderTitle']), Paragraph("DOC NO: EIL/IRI/EHS/F-03", styles['HeaderInfo'])],
        ['', Paragraph("<b>INSPECTION REPORT</b>", styles['HeaderTitle']), Paragraph("REV NO: 00 &<br/>DATE: 01-09-2021", styles['HeaderInfo'])],
    ]
    header_table = Table(
        header_data,
        colWidths=[drawable_width * 0.2875, drawable_width * 0.4875, drawable_width * 0.225],
        rowHeights=[0.8 * inch, 0.8 * inch]
    )
    header_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, border_color),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('SPAN', (0, 0), (0, 1)),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))

    def draw_header(canvas_obj, doc_obj):
        canvas_obj.saveState()
        _, height = header_table.wrap(doc_obj.width, doc_obj.topMargin)
        header_table.drawOn(canvas_obj, doc_obj.leftMargin, doc_obj.height + doc_obj.topMargin - height + 5 * mm)
        canvas_obj.restoreState()

    story.append(Spacer(1, 4 * mm))
    ref_number_data = [
        [Paragraph("<b>Inspection Report</b>", styles['ReportTitle']), Paragraph(f"<b>Reference number:</b><br/>{_text(schedule.schedule_code)}", styles['HeaderInfo'])]
    ]
    ref_number_table = Table(ref_number_data, colWidths=[drawable_width * 0.7, drawable_width * 0.3])
    ref_number_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, border_color),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    story.append(ref_number_table)

    story.append(Paragraph("<b>SECTION 1: SCHEDULE & ASSIGNMENT DETAILS</b>", styles['SectionHeader']))

    schedule_rows = [
        [Paragraph("<b>Schedule Code:</b>", styles['Label']), Paragraph(_text(schedule.schedule_code), styles['Value']), Paragraph("<b>Template:</b>", styles['Label']), Paragraph(_text(schedule.template.template_name), styles['Value'])],
        [Paragraph("<b>Inspection Type:</b>", styles['Label']), Paragraph(_text(schedule.template.get_inspection_type_display()), styles['Value']), Paragraph("<b>Status:</b>", styles['Label']), Paragraph(_text(schedule.get_status_display()), styles['Value'])],
        [Paragraph("<b>Assigned To:</b>", styles['Label']), Paragraph(_text(schedule.assigned_to.get_full_name() if schedule.assigned_to else ''), styles['Value']), Paragraph("<b>Assigned By:</b>", styles['Label']), Paragraph(_text(schedule.assigned_by.get_full_name() if schedule.assigned_by else 'System Auto Scheduled'), styles['Value'])],
        [Paragraph("<b>Department:</b>", styles['Label']), Paragraph(_text(schedule.department.name if schedule.department else ''), styles['Value']), Paragraph("<b>Created At:</b>", styles['Label']), Paragraph(_datetime(schedule.created_at), styles['Value'])],
        [Paragraph("<b>Scheduled Date:</b>", styles['Label']), Paragraph(_date(schedule.scheduled_date), styles['Value']), Paragraph("<b>Due Date:</b>", styles['Label']), Paragraph(_date(schedule.due_date), styles['Value'])],
        [Paragraph("<b>Scheduled End Date:</b>", styles['Label']), Paragraph(_date(schedule.scheduled_end_date), styles['Value']), Paragraph("<b>Started At:</b>", styles['Label']), Paragraph(_datetime(schedule.started_at), styles['Value'])],
        [Paragraph("<b>Closed At:</b>", styles['Label']), Paragraph(_datetime(schedule.closed_at), styles['Value']), Paragraph("<b>Reminder Sent:</b>", styles['Label']), Paragraph("Yes" if schedule.reminder_sent else "No", styles['Value'])],
        [Paragraph("<b>Reminder Sent At:</b>", styles['Label']), Paragraph(_datetime(schedule.reminder_sent_at), styles['Value']), Paragraph("<b>Last Updated:</b>", styles['Label']), Paragraph(_datetime(schedule.updated_at), styles['Value'])],
    ]
    schedule_table = Table(schedule_rows, colWidths=[drawable_width / 4] * 4)
    schedule_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, border_color),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(schedule_table)

    story.append(Paragraph("<b>SECTION 2: INSPECTION SCOPE</b>", styles['SectionHeader']))

    scope_rows = [
        [Paragraph("<b>Plants:</b>", styles['Label']), Paragraph(_join_queryset(schedule.plants.all()), styles['Value'])],
        [Paragraph("<b>Zones:</b>", styles['Label']), Paragraph(_join_queryset(schedule.zones.all()), styles['Value'])],
        [Paragraph("<b>Locations:</b>", styles['Label']), Paragraph(_join_queryset(schedule.locations.all()), styles['Value'])],
        [Paragraph("<b>Sub-Locations:</b>", styles['Label']), Paragraph(_join_queryset(schedule.sublocations.all()), styles['Value'])],
        [Paragraph("<b>Assignment Notes:</b>", styles['Label']), Paragraph(_text(schedule.assignment_notes), styles['Value'])],
    ]
    scope_table = Table(scope_rows, colWidths=[drawable_width * 0.25, drawable_width * 0.75])
    scope_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, border_color),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    story.append(scope_table)

    try:
        submission = schedule.submission
    except InspectionSubmission.DoesNotExist:
        submission = None
    if submission:
        responses = submission.responses.select_related(
            'question',
            'question__category',
            'assigned_to',
            'assigned_by',
            'converted_to_hazard'
        ).order_by('question__category__category_name', 'question__question_code')

        total_responses = responses.count()
        yes_count = responses.filter(answer='Yes').count()
        no_count = responses.filter(answer='No').count()
        na_count = responses.filter(answer='N/A').count()
        compliance_score = submission.compliance_score if submission.compliance_score is not None else 0

        story.append(Paragraph("<b>SECTION 3: SUBMISSION SUMMARY</b>", styles['SectionHeader']))
        submission_rows = [
            [Paragraph("<b>Submitted By:</b>", styles['Label']), Paragraph(_text(submission.submitted_by.get_full_name()), styles['Value']), Paragraph("<b>Submitted At:</b>", styles['Label']), Paragraph(_datetime(submission.submitted_at), styles['Value'])],
            [Paragraph("<b>Compliance Score:</b>", styles['Label']), Paragraph(f"{compliance_score:.2f}%", styles['Value']), Paragraph("<b>Total Responses:</b>", styles['Label']), Paragraph(str(total_responses), styles['Value'])],
            [Paragraph("<b>Yes Answers:</b>", styles['Label']), Paragraph(str(yes_count), styles['Value']), Paragraph("<b>No Answers:</b>", styles['Label']), Paragraph(str(no_count), styles['Value'])],
            [Paragraph("<b>N/A Answers:</b>", styles['Label']), Paragraph(str(na_count), styles['Value']), Paragraph("<b>Remarks:</b>", styles['Label']), Paragraph(_text(submission.remarks), styles['Value'])],
        ]
        submission_table = Table(submission_rows, colWidths=[drawable_width / 4] * 4)
        submission_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, border_color),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ]))
        story.append(submission_table)

        responses_by_category = defaultdict(list)
        for response in responses:
            responses_by_category[response.question.category].append(response)

        story.append(Paragraph("<b>SECTION 4: FULL INSPECTION RESPONSES</b>", styles['SectionHeader']))
        max_photo_width = drawable_width * 0.28
        max_photo_height = 2.6 * inch

        for category, category_responses in responses_by_category.items():
            story.append(Paragraph(f"<b>{_text(category.category_name)}</b>", styles['Label']))
            story.append(Spacer(1, 2 * mm))

            for response in category_responses:
                left_flowables = [
                    Paragraph(f"<b>{_text(response.question.question_code)}:</b> {_text(response.question.question_text)}", styles['Value']),
                    Spacer(1, 1 * mm),
                    Paragraph(f"<b>Answer:</b> {_text(response.answer)}", styles['Value']),
                ]

                if response.remarks:
                    left_flowables.extend([
                        Spacer(1, 1 * mm),
                        Paragraph(f"<b>Remarks:</b> {_text(response.remarks)}", styles['Value'])
                    ])

                if response.specific_location:
                    left_flowables.extend([
                        Spacer(1, 1 * mm),
                        Paragraph(f"<b>Specific Location:</b> {_text(response.specific_location)}", styles['Value'])
                    ])

                left_flowables.extend([
                    Spacer(1, 1 * mm),
                    Paragraph(f"<b>Answered At:</b> {_datetime(response.answered_at)}", styles['Value']),
                ])

                if response.assigned_to:
                    left_flowables.extend([
                        Spacer(1, 1 * mm),
                        Paragraph(f"<b>Assigned To:</b> {_text(response.assigned_to.get_full_name())}", styles['Value']),
                    ])

                if response.assigned_by:
                    left_flowables.extend([
                        Spacer(1, 1 * mm),
                        Paragraph(f"<b>Assigned By:</b> {_text(response.assigned_by.get_full_name())}", styles['Value']),
                    ])

                if response.assigned_at:
                    left_flowables.extend([
                        Spacer(1, 1 * mm),
                        Paragraph(f"<b>Assigned At:</b> {_datetime(response.assigned_at)}", styles['Value']),
                    ])

                if response.assignment_remarks:
                    left_flowables.extend([
                        Spacer(1, 1 * mm),
                        Paragraph(f"<b>Assignment Remarks:</b> {_text(response.assignment_remarks)}", styles['Value']),
                    ])

                if response.question.reference_standard:
                    left_flowables.extend([
                        Spacer(1, 1 * mm),
                        Paragraph(f"<b>Reference:</b> {_text(response.question.reference_standard)}", styles['Value']),
                    ])

                if response.question.guidance_notes:
                    left_flowables.extend([
                        Spacer(1, 1 * mm),
                        Paragraph(f"<b>Guidance:</b> {_text(response.question.guidance_notes)}", styles['Value']),
                    ])

                if response.converted_to_hazard:
                    left_flowables.extend([
                        Spacer(1, 1 * mm),
                        Paragraph(f"<b>Converted to Hazard:</b> {_text(response.converted_to_hazard.report_number)}", styles['Value']),
                    ])

                right_flowable = _build_photo_flowable(
                    response.photo.path if response.photo else None,
                    styles,
                    max_photo_width,
                    max_photo_height
                )

                response_table = Table(
                    [[left_flowables, right_flowable]],
                    colWidths=[drawable_width * 0.72, drawable_width * 0.28]
                )
                response_table.setStyle(TableStyle([
                    ('GRID', (0, 0), (-1, -1), 1, border_color),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 6),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                    ('TOPPADDING', (0, 0), (-1, -1), 5),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
                    ('BACKGROUND', (0, 0), (0, 0), header_bg_color),
                ]))
                story.append(response_table)
                story.append(Spacer(1, 3 * mm))

        findings = InspectionFinding.objects.filter(submission=submission).select_related('question', 'assigned_to').order_by('priority', 'finding_code')
        if findings.exists():
            story.append(Paragraph("<b>SECTION 5: AUTO-GENERATED FINDINGS</b>", styles['SectionHeader']))
            findings_rows = [[
                Paragraph("<b>Finding Code</b>", styles['Label']),
                Paragraph("<b>Question</b>", styles['Label']),
                Paragraph("<b>Priority</b>", styles['Label']),
                Paragraph("<b>Status</b>", styles['Label']),
                Paragraph("<b>Assigned To</b>", styles['Label']),
                Paragraph("<b>Due Date</b>", styles['Label']),
            ]]

            for finding in findings:
                findings_rows.append([
                    Paragraph(_text(finding.finding_code), styles['Value']),
                    Paragraph(f"{_text(finding.question.question_code)}<br/>{_text(finding.question.question_text)}", styles['Value']),
                    Paragraph(_text(finding.get_priority_display()), styles['Value']),
                    Paragraph(_text(finding.get_status_display()), styles['Value']),
                    Paragraph(_text(finding.assigned_to.get_full_name() if finding.assigned_to else 'N/A'), styles['Value']),
                    Paragraph(_date(finding.due_date), styles['Value']),
                ])

            findings_table = Table(
                findings_rows,
                colWidths=[drawable_width * 0.15, drawable_width * 0.35, drawable_width * 0.11, drawable_width * 0.13, drawable_width * 0.16, drawable_width * 0.10]
            )
            findings_table.setStyle(TableStyle([
                ('GRID', (0, 0), (-1, -1), 1, border_color),
                ('BACKGROUND', (0, 0), (-1, 0), header_bg_color),
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ]))
            story.append(findings_table)
    else:
        story.append(Paragraph("<b>SECTION 3: SUBMISSION SUMMARY</b>", styles['SectionHeader']))
        story.append(Paragraph("This inspection has not been submitted yet, so no response data is available.", styles['Value']))

    story.append(Spacer(1, 10 * mm))
    footer_text = f"Document generated from EHS-360 System on {datetime.datetime.now().strftime('%d-%b-%Y at %H:%M hrs')}"
    story.append(Paragraph(footer_text, styles['FooterText']))

    doc.build(story, onFirstPage=draw_header, onLaterPages=draw_header, canvasmaker=NumberedCanvas)

    pdf = buffer.getvalue()
    buffer.close()

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Inspection_Report_{schedule.schedule_code}.pdf"'
    response.write(pdf)
    return response
