import io
import pandas as pd
from typing import List, Dict, Any
from datetime import datetime

def generate_pipeline_excel(pipeline_data: Dict[str, Any]) -> bytes:
    """
    Generate Excel file for pipeline summary data
    
    Args:
        pipeline_data: Dictionary containing pipeline statistics
        
    Returns:
        Excel file as bytes
    """
    # Create pipeline summary dataframe
    pipeline_df = pd.DataFrame({
        'Stage': ['Lead', 'Proposed', 'Won'],
        'Count': [
            pipeline_data['lead_count'], 
            pipeline_data['proposed_count'], 
            pipeline_data['won_count']
        ],
        'Value ($)': [
            pipeline_data['lead_value'], 
            pipeline_data['proposed_value'], 
            pipeline_data['won_value']
        ]
    })
    
    # Add totals row
    pipeline_df.loc[len(pipeline_df)] = [
        'Total', 
        pipeline_data['total_count'],
        pipeline_data['total_value']
    ]
    
    # Create Excel writer with pandas
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        pipeline_df.to_excel(writer, sheet_name='Pipeline Summary', index=False)
        
        # Get the worksheet and workbook
        workbook = writer.book
        worksheet = writer.sheets['Pipeline Summary']
        
        # Add formats
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#0d6efd',
            'color': 'white',
            'border': 1
        })
        
        total_format = workbook.add_format({
            'bold': True,
            'bg_color': '#f8f9fa',
            'border': 1
        })
        
        # Format cells
        for col_num, value in enumerate(pipeline_df.columns.values):
            worksheet.write(0, col_num, value, header_format)
        
        # Format total row
        for col_num in range(len(pipeline_df.columns)):
            worksheet.write(4, col_num, pipeline_df.iloc[3, col_num], total_format)
        
        # Set column widths
        worksheet.set_column('A:A', 15)
        worksheet.set_column('B:C', 20)
        
        # Add a title
        title_format = workbook.add_format({'bold': True, 'font_size': 16})
        worksheet.write('A1', 'Pipeline Summary', title_format)
        worksheet.write('A2', f'Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M")}')
        
        # Start the actual data at row 4
        pipeline_df.to_excel(writer, sheet_name='Pipeline Summary', startrow=3, index=False)
    
    return output.getvalue()

def generate_clients_excel(client_data: List[Dict[str, Any]]) -> bytes:
    """
    Generate Excel file for client distribution data
    
    Args:
        client_data: List of dictionaries containing client distribution data
        
    Returns:
        Excel file as bytes
    """
    # Create clients dataframe
    clients_df = pd.DataFrame(client_data)
    
    # Create Excel writer with pandas
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        clients_df.to_excel(writer, sheet_name='Client Distribution', index=False)
        
        # Get the worksheet and workbook
        workbook = writer.book
        worksheet = writer.sheets['Client Distribution']
        
        # Add formats
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#0d6efd',
            'color': 'white',
            'border': 1
        })
        
        # Format header
        for col_num, value in enumerate(clients_df.columns.values):
            worksheet.write(0, col_num, value, header_format)
        
        # Set column widths
        for i, col in enumerate(clients_df.columns):
            column_width = max(clients_df[col].astype(str).map(len).max(), len(col)) + 2
            worksheet.set_column(i, i, column_width)
        
        # Add title
        title_format = workbook.add_format({'bold': True, 'font_size': 16})
        worksheet.merge_range('A1:C1', 'Client Distribution Report', title_format)
        worksheet.write('A2', f'Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M")}')
        
        # Start the actual data at row 4
        clients_df.to_excel(writer, sheet_name='Client Distribution', startrow=3, index=False)
    
    return output.getvalue()

def generate_deals_excel(deals_data: List[Dict[str, Any]]) -> bytes:
    """
    Generate Excel file for deals data
    
    Args:
        deals_data: List of dictionaries containing deals data
        
    Returns:
        Excel file as bytes
    """
    # Create deals dataframe
    deals_df = pd.DataFrame(deals_data)
    
    # Create Excel writer with pandas
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        deals_df.to_excel(writer, sheet_name='Deals', index=False)
        
        # Get the worksheet and workbook
        workbook = writer.book
        worksheet = writer.sheets['Deals']
        
        # Add formats
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#0d6efd',
            'color': 'white',
            'border': 1
        })
        
        currency_format = workbook.add_format({'num_format': '$#,##0.00'})
        date_format = workbook.add_format({'num_format': 'yyyy-mm-dd'})
        
        # Format header
        for col_num, value in enumerate(deals_df.columns.values):
            worksheet.write(0, col_num, value, header_format)
        
        # Format columns based on data type
        if 'value' in deals_df.columns:
            value_col = deals_df.columns.get_loc('value')
            worksheet.set_column(value_col, value_col, 15, currency_format)
        
        if 'created_at' in deals_df.columns:
            date_col = deals_df.columns.get_loc('created_at')
            worksheet.set_column(date_col, date_col, 12, date_format)
        
        if 'updated_at' in deals_df.columns:
            date_col = deals_df.columns.get_loc('updated_at')
            worksheet.set_column(date_col, date_col, 12, date_format)
        
        # Set column widths
        for i, col in enumerate(deals_df.columns):
            if col not in ['value', 'created_at', 'updated_at']:
                column_width = max(deals_df[col].astype(str).map(len).max(), len(col)) + 2
                worksheet.set_column(i, i, column_width)
        
        # Add title
        title_format = workbook.add_format({'bold': True, 'font_size': 16})
        worksheet.merge_range('A1:E1', 'Deals Report', title_format)
        worksheet.write('A2', f'Generated on: {datetime.now().strftime("%Y-%m-%d %H:%M")}')
        
        # Start the actual data at row 4
        deals_df.to_excel(writer, sheet_name='Deals', startrow=3, index=False)
    
    return output.getvalue() 