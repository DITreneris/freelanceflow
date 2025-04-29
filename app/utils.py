"""
Utility functions for the FreelanceFlow application.
"""

import locale
from datetime import datetime
import io
import tempfile
import os
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.units import inch
import base64
from weasyprint import HTML
import pandas as pd

def format_money(cents, currency="USD"):
    """
    Format money values from cents to dollars/euros with proper currency symbol.
    
    Args:
        cents (int): Value in cents
        currency (str): Currency code (default: USD)
    
    Returns:
        str: Formatted currency string
    """
    # Convert cents to dollars/euros
    dollars = cents / 100.0
    
    # Format based on currency
    if currency == "USD":
        return f"${dollars:.2f}"
    elif currency == "EUR":
        return f"€{dollars:.2f}"
    else:
        return f"{dollars:.2f} {currency}"

def format_date(date_obj, format_str="%Y-%m-%d"):
    """
    Format date objects consistently.
    
    Args:
        date_obj (datetime): Date to format
        format_str (str): Format string (default: YYYY-MM-DD)
    
    Returns:
        str: Formatted date string or empty string if None
    """
    if date_obj is None:
        return ""
    
    return date_obj.strftime(format_str)

def truncate_text(text, max_length=50):
    """
    Truncate text with ellipsis if it exceeds max_length.
    
    Args:
        text (str): Text to truncate
        max_length (int): Maximum length before truncation
    
    Returns:
        str: Truncated text with ellipsis or original text
    """
    if not text or len(text) <= max_length:
        return text
    
    return text[:max_length - 3] + "..."

# PDF generation utilities
def generate_pipeline_summary_pdf(pipeline_stats, company_name="FreelanceFlow"):
    """Generate a PDF report for pipeline summary"""
    buffer = io.BytesIO()
    
    # Create PDF document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = styles['Heading1']
    subtitle_style = styles['Heading2']
    normal_style = styles['Normal']
    
    # Add company name and report title
    elements.append(Paragraph(f"{company_name}", title_style))
    elements.append(Spacer(1, 0.25*inch))
    elements.append(Paragraph("Pipeline Summary Report", subtitle_style))
    elements.append(Spacer(1, 0.1*inch))
    
    # Add date
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    elements.append(Paragraph(f"Generated: {date_str}", normal_style))
    elements.append(Spacer(1, 0.25*inch))
    
    # Pipeline summary table
    pipeline_data = [
        ["Stage", "Count", "Value"],
        ["Lead", pipeline_stats.get("stages", {}).get("lead", {}).get("count", 0), 
         pipeline_stats.get("stages", {}).get("lead", {}).get("value_formatted", "$0")],
        ["Proposed", pipeline_stats.get("stages", {}).get("proposed", {}).get("count", 0), 
         pipeline_stats.get("stages", {}).get("proposed", {}).get("value_formatted", "$0")],
        ["Won", pipeline_stats.get("stages", {}).get("won", {}).get("count", 0), 
         pipeline_stats.get("stages", {}).get("won", {}).get("value_formatted", "$0")],
        ["Total", pipeline_stats.get("total", {}).get("count", 0), 
         pipeline_stats.get("total", {}).get("value_formatted", "$0")]
    ]
    
    table = Table(pipeline_data, colWidths=[2*inch, 1*inch, 2*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 0.5*inch))
    
    # Add summary text
    elements.append(Paragraph("Pipeline Analysis", subtitle_style))
    elements.append(Spacer(1, 0.1*inch))
    
    total_value = pipeline_stats.get("total", {}).get("value", 0) / 100  # Convert cents to dollars
    total_count = pipeline_stats.get("total", {}).get("count", 0)
    avg_deal_size = total_value / total_count if total_count > 0 else 0
    
    elements.append(Paragraph(f"Your pipeline currently contains {total_count} deals with a total value of {format_money(total_value * 100)}.", normal_style))
    elements.append(Spacer(1, 0.1*inch))
    elements.append(Paragraph(f"Average deal size: {format_money(avg_deal_size * 100)}", normal_style))
    
    # Build the PDF
    doc.build(elements)
    
    # Get the PDF data
    buffer.seek(0)
    return buffer.getvalue()

