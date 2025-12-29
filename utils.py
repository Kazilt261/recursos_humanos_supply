import pandas as pd
from io import BytesIO
import decimal

def redondear_excel(valor, decimales=0):
    if valor is None: return 0
    try:
        if decimales > 0:
            return round(valor, decimales)
        d = decimal.Decimal(str(float(valor)))
        return int(d.quantize(decimal.Decimal('1'), rounding=decimal.ROUND_HALF_UP))
    except:
        return 0

def generar_excel_estilizado(df):
    """Genera un archivo Excel con formato profesional (encabezados azules, moneda, anchos)."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Planilla')
        workbook = writer.book
        worksheet = writer.sheets['Planilla']

        # --- FORMATOS ---
        header_format = workbook.add_format({
            'bold': True, 'text_wrap': True, 'valign': 'top',
            'fg_color': '#1F4E78', 'font_color': 'white', # Azul corporativo
            'border': 1, 'align': 'center'
        })
        money_format = workbook.add_format({'num_format': '$ #,##0', 'border': 1})
        text_format = workbook.add_format({'border': 1})

        # --- APLICAR FORMATOS ---
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
            
            # Ancho columna
            max_len = max(df[value].astype(str).map(len).max(), len(str(value))) + 2
            
            # Detectar si es dinero
            keywords_dinero = ['Sueldo', 'Costo', 'Total', 'Bono', 'Gratificación', 
                               'Colación', 'Movilización', 'AFP', 'Salud', 'Seg.', 
                               'Impuesto', 'SIS', 'Mutual', 'Ley', 'Aporte', 'Prov.', 'Fee', 'Líquido']
            
            es_dinero = any(k in str(value) for k in keywords_dinero) and "Contrato" not in str(value)

            if es_dinero:
                worksheet.set_column(col_num, col_num, max_len + 2, money_format)
            else:
                worksheet.set_column(col_num, col_num, max_len, text_format)

    return output.getvalue()