"""
PDF Generator for Financial Reports
Uses ReportLab to generate professional PDF reports
"""
from reportlab.lib.pagesizes import A4, letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from io import BytesIO
from datetime import datetime
import os


def generate_financial_report_pdf(report_data, title, report_type, start_date=None, end_date=None):
    """
    Generate a PDF financial report
    
    Args:
        report_data: Dictionary containing report data (from get_financial_reports)
        title: Report title
        report_type: Type of report (daily, weekly, monthly, custom)
        start_date: Start date string (optional)
        end_date: End date string (optional)
    
    Returns:
        BytesIO object containing the PDF
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                           rightMargin=72, leftMargin=72,
                           topMargin=72, bottomMargin=18)
    
    # Register a Unicode-compatible font for proper currency symbol display
    try:
        # Try to use DejaVu Sans which supports Unicode
        from reportlab.pdfbase.pdfmetrics import registerFontFamily
        from reportlab.pdfbase.ttfonts import TTFont
        
        # Use system fonts that support Unicode
        font_paths = [
            'C:/Windows/Fonts/arial.ttf',  # Windows Arial
            'C:/Windows/Fonts/calibri.ttf',  # Windows Calibri
            '/System/Library/Fonts/Arial.ttf',  # macOS Arial
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',  # Linux DejaVu
        ]
        
        unicode_font = None
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    pdfmetrics.registerFont(TTFont('UnicodeFont', font_path))
                    unicode_font = 'UnicodeFont'
                    break
                except:
                    continue
        
        # Fallback to built-in fonts if no Unicode font found
        if not unicode_font:
            unicode_font = 'Helvetica'
            
    except Exception:
        unicode_font = 'Helvetica'
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Define styles
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#2E7D32'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName=unicode_font
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#2E7D32'),
        spaceAfter=12,
        spaceBefore=12,
        fontName=unicode_font
    )
    
    # Add title
    title_text = Paragraph(title, title_style)
    elements.append(title_text)
    
    # Add date range if provided
    if start_date and end_date:
        date_range = Paragraph(f"<b>Period:</b> {start_date} to {end_date}", styles['Normal'])
        elements.append(date_range)
        elements.append(Spacer(1, 12))
    
    # Add generated timestamp
    generated_time = Paragraph(f"<i>Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>", styles['Normal'])
    elements.append(generated_time)
    elements.append(Spacer(1, 20))
    
    # Summary Section
    summary = report_data.get('summary', {})
    elements.append(Paragraph("📊 Summary", heading_style))
    
    summary_data = [
        ['Metric', 'Value'],
        ['Total Orders', str(summary.get('total_orders', 0))],
        ['Total Revenue', f"{summary.get('total_order_amount', 0):.2f}"],
        ['Platform Fee', f"{summary.get('total_platform_fee', 0):.2f}"],
        ['Delivery Charges', f"{summary.get('total_delivery_charge', 0):.2f}"],
        ['COD Collected', f"{summary.get('total_cod_collected', 0):.2f}"],
        ['Average Order Value', f"{summary.get('average_order_value', 0):.2f}"],
    ]
    
    summary_table = Table(summary_data, colWidths=[3*inch, 3*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E7D32')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), unicode_font),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (0, -1), unicode_font),
    ]))
    elements.append(summary_table)
    elements.append(Spacer(1, 20))
    
    # Payment Method Breakdown
    elements.append(Paragraph("💳 Payment Method Breakdown", heading_style))
    payment_breakdown = report_data.get('payment_breakdown', {})
    payment_data = [['Payment Method', 'Orders', 'Amount', 'Percentage']]
    
    total_amount = summary.get('total_order_amount', 0)
    for method, method_data in payment_breakdown.items():
        percentage = (method_data['amount'] / total_amount * 100) if total_amount > 0 else 0
        payment_data.append([
            method.upper(),
            str(method_data['count']),
            f"{method_data['amount']:.2f}",
            f"{percentage:.1f}%"
        ])
    
    payment_table = Table(payment_data, colWidths=[1.5*inch, 1.5*inch, 1.5*inch, 1.5*inch])
    payment_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E7D32')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), unicode_font),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
    ]))
    elements.append(payment_table)
    elements.append(Spacer(1, 20))
    
    # Delivery Status Breakdown
    elements.append(Paragraph("🚚 Delivery Status Breakdown", heading_style))
    delivery_breakdown = report_data.get('delivery_breakdown', {})
    delivery_data = [['Status', 'Orders', 'Amount', 'Percentage']]
    
    total_orders = summary.get('total_orders', 0)
    for status, status_data in delivery_breakdown.items():
        percentage = (status_data['count'] / total_orders * 100) if total_orders > 0 else 0
        status_label = status.replace('_', ' ').title()
        delivery_data.append([
            status_label,
            str(status_data['count']),
            f"{status_data['amount']:.2f}",
            f"{percentage:.1f}%"
        ])
    
    delivery_table = Table(delivery_data, colWidths=[1.5*inch, 1.5*inch, 1.5*inch, 1.5*inch])
    delivery_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E7D32')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), unicode_font),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
    ]))
    elements.append(delivery_table)
    elements.append(Spacer(1, 20))
    
    # Daily Breakdown (if available)
    daily_breakdown = report_data.get('daily_breakdown', [])
    if daily_breakdown:
        elements.append(Paragraph("📅 Daily Breakdown", heading_style))
        daily_data = [['Date', 'Orders', 'Revenue', 'Platform Fee', 'Delivery', 'COD']]
        
        for day in daily_breakdown:
            daily_data.append([
                str(day['date']),
                str(day['orders_count']),
                f"{day['total_amount']:.2f}",
                f"{day['platform_fee']:.2f}",
                f"{day['delivery_charge']:.2f}",
                f"{day['cod_collected']:.2f}"
            ])
        
        daily_table = Table(daily_data, colWidths=[1*inch, 0.8*inch, 1.2*inch, 1.1*inch, 0.9*inch, 1*inch])
        daily_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E7D32')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), unicode_font),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
        ]))
        elements.append(daily_table)
        elements.append(Spacer(1, 20))
    
    # Top Delivery Boys (if available)
    top_delivery_boys = report_data.get('top_delivery_boys', [])
    if top_delivery_boys:
        elements.append(Paragraph("🏆 Top Delivery Boys", heading_style))
        delivery_boy_data = [['Delivery Boy', 'Total Earnings', 'Deliveries', 'Avg per Delivery']]
        
        for delivery_boy in top_delivery_boys[:10]:  # Top 10
            avg_earning = (delivery_boy['total_earnings'] / delivery_boy['delivery_count']) if delivery_boy['delivery_count'] > 0 else 0
            delivery_boy_data.append([
                delivery_boy['delivery_boy__username'],
                f"{delivery_boy['total_earnings']:.2f}",
                str(delivery_boy['delivery_count']),
                f"{avg_earning:.2f}"
            ])
        
        delivery_boy_table = Table(delivery_boy_data, colWidths=[2*inch, 1.5*inch, 1.5*inch, 1.5*inch])
        delivery_boy_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E7D32')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), unicode_font),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))
        elements.append(delivery_boy_table)
        elements.append(Spacer(1, 20))
    
    # COD Information
    elements.append(Paragraph("💰 COD Information", heading_style))
    cod_data = [
        ['Metric', 'Value'],
        ['COD Collected', f"{summary.get('total_cod_collected', 0):.2f}"],
        ['COD Submitted', f"{summary.get('total_cod_submitted', 0):.2f}"],
        ['Pending COD', f"{summary.get('pending_cod_amount', 0):.2f}"],
    ]
    
    cod_table = Table(cod_data, colWidths=[3*inch, 3*inch])
    cod_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E7D32')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), unicode_font),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTNAME', (0, 1), (0, -1), unicode_font),
    ]))
    elements.append(cod_table)
    
    # Build PDF
    doc.build(elements)
    
    # Get the value of the BytesIO buffer and return it
    pdf = buffer.getvalue()
    buffer.close()
    return pdf

