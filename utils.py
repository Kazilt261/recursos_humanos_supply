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
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Planilla')
        workbook = writer.book
        worksheet = writer.sheets['Planilla']

        header_format = workbook.add_format({
            'bold': True, 'text_wrap': True, 'valign': 'top',
            'fg_color': '#1F4E78', 'font_color': 'white', 
            'border': 1, 'align': 'center'
        })
        money_format = workbook.add_format({'num_format': '$ #,##0', 'border': 1})
        uf_format = workbook.add_format({'num_format': '#,##0.00', 'border': 1}) # Nuevo formato para indicadores
        text_format = workbook.add_format({'border': 1})

        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
            
            max_len = max(df[value].astype(str).map(len).max(), len(str(value))) + 2
            col_name_str = str(value)
            
            # Keywords corregidas para hacer match exacto con tu diccionario de costos
            keywords_dinero = ['Sueldo', 'Costo', 'Total', 'Bono', 'Gratificación', 
                               'Colación', 'Movilización', 'AFP', 'Salud', 'Seguro', 
                               'Impuesto', 'SIS', 'Mutual', 'Ley', 'Aporte', 'Provisión', 'LÍQUIDO', 'líquida']
            
            # 1. Si es UF o UTM, usa formato con decimales (sin signo $)
            if "Cálculo" in col_name_str:
                worksheet.set_column(col_num, col_num, max_len + 2, uf_format)
            # 2. Si es costo/sueldo, usa formato peso chileno
            elif any(k in col_name_str for k in keywords_dinero) and "Contrato" not in col_name_str:
                worksheet.set_column(col_num, col_num, max_len + 2, money_format)
            # 3. Textos e IDs
            else:
                worksheet.set_column(col_num, col_num, max_len, text_format)

    return output.getvalue()