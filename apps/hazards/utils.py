import os
from io import BytesIO
from django.http import HttpResponse
from django.conf import settings
import datetime

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm, inch
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak, KeepTogether
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# =============================================================================
# 1. HELPER CLASS FOR PAGE NUMBERING
# Custom Canvas to add 'Page X of Y' numbering.
# =============================================================================
class NumberedCanvas(canvas.Canvas):
    """
    Custom Canvas to add 'Page X of Y' numbering to each page.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        # Save the state of the current page before starting a new one.
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        # The save method is called after all content is drawn.
        # It iterates through the saved page states to draw the page number on each page.
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        # Draw the "Page X of Y" string at the bottom right of the page.
        self.setFont("Helvetica", 9)
        self.setFillColor(colors.darkgrey)
        self.drawRightString(200 * mm, 15 * mm, f"Page {self._pageNumber} of {page_count}")

# =============================================================================
# 2. MAIN PDF GENERATION FUNCTION
# This function orchestrates the creation of the comprehensive Hazard Report PDF,
# styled similarly to the incident report for consistency.
# =============================================================================
def generate_hazard_pdf(hazard):
    """
    Generates a comprehensive, professional PDF report for a given Hazard object,
    including all related details, action items, and photos, with styling
    consistent with the incident report format.
    
    Args:
        hazard (Hazard): The Hazard model instance to generate the report for.
        
    Returns:
        HttpResponse: A response object containing the generated PDF file.
    """
    # Create a buffer to hold the PDF data in memory.
    buffer = BytesIO()
    
    # Define page layout and margins.
    header_height = 1.6 * inch
    left_margin = 15*mm
    right_margin = 15*mm
    
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=right_margin,
        leftMargin=left_margin,
        topMargin=header_height + 22*mm, # Make space for the header
        bottomMargin=25*mm
    )

    # The 'story' is a list of ReportLab Flowables that will be drawn on the document.
    story = []
    
    # Calculate the drawable width for full-width tables.
    drawable_width = A4[0] - left_margin - right_margin

    # --- Style Definitions (consistent with incident report) ---
    try:
        font_path = os.path.join(settings.BASE_DIR, 'static', 'fonts', 'DejaVuSans.ttf')
        pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))
    except Exception:
        pass # Fallback to default fonts if not found

    primary_text_color = colors.HexColor('#212529')
    secondary_text_color = colors.HexColor('#495057')
    header_bg_color = colors.HexColor('#F8F9FA')
    border_color = colors.HexColor('#DEE2E6')

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name='HeaderTitle', fontSize=10, fontName='Helvetica-Bold', alignment=TA_CENTER, textColor=primary_text_color))
    styles.add(ParagraphStyle(name='HeaderInfo', fontSize=9, fontName='Helvetica', alignment=TA_LEFT, textColor=secondary_text_color, leading=12))
    styles.add(ParagraphStyle(name='ReportTitle', fontSize=11, fontName='Helvetica-Bold', alignment=TA_LEFT, textColor=primary_text_color, spaceBefore=6))
    styles.add(ParagraphStyle(name='SectionHeader', fontSize=10, fontName='Helvetica-Bold', textColor=primary_text_color, spaceBefore=8, spaceAfter=4, alignment=TA_LEFT, backColor=header_bg_color, borderPadding=(6, 4)))
    styles.add(ParagraphStyle(name='Label', fontSize=9, fontName='Helvetica-Bold', textColor=primary_text_color, alignment=TA_LEFT))
    styles.add(ParagraphStyle(name='Value', fontSize=9, fontName='Helvetica', textColor=secondary_text_color, alignment=TA_LEFT, leading=12))
    styles.add(ParagraphStyle(name='FooterText', fontSize=8, fontName='Helvetica', textColor=colors.darkgrey, alignment=TA_CENTER))

    # --- Header Definition (consistent with incident report) ---
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'logo.jpg')
    logo_img = Image(logo_path, width=2.2*inch, height=header_height) if os.path.exists(logo_path) else Paragraph("<b>Your Company</b>", styles['HeaderTitle'])

    header_data = [
        [logo_img, Paragraph("<b>INTEGRATED MANAGEMENT SYSTEM [EHS]</b>", styles['HeaderTitle']), Paragraph(f"DOC NO: EHS/HAZ/F-01", styles['HeaderInfo'])],
        ['', Paragraph("<b>HAZARD REPORT</b>", styles['HeaderTitle']), Paragraph(f"REV NO: 00 &<br/>DATE: 01-01-2024", styles['HeaderInfo'])],
    ]

    header_table = Table(
        header_data,
        colWidths=[drawable_width * 0.2875, drawable_width * 0.4875, drawable_width * 0.225],
        rowHeights=[0.8*inch, 0.8*inch]
    )
    header_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, border_color),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('SPAN', (0, 0), (0, 1)),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ]))

    # --- Page Template Function ---
    def draw_header(canvas, doc):
        canvas.saveState()
        w, h = header_table.wrap(doc.width, doc.topMargin)
        header_table.drawOn(canvas, doc.leftMargin, doc.height + doc.topMargin - h + 5*mm)
        canvas.restoreState()
        
    # --- Hazard Report Title & Reference Number ---
    story.append(Spacer(1, 4*mm))
    ref_number_data = [
        [Paragraph("<b>Hazard Investigation Report</b>", styles['ReportTitle']), Paragraph(f"<b>Reference number:</b><br/>{hazard.report_number}", styles['HeaderInfo'])]
    ]
    ref_number_table = Table(ref_number_data, colWidths=[drawable_width * 0.7, drawable_width * 0.3])
    ref_number_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, border_color), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('LEFTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(ref_number_table)
    story.append(Spacer(1, 6*mm))

    # --- Section 1: Hazard Overview ---
    story.append(Paragraph("<b>1. HAZARD OVERVIEW</b>", styles['SectionHeader']))
    
    col_width_overview = drawable_width / 4
    overview_data = [
        [Paragraph("<b>Report Number:</b>", styles['Label']), Paragraph(hazard.report_number, styles['Value']), Paragraph("<b>Severity:</b>", styles['Label']), Paragraph(hazard.get_severity_display(), styles['Value'])],
        [Paragraph("<b>Current Status:</b>", styles['Label']), Paragraph(hazard.effective_status_display, styles['Value']),],
        [Paragraph("<b>Date & Time:</b>", styles['Label']), Paragraph(hazard.incident_datetime.strftime('%d-%b-%Y, %I:%M %p'), styles['Value']), Paragraph("<b>Action Deadline:</b>", styles['Label']), Paragraph(hazard.action_deadline.strftime('%d-%b-%Y') if hazard.action_deadline else 'N/A', styles['Value'])],
    ]
    overview_table = Table(overview_data, colWidths=[col_width_overview] * 4)
    overview_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, border_color), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('LEFTPADDING', (0, 0), (-1, -1), 6), ('TOPPADDING', (0,0), (-1,-1), 4), ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(overview_table)
    story.append(Spacer(1, 6*mm))

    # --- Section 2: Hazard Details ---
    story.append(Paragraph("<b>2. HAZARD DESCRIPTION</b>", styles['SectionHeader']))
    
    details_data = [
        [Paragraph("<b>Hazard Type:</b>", styles['Label']), Paragraph(hazard.get_hazard_type_display(), styles['Value'])],
        [Paragraph("<b>Hazard Category:</b>", styles['Label']), Paragraph(hazard.get_hazard_category_display(), styles['Value'])],
        [Paragraph("<b>Hazard Title:</b>", styles['Label']), Paragraph(hazard.hazard_title, styles['Value'])],
        [Paragraph("<b>Detailed Description:</b>", styles['Label']), Paragraph(hazard.hazard_description.replace('\n', '<br/>') or 'N/A', styles['Value'])],
        [Paragraph("<b>Immediate Action Taken:</b>", styles['Label']), Paragraph(hazard.immediate_action.replace('\n', '<br/>') or 'N/A', styles['Value'])],
    ]
    details_table = Table(details_data, colWidths=[drawable_width * 0.25, drawable_width * 0.75])
    details_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 1, border_color), ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 6), ('TOPPADDING', (0,0), (-1,-1), 4), ('BOTTOMPADDING', (0,0), (-1,-1), 4),
    ]))
    story.append(details_table)
    story.append(Spacer(1, 6*mm))
    
    # --- Section 3: Location and Reporter Information ---
    story.append(Paragraph("<b>3. LOCATION & REPORTER INFORMATION</b>", styles['SectionHeader']))
    
    location_data = [
        [Paragraph("<b>Full Location:</b>", styles['Label']), Paragraph(hazard.get_full_location(), styles['Value'])],
        # [Paragraph("<b>Specific Location Details:</b>", styles['Label']), Paragraph(hazard.location_details or 'N/A', styles['Value'])],
        [Paragraph("<b>Reported By:</b>", styles['Label']), Paragraph(f"{hazard.reported_by.get_full_name()} ({hazard.reporter_email})", styles['Value'])],
        [Paragraph("<b>Report Submitted On:</b>", styles['Label']), Paragraph(hazard.reported_date.strftime('%d-%b-%Y, %I:%M %p'), styles['Value'])],
    ]
    if hazard.behalf_person_name:
        dept_name = f"({hazard.behalf_person_dept.name})" if hazard.behalf_person_dept else ""
        location_data.append([Paragraph("<b>Reported On Behalf Of:</b>", styles['Label']), Paragraph(f"{hazard.behalf_person_name} {dept_name}", styles['Value'])])
    
    location_table = Table(location_data, colWidths=[drawable_width * 0.25, drawable_width * 0.75])
    location_table.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 1, border_color), ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 6), ('TOPPADDING', (0,0), (-1,-1), 4), ('BOTTOMPADDING', (0,0), (-1,-1), 4)]))
    story.append(location_table)
    story.append(Spacer(1, 6*mm))

    # --- Section 4: Assignment, Approval & Closure ---
    # story.append(Paragraph("<b>4. ASSIGNMENT, APPROVAL & CLOSURE</b>", styles['SectionHeader']))

    # assignment_data = [
    #     [Paragraph("<b>Assigned To:</b>", styles['Label']), Paragraph(hazard.assigned_to.get_full_name() if hazard.assigned_to else 'Not Assigned', styles['Value'])],
    #     [Paragraph("<b>Approved By:</b>", styles['Label']), Paragraph(hazard.approved_by.get_full_name() if hazard.approved_by else 'Pending Approval', styles['Value'])],
    #     [Paragraph("<b>Approved Date:</b>", styles['Label']), Paragraph(hazard.approved_date.strftime('%d-%b-%Y') if hazard.approved_date else 'N/A', styles['Value'])],
    #     [Paragraph("<b>Approval Remarks:</b>", styles['Label']), Paragraph(hazard.approved_remarks or 'N/A', styles['Value'])],
    #     [Paragraph("<b>Closure Date:</b>", styles['Label']), Paragraph(hazard.closure_date.strftime('%d-%b-%Y') if hazard.closure_date else 'Not Closed', styles['Value'])],
    #     [Paragraph("<b>Closure Remarks:</b>", styles['Label']), Paragraph(hazard.closure_remarks or 'N/A', styles['Value'])],
    # ]
    # assignment_table = Table(assignment_data, colWidths=[drawable_width * 0.25, drawable_width * 0.75])
    # assignment_table.setStyle(TableStyle([('GRID', (0, 0), (-1, -1), 1, border_color), ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0, 0), (-1, -1), 6), ('TOPPADDING', (0,0), (-1,-1), 4), ('BOTTOMPADDING', (0,0), (-1,-1), 4)]))
    # story.append(assignment_table)
    
    # --- Section 5: Corrective / Preventive Action Items ---
    action_items = hazard.action_items.all()
    if action_items.exists():
        story.append(Spacer(1, 6*mm))
        story.append(Paragraph("<b>5. CORRECTIVE / PREVENTIVE ACTION ITEMS</b>", styles['SectionHeader']))
        
        action_header = [
            Paragraph("<b>Action Taken</b>", styles['Label']), 
            Paragraph("<b>Assigned To</b>", styles['Label']), 
            Paragraph("<b>Target Date</b>", styles['Label']), 
            Paragraph("<b>Status</b>", styles['Label']),
            Paragraph("<b>Completion Date</b>", styles['Label'])
        ]
        action_data = [action_header]

        for item in action_items:
            emails = item.responsible_emails.replace(',', ', ')
            action_data.append([
                Paragraph(item.action_description, styles['Value']),
                Paragraph(emails, styles['Value']),
                Paragraph(item.target_date.strftime('%d-%b-%Y') if item.target_date else 'N/A', styles['Value']),
                Paragraph(item.get_status_display(), styles['Value']),
                Paragraph(item.completion_date.strftime('%d-%b-%Y') if item.completion_date else 'Pending', styles['Value'])
            ])
        
        action_table = Table(action_data, colWidths=[drawable_width * 0.35, drawable_width * 0.25, drawable_width * 0.15, drawable_width * 0.10, drawable_width * 0.15])
        action_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 1, border_color), ('BACKGROUND', (0, 0), (-1, 0), header_bg_color), ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('LEFTPADDING', (0,0), (-1,-1), 6), ('TOPPADDING', (0,0), (-1,-1), 4), ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        story.append(action_table)
        story.append(Spacer(1, 6*mm))

    # --- Section 6: Attached Photos ---
        photos = hazard.photos.all()
        if photos.exists():
            # story.append(PageBreak())
            photo_flowables = [Paragraph("<b>6. ATTACHED PHOTOS</b>", styles['SectionHeader'])]
            
            photo_table_data = []
            photo_row = []
            for photo in photos:
                # Pehle check karein ki photo object aur uska path maujood hai ya nahi
                if photo.photo and hasattr(photo.photo, 'path') and os.path.exists(photo.photo.path):
                    # Agar file exist karti hai, to use process karne ki koshish karein
                    try:
                        img = Image(photo.photo.path, width=3*inch, height=3*inch, kind='proportional')
                        img.hAlign = 'CENTER'
                        photo_row.append(img)
                    except Exception as e:
                        # Agar file exist karti hai lekin corrupt hai, to error dikhayein
                        error_text = Paragraph(f"<i>Error reading image:<br/>{os.path.basename(photo.photo.name)}</i>", styles['Value'])
                        photo_row.append(error_text)
                else:
                    # Agar file exist nahi karti, to placeholder text dikhayein
                    error_text = Paragraph(f"<i>Image not found:<br/>{os.path.basename(photo.photo.name)}</i>", styles['Value'])
                    photo_row.append(error_text)

                # Har do photo ke baad table mein ek nayi row banayein
                if len(photo_row) == 2:
                    photo_table_data.append(photo_row)
                    photo_row = []
            
            if photo_row:
                photo_table_data.append(photo_row)
                
            if photo_table_data:
                photo_table = Table(photo_table_data, colWidths=[drawable_width / 2] * 2, rowHeights=3.2*inch)
                photo_table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'), ('GRID', (0, 0), (-1, -1), 1, border_color),
                ]))
                photo_flowables.append(photo_table)
                story.append(KeepTogether(photo_flowables))

    # --- Footer ---
    story.append(Spacer(1, 10*mm))
    footer_text = f"This is a system-generated report from EHS-360 on {datetime.datetime.now().strftime('%d-%b-%Y at %I:%M %p')}"
    story.append(Paragraph(footer_text, styles['FooterText']))
    
    # --- Build the PDF ---
    doc.build(story, onFirstPage=draw_header, onLaterPages=draw_header, canvasmaker=NumberedCanvas)
    
    # Get the PDF data from the buffer and create the HTTP response for download.
    pdf = buffer.getvalue()
    buffer.close()
    
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Hazard_Report_{hazard.report_number}.pdf"'
    response.write(pdf)
    
    return response