def generate_client_distribution_pdf(client_distribution, company_name="FreelanceFlow"):
    """Generate a PDF report for client distribution"""
    buffer = io.BytesIO()
    
    # Create PDF document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = styles['Heading1']
    subtitle_style = styles['Heading2']
    normal_style = styles['Normal']
    
    # Add company name and report title
    elements.append(Paragraph(f"{company_name}", title_style))
    elements.append(Spacer(1, 0.25*inch))
    elements.append(Paragraph("Top Clients Report", subtitle_style))
    elements.append(Spacer(1, 0.1*inch))
    
    # Add date
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    elements.append(Paragraph(f"Generated: {date_str}", normal_style))
    elements.append(Spacer(1, 0.25*inch))
    
    # Client distribution table
    table_data = [["Client", "Deal Count", "Total Value"]]
    
    for client in client_distribution[:10]:  # Top 10 clients
        table_data.append([
            client.get("name", "Unknown"),
            client.get("deal_count", 0),
            client.get("total_value_formatted", "$0")
        ])
    
    if len(table_data) == 1:  # Only header, no data
        table_data.append(["No client data available", "", ""])
    
    table = Table(table_data, colWidths=[3*inch, 1.5*inch, 1.5*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 0.5*inch))
    
    # Add summary
    elements.append(Paragraph("Client Distribution Analysis", subtitle_style))
    elements.append(Spacer(1, 0.1*inch))
    
    if len(client_distribution) > 0:
        total_deals = sum(client.get("deal_count", 0) for client in client_distribution)
        top_client = client_distribution[0] if client_distribution else {"name": "N/A", "deal_count": 0, "total_value": 0}
        
        elements.append(Paragraph(f"You currently have {total_deals} deals distributed across {len(client_distribution)} clients.", normal_style))
        elements.append(Spacer(1, 0.1*inch))
        elements.append(Paragraph(f"Your top client, {top_client.get('name')}, represents {top_client.get('deal_count')} deals with a total value of {top_client.get('total_value_formatted')}.", normal_style))
    else:
        elements.append(Paragraph("No client data available for analysis.", normal_style))
    
    # Build the PDF
    doc.build(elements)
    
    # Get the PDF data
    buffer.seek(0)
    return buffer.getvalue()

def generate_dashboard_pdf(pipeline_stats, client_distribution, deals_chart_url=None, pipeline_chart_url=None, company_name="FreelanceFlow"):
    """Generate a comprehensive PDF report with charts"""
    buffer = io.BytesIO()
    
    # Create PDF document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    title_style = styles['Heading1']
    subtitle_style = styles['Heading2']
    normal_style = styles['Normal']
    
    # Add company name and report title
    elements.append(Paragraph(f"{company_name}", title_style))
    elements.append(Spacer(1, 0.25*inch))
    elements.append(Paragraph("Dashboard Report", subtitle_style))
    elements.append(Spacer(1, 0.1*inch))
    
    # Add date
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    elements.append(Paragraph(f"Generated: {date_str}", normal_style))
    elements.append(Spacer(1, 0.25*inch))
    
    # Pipeline summary section
    elements.append(Paragraph("Pipeline Summary", subtitle_style))
    elements.append(Spacer(1, 0.1*inch))
    
    # Pipeline summary table
    pipeline_data = [
        ["Stage", "Count", "Value"],
        ["Lead", pipeline_stats.get("stages", {}).get("lead", {}).get("count", 0), 
         pipeline_stats.get("stages", {}).get("lead", {}).get("value_formatted", "$0")],
        ["Proposed", pipeline_stats.get("stages", {}).get("proposed", {}).get("count", 0), 
         pipeline_stats.get("stages", {}).get("proposed", {}).get("value_formatted", "$0")],
        ["Won", pipeline_stats.get("stages", {}).get("won", {}).get("count", 0), 
         pipeline_stats.get("stages", {}).get("won", {}).get("value_formatted", "$0")],
        ["Total", pipeline_stats.get("total", {}).get("count", 0), 
         pipeline_stats.get("total", {}).get("value_formatted", "$0")]
    ]
    
    table = Table(pipeline_data, colWidths=[2*inch, 1*inch, 2*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, -1), (-1, -1), colors.lightgrey),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Add charts if available
    if deals_chart_url and deals_chart_url.startswith("data:image/png;base64,"):
        elements.append(Paragraph("Deal Distribution by Stage", subtitle_style))
        elements.append(Spacer(1, 0.1*inch))
        
        # Extract base64 data
        img_data = deals_chart_url.replace("data:image/png;base64,", "")
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
            tmp.write(base64.b64decode(img_data))
            tmp_path = tmp.name
        
        # Add to PDF
        img = Image(tmp_path, width=5*inch, height=3*inch)
        elements.append(img)
        elements.append(Spacer(1, 0.3*inch))
        
        # Clean up temp file
        os.unlink(tmp_path)
    
    if pipeline_chart_url and pipeline_chart_url.startswith("data:image/png;base64,"):
        elements.append(Paragraph("Pipeline Value by Stage", subtitle_style))
        elements.append(Spacer(1, 0.1*inch))
        
        # Extract base64 data
        img_data = pipeline_chart_url.replace("data:image/png;base64,", "")
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.png') as tmp:
            tmp.write(base64.b64decode(img_data))
            tmp_path = tmp.name
        
        # Add to PDF
        img = Image(tmp_path, width=5*inch, height=3*inch)
        elements.append(img)
        elements.append(Spacer(1, 0.3*inch))
        
        # Clean up temp file
        os.unlink(tmp_path)
    
    # Top Clients section
    elements.append(Paragraph("Top Clients", subtitle_style))
    elements.append(Spacer(1, 0.1*inch))
    
    # Client distribution table
    table_data = [["Client", "Deal Count", "Total Value"]]
    
    for client in client_distribution[:5]:  # Top 5 clients for the report
        table_data.append([
            client.get("name", "Unknown"),
            client.get("deal_count", 0),
            client.get("total_value_formatted", "$0")
        ])
    
    if len(table_data) == 1:  # Only header, no data
        table_data.append(["No client data available", "", ""])
    
    table = Table(table_data, colWidths=[3*inch, 1.5*inch, 1.5*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Summary
    elements.append(Paragraph("Summary", subtitle_style))
    elements.append(Spacer(1, 0.1*inch))
    
    total_value = pipeline_stats.get("total", {}).get("value", 0) / 100  # Convert cents to dollars
    total_count = pipeline_stats.get("total", {}).get("count", 0)
    
    if total_count > 0:
        avg_deal_size = total_value / total_count
        elements.append(Paragraph(f"Your pipeline contains {total_count} deals with a total value of {format_money(total_value * 100)}.", normal_style))
        elements.append(Spacer(1, 0.1*inch))
        elements.append(Paragraph(f"Average deal size: {format_money(avg_deal_size * 100)}", normal_style))
        elements.append(Spacer(1, 0.1*inch))
    else:
        elements.append(Paragraph("No deals in your pipeline yet.", normal_style))
    
    if len(client_distribution) > 0:
        top_client = client_distribution[0]
        elements.append(Paragraph(f"Your top client is {top_client.get('name')} with {top_client.get('deal_count')} deals.", normal_style))
    
    # Build the PDF
    doc.build(elements)
    
    # Get the PDF data
    buffer.seek(0)
    return buffer.getvalue()

def html_to_pdf(html_content):
    """Convert HTML to PDF using WeasyPrint"""
    buffer = io.BytesIO()
    HTML(string=html_content).write_pdf(buffer)
    buffer.seek(0)
    return buffer.getvalue()

# Excel export utilities
def generate_excel_file(data, sheet_name="Sheet1"):
    """Convert data to Excel file format
    
    Args:
        data (list): List of dictionaries with data to export
        sheet_name (str): Name of the Excel sheet
    
    Returns:
        bytes: Excel file content as bytes
    """
    buffer = io.BytesIO()
    
    # Convert data to DataFrame
    df = pd.DataFrame(data)
    
    # Write to Excel
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        # Get workbook and worksheet objects for formatting
        workbook = writer.book
        worksheet = writer.sheets[sheet_name]
        
        # Add formats
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#4285F4',
            'font_color': 'white',
            'border': 1
        })
        
        # Format the header row
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
            
        # Adjust column widths
        for idx, col in enumerate(df.columns):
            max_len = max(df[col].astype(str).apply(len).max(), len(col)) + 2
            worksheet.set_column(idx, idx, max_len)
    
    buffer.seek(0)
    return buffer.getvalue()

def generate_pipeline_excel(pipeline_stats):
    """Generate Excel for pipeline summary data
    
    Args:
        pipeline_stats (dict): Dictionary with pipeline statistics
        
    Returns:
        bytes: Excel file content
    """
    # Create data structure for export
    data = []
    
    # Add header row
    data.append({
        "Stage": "Lead",
        "Count": pipeline_stats.get("stages", {}).get("lead", {}).get("count", 0),
        "Value": pipeline_stats.get("stages", {}).get("lead", {}).get("value_formatted", "$0")
    })
    
    data.append({
        "Stage": "Proposed",
        "Count": pipeline_stats.get("stages", {}).get("proposed", {}).get("count", 0),
        "Value": pipeline_stats.get("stages", {}).get("proposed", {}).get("value_formatted", "$0")
    })
    
    data.append({
        "Stage": "Won",
        "Count": pipeline_stats.get("stages", {}).get("won", {}).get("count", 0),
        "Value": pipeline_stats.get("stages", {}).get("won", {}).get("value_formatted", "$0")
    })
    
    data.append({
        "Stage": "Total",
        "Count": pipeline_stats.get("total", {}).get("count", 0),
        "Value": pipeline_stats.get("total", {}).get("value_formatted", "$0")
    })
    
    return generate_excel_file(data, "Pipeline Summary")

def generate_clients_excel(client_distribution):
    """Generate Excel for client distribution data
    
    Args:
        client_distribution (list): List of clients with deal data
        
    Returns:
        bytes: Excel file content
    """
    data = []
    
    for client in client_distribution:
        data.append({
            "Client": client.get("name", ""),
            "Deal Count": client.get("deal_count", 0),
            "Total Value": client.get("total_value_formatted", "$0")
        })
    
    return generate_excel_file(data, "Client Distribution")

def generate_deals_excel(deals):
    """Generate Excel file with deals data
    
    Args:
        deals (list): List of deals to export
        
    Returns:
        bytes: Excel file content
    """
    data = []
    
    for deal in deals:
        data.append({
            "Client": deal.get("client_name", ""),
            "Stage": deal.get("stage", ""),
            "Value": deal.get("value_formatted", "$0"),
            "Updated": deal.get("updated_at", "")
        })
    
    return generate_excel_file(data, "Deals") 