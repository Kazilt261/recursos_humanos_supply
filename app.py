import streamlit as st
import streamlit_authenticator as stauth
import pandas as pd
import time
import altair as alt
from datetime import datetime

# --- IMPORTAMOS NUESTROS ARCHIVOS PROPIOS ---
from auth_manager import AdminUsuarios
from calculos import GestorParametros, CalculadoraCostos
from utils import generar_excel_estilizado

# Configuración Inicial
st.set_page_config(page_title="Simulador RRHH Pro", layout="wide", page_icon="💼")

# Estilos CSS
st.markdown("""
<style>
    .metric-card {background-color: #ffffff; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); border: 1px solid #e0e0e0; margin-bottom: 15px;}
    div[data-testid="stMetricValue"] {font-size: 1.8rem !important; font-weight: 600; color: #0f172a;}
    div[data-testid="stMetricLabel"] {font-size: 1rem !important; color: #64748b;}
</style>
""", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# 1. LÓGICA DE SEGURIDAD
# -----------------------------------------------------------------------------
admin_tools = AdminUsuarios()
config = admin_tools.cargar_config()

try:
    authenticator = stauth.Authenticate(
        config['credentials'], config['cookie']['name'], config['cookie']['key'], config['cookie']['expiry_days']
    )
    try: authenticator.login()
    except: name, authentication_status, username = authenticator.login('Login', 'main')

    if st.session_state["authentication_status"] is False:
        st.error('Usuario o contraseña incorrectos'); st.stop()
    elif st.session_state["authentication_status"] is None:
        st.warning('Por favor, ingresa tus credenciales'); st.stop()
    
    with st.sidebar:
        st.write(f"👤 **{st.session_state['name']}**")
        authenticator.logout('Cerrar Sesión', 'sidebar')
        st.divider()
except:
    st.session_state["username"] = "admin" 

# -----------------------------------------------------------------------------
# 2. INICIALIZACIÓN
# -----------------------------------------------------------------------------
gestor = GestorParametros()
calc = CalculadoraCostos(gestor)

if 'escenarios' not in st.session_state: st.session_state.escenarios = []
if 'nomina_df' not in st.session_state:
    st.session_state.nomina_df = pd.DataFrame([
        {
            "Rol": "Gerente", "Cantidad": 1, 
            "Sueldo bruto (Input)": 0, "Total Haberes (Input)": 0, "Sueldo Líquido (Input)": 2500000, 
            "Contrato": "Indefinido", "Bono": 0, "Colación": 100000, "Movilización": 0
        },
        {
            "Rol": "Chofer", "Cantidad": 10, 
            "Sueldo bruto (Input)": 0, "Total Haberes (Input)": 0, "Sueldo Líquido (Input)": 900000, 
            "Contrato": "Indefinido", "Bono": 0, "Colación": 100000, "Movilización": 0
        }
    ])

col_head_1, col_head_2 = st.columns([3, 1])
with col_head_1:
    st.title("💼 Simulador de Remuneraciones")
with col_head_2:
    st.info(f"**Indicadores Hoy**\n\nUF: ${gestor.obtener_uf():,.2f}\n\nUTM: ${gestor.obtener_utm():,.0f}")

# -----------------------------------------------------------------------------
# 3. INTERFAZ GRÁFICA (TABS)
# -----------------------------------------------------------------------------
es_admin = (st.session_state.get("username") == "admin")
lista_tabs = ["📊 Simulador Individual", "👥 Nómina Masiva", "📈 Análisis", "⚙️ Configuración"]
if es_admin: lista_tabs.append("🔐 Gestión Usuarios")

tabs = st.tabs(lista_tabs)

# --- TAB 1: SIMULADOR INDIVIDUAL ---
with tabs[0]:
    c_inputs, c_results = st.columns([4, 6], gap="large")
    with c_inputs:
        st.subheader("1. Configuración")
        with st.container(border=True):
            tipo_calculo = st.radio("Entrada:", ["Sueldo Líquido", "Total Haberes", "Sueldo Bruto"], horizontal=True)
            target = st.number_input(f"Monto {tipo_calculo} ($)", value=1000000, step=50000)
            tipo_con = st.selectbox("Contrato", ["Indefinido", "Plazo Fijo"])
            es_indef = (tipo_con == "Indefinido")
        
        with st.container(border=True):
            c1, c2 = st.columns(2)
            col_in = c1.number_input("Colación", value=100000); mov_in = c2.number_input("Movilización", value=0)
            bon_in = st.number_input("Bonos Imp.", value=0); oni_in = st.number_input("Otros No Imp.", value=0)
        
        with st.expander("Parámetros Avanzados"):
            c3, c4 = st.columns(2)
            afp_in = c3.number_input("AFP %", 11.45); sal_in = c4.number_input("Salud %", 7.0)
            isa_in = st.number_input("Isapre (UF)", 0.0); apv_in = st.number_input("APV ($)", 0)
            st.divider()
            use_admin_pct = st.toggle("Admin %", False)
            adm_in = st.number_input("Admin", 0.0); mgt_in = st.number_input("Mgmt", 0)
            check_bono = st.checkbox("Prov. Bono Anual", True)

    if tipo_calculo == "Sueldo Líquido":
        res = calc.encontrar_sueldo_base_iterativo(
            target, es_indef, col_in, mov_in, oni_in, bon_in, 0, adm_in, use_admin_pct, mgt_in, 
            check_bono, afp_in, sal_in, apv_in, isa_in, 
            campo_objetivo="SUELDO LÍQUIDO"
        )
    elif tipo_calculo == "Total Haberes":
        res = calc.encontrar_sueldo_base_iterativo(
            target, es_indef, col_in, mov_in, oni_in, bon_in, 0, adm_in, use_admin_pct, mgt_in, 
            check_bono, afp_in, sal_in, apv_in, isa_in, 
            campo_objetivo="TOTAL HABERES"
        )
    else: # Sueldo Bruto
        res = calc.calcular_costo_empresa(
            target, es_indef, col_in, mov_in, oni_in, bon_in, 0, adm_in, use_admin_pct, mgt_in, 
            check_bono, afp_in, sal_in, apv_in, isa_in
        )

    with c_results:
        st.subheader("Resultado")
        with st.container(border=True):
            m1, m2, m3, m4 = st.columns(4)
        
            
    
            m1.metric("Sueldo Líquido", f"${res['SUELDO LÍQUIDO']:,.0f}", delta="Resultado")
            m2.metric("Tot. Haberes", f"${res['TOTAL HABERES']:,.0f}", delta="Objetivo" if tipo_calculo=="Total Haberes" else None)
            m3.metric("Costo Empresa Supplynet", f"${res['Costo Empresa Supplynet']:,.0f}")
            m4.metric("Costo Total(IAS)", f"${res['Costo Total(IAS)']:,.0f}")
            
            st.divider()
            
            
            items_ordenados = [
                "Sueldo bruto","Colación","Movilización","Gratificación", "Total Imponible", "TOTAL HABERES",
                "AFP", "Salud Total", "Seguro Cesantía(Trabajador)", "Impuesto Único",
                "Total Descuentos", "-----------------",
                "Ley SANNA", "Mutual", "SIS", "Seguro Cesantía (Empresa)",
                "-----------------",
                "Provisión Vacaciones", "Provisión Indemnización", 
                "Provisión Bono Anual", "Seguro Salud (1 UF)",
                "-----------------",
                "Costo Admin", "Costo Mgmt","Costo Empresa Supplynet","Costo Total(IAS)"
            ]
            rows = []
            for k in items_ordenados:
                if k == "-----------------": continue
                rows.append({"Concepto": k, "Monto": res.get(k, 0)})
            
            st.dataframe(pd.DataFrame(rows).style.format({"Monto": "${:,.0f}"}), use_container_width=True, height=400, hide_index=True)

        if st.button("💾 Guardar Escenario"):
            st.session_state.escenarios.append({"ID": len(st.session_state.escenarios)+1, "Hora": datetime.now().strftime("%H:%M"), "Monto": target, "Tipo": tipo_calculo, "Líquido": res["SUELDO LÍQUIDO"], "Total Costo": res["COSTO FINANCIERO TOTAL"], "full_res": res})
            st.toast("Guardado")

# --- TAB 2: NÓMINA MASIVA ---
with tabs[1]:
    st.header("👥 Nómina Masiva por Perfiles")
    
    with st.expander("🛠️ Generador Rápido", expanded=True):
        cg1, cg2, cg3 = st.columns(3)
        n_perf = cg1.number_input("Perfiles", 1, value=3)
        sueldo_ini = cg2.number_input("Monto Inicial", value=800000)
        
        tipo_gen = cg2.radio("Llenar con:", ["Sueldo Líquido", "Total Haberes", "Sueldo Bruto"])
        
        if cg3.button("Crear Nueva Tabla"):
            data = []
            for i in range(n_perf):
                bruto = sueldo_ini if tipo_gen == "Sueldo Bruto" else 0
                haberes = sueldo_ini if tipo_gen == "Total Haberes" else 0
                liquido = sueldo_ini if tipo_gen == "Sueldo Líquido" else 0
                
                data.append({
                    "Rol": f"Perfil {i+1}", 
                    "Cantidad": 1, 
                    "Sueldo bruto (Input)": bruto, 
                    "Total Haberes (Input)": haberes, 
                    "Sueldo Líquido (Input)": liquido, 
                    "Contrato": "Indefinido", "Bono": 0, "Colación": 100000, "Movilización": 0
                })
            st.session_state.nomina_df = pd.DataFrame(data)
            st.rerun()

    with st.container(border=True):
        st.subheader("Configuración Global")
        c_gl1, c_gl2, c_gl3 = st.columns(3)
        g_afp = c_gl1.number_input("AFP Global", 11.45)
        g_salud = c_gl2.number_input("Salud Global", 7.0)
        g_bono_anual = c_gl3.checkbox("Bono Anual (5%)", value=True)
        
        st.markdown("---")
        
        # --- AQUÍ ESTÁ EL CAMBIO PARA ADMIN EN % ---
        c_gl4, c_gl5 = st.columns(2)
        
        # 1. Toggle para decidir si es porcentaje
        g_use_admin_pct = c_gl4.toggle("¿Admin Global es %?", value=False)
        
        # 2. Input numérico adaptativo
        label_admin_g = "Admin Global (%)" if g_use_admin_pct else "Admin Global ($)"
        step_admin_g = 0.5 if g_use_admin_pct else 1000.0
        
        g_admin = c_gl4.number_input(label_admin_g, value=0.0, step=step_admin_g)
        
        # Mgmt lo dejamos fijo por ahora (o podrías pedir añadirlo si quieres)
        g_mgmt = 0 

    edited_df = st.data_editor(st.session_state.nomina_df, num_rows="dynamic", use_container_width=True,
        column_config={
            "Sueldo bruto (Input)": st.column_config.NumberColumn("Sueldo bruto (Input)", format="$%d"),
            "Total Haberes (Input)": st.column_config.NumberColumn("Total Haberes (Input)", format="$%d"),
            "Sueldo Líquido (Input)": st.column_config.NumberColumn("Sueldo Líquido (Input)", format="$%d")
        }
    )

    if st.button("🚀 Calcular Nómina", type="primary"):
        res_nomina = []
        total_costo_empresa = 0
        total_liquido = 0
        total_costo_Empresa_sin = 0
        
        progress_bar = st.progress(0)
        total_rows = len(edited_df)

        for index, row in edited_df.iterrows():
            cant = int(row.get('Cantidad', 1))
            
            base_in = row.get('Sueldo bruto (Input)', 0) 
            haberes_in = row.get('Total Haberes (Input)', 0) 
            liq_in = row.get('Sueldo Líquido (Input)', 0)
            
            # Pasamos g_use_admin_pct (True/False) en lugar del "False" fijo
            if base_in > 0:
                r = calc.calcular_costo_empresa(base_in, row['Contrato']=="Indefinido", row.get('Colación',0), row.get('Movilización',0), 0, row.get('Bono',0), 0, g_admin, g_use_admin_pct, 0, g_bono_anual, g_afp, g_salud, 0, 0)
            elif haberes_in > 0:
                r = calc.encontrar_sueldo_base_iterativo(haberes_in, row['Contrato']=="Indefinido", row.get('Colación',0), row.get('Movilización',0), 0, row.get('Bono',0), 0, g_admin, g_use_admin_pct, 0, g_bono_anual, g_afp, g_salud, 0, 0, campo_objetivo="TOTAL HABERES")
            else:
                r = calc.encontrar_sueldo_base_iterativo(liq_in, row['Contrato']=="Indefinido", row.get('Colación',0), row.get('Movilización',0), 0, row.get('Bono',0), 0, g_admin, g_use_admin_pct, 0, g_bono_anual, g_afp, g_salud, 0, 0, campo_objetivo="SUELDO LÍQUIDO")
            
            for i in range(cant):
                suffix = f" ({i+1})" if cant > 1 else ""
                fila = {
                    "Rol": f"{row['Rol']}{suffix}",
                    "Nombre": "",
                    "Tipo Contrato": row['Contrato'],
                    **r
                }
                res_nomina.append(fila)
                total_costo_empresa += r['COSTO FINANCIERO TOTAL']
                total_liquido += r['SUELDO LÍQUIDO']
                total_costo_Empresa_sin += r['COSTO FINANCIERO TOTAL sin ind']

            progress_bar.progress((index + 1) / total_rows)

        progress_bar.empty()
        st.success("Cálculo Finalizado")

        m_tot1, m_tot2, m_tot3, m_tot4 = st.columns(4)
        m_tot1.metric("Trabajadores", len(res_nomina))
        m_tot2.metric("Total Líquido", f"${total_liquido:,.0f}")
        m_tot3.metric("Costo Empresa Supplynet", f"${total_costo_Empresa_sin:,.0f}")
        m_tot4.metric("Costo Total", f"${total_costo_empresa:,.0f}")

        df_final = pd.DataFrame(res_nomina)
        
        cols_orden = [
                "Rol","Nombre", "Tipo Contrato", "Sueldo bruto","Colación","Movilización","Gratificación", "Total Imponible", "TOTAL HABERES",
                "AFP", "Salud Total", "Seguro Cesantía(Trabajador)", "Impuesto Único",
                "Total Descuentos", "-----------------",
                "Ley SANNA", "Mutual", "SIS", "Seguro Cesantía (Empresa)",
                "-----------------",
                "Provisión Vacaciones", "Provisión Indemnización",
                "Provisión Bono Anual", "Seguro Salud (1 UF)",
                "-----------------",
                "Costo Admin", "Costo Mgmt","Costo Empresa Supplynet","Costo Total(IAS)"
        ]    
        
        cols_existentes = [c for c in cols_orden if c in df_final.columns]
        df_final = df_final[cols_existentes]

        st.dataframe(df_final, use_container_width=True)
        
        excel_data = generar_excel_estilizado(df_final)
        st.download_button("📥 Descargar Excel", excel_data, "nomina_masiva.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# --- TAB 3: ANÁLISIS ---
with tabs[2]:
    st.header("Análisis")
    if st.session_state.escenarios:
        df_hist = pd.DataFrame(st.session_state.escenarios)
        
        # CORRECCIÓN GRÁFICO (RENOMBRAR PARA EVITAR CONFLICTO)
        df_grafico = df_hist.rename(columns={"Monto": "Monto Ingresado"})
        
        try:
            df_melted = df_grafico.melt(
                id_vars=["ID"], 
                value_vars=["Total Costo", "Líquido", "Monto Ingresado"], 
                var_name="Tipo", 
                value_name="Monto ($)"
            )
            c = alt.Chart(df_melted).mark_line(point=True).encode(
                x='ID:O', y='Monto ($):Q', color='Tipo', tooltip=['ID', 'Tipo', alt.Tooltip('Monto ($)', format='$,.0f')]
            ).interactive()
            st.altair_chart(c, use_container_width=True)
            
            # --- AQUÍ ESTÁ EL CAMBIO PARA EL EXCEL COMPLETO ---
            df_detalles = pd.json_normalize(df_hist['full_res'])
            df_base = df_hist.drop(columns=['full_res', 'Líquido', 'Total Costo']).reset_index(drop=True)
            df_export_completo = pd.concat([df_base, df_detalles], axis=1)
            
            excel_hist = generar_excel_estilizado(df_export_completo)
            
            st.download_button(
                label="📥 Descargar Historial Completo (Detallado)", 
                data=excel_hist, 
                file_name="historial_full_detalle.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
        except Exception as e:
            st.error(f"Error al procesar los datos: {e}")
            st.write("Intenta guardar un nuevo escenario para limpiar los datos antiguos.")
            
    else:
        st.info("Sin datos.")

# --- TAB 4: CONFIG ---
with tabs[3]:
    st.header("⚙️ Configuración de Parámetros")

    # Fila 1: Indicadores e Impuestos (Solo Visualización)
    c1, c2 = st.columns([1, 2])
    with c1:
        st.subheader("Indicadores (API)")
        st.json(gestor.datos["indicadores"])
        if st.button("🔄 Actualizar UF/UTM"):
            ok, msg = gestor.obtener_indicadores_online()
            if ok: st.success(msg); time.sleep(1); st.rerun()
            else: st.error(msg)
    
    with c2:
        st.subheader("Tabla Impuesto 2da Categoría")
        st.dataframe(calc.obtener_tabla_impuesto_visual(), hide_index=True, use_container_width=True)

    st.divider()

    # Fila 2: Edición de Parámetros (NUEVO)
    st.subheader("📝 Parámetros Legales Editables")
    st.info("Modifica aquí los valores internos del cálculo. Recuerda guardar para aplicar los cambios.")

    params_actuales = gestor.datos["parametros"]
    
    with st.form("form_parametros"):
        col_p1, col_p2, col_p3 = st.columns(3)
        
        with col_p1:
            val_sueldo = float(params_actuales.get("sueldo_minimo", 500000))
            n_sueldo = st.number_input("Sueldo Mínimo ($)", value=val_sueldo, step=1000.0)
            n_sis = st.number_input("SIS (%)", value=params_actuales.get("tasa_sis", 1.44), step=0.01)
        
        with col_p2:
            n_tope_afp = st.number_input("Tope Imponible AFP (UF)", value=params_actuales.get("factor_tope_afp", 84.3), step=0.1)
            n_sanna = st.number_input("Ley SANNA (%)", value=params_actuales.get("sanna", 0.03), step=0.01)
        
        with col_p3:
            n_tope_ces = st.number_input("Tope Seguro Cesantía (UF)", value=params_actuales.get("factor_tope_cesantia", 126.6), step=0.1)
            n_mutual = st.number_input("Mutual Base (%)", value=params_actuales.get("mutual", 0.90), step=0.01)
            
        n_grat = st.number_input("Factor Gratificación (Sueldos Mínimos)", value=params_actuales.get("factor_gratificacion_legal", 4.75), step=0.25)

        if st.form_submit_button("💾 Guardar Nuevos Parámetros"):
            gestor.datos["parametros"]["sueldo_minimo"] = n_sueldo
            gestor.datos["parametros"]["tasa_sis"] = n_sis
            gestor.datos["parametros"]["factor_tope_afp"] = n_tope_afp
            gestor.datos["parametros"]["sanna"] = n_sanna
            gestor.datos["parametros"]["factor_tope_cesantia"] = n_tope_ces
            gestor.datos["parametros"]["mutual"] = n_mutual
            gestor.datos["parametros"]["factor_gratificacion_legal"] = n_grat
            
            gestor.guardar_cambios()
            st.success("¡Parámetros actualizados correctamente!")
            time.sleep(1.5)
            st.rerun()

# --- TAB 5: ADMIN (Solo si es admin) ---
if es_admin:
    with tabs[4]:
        st.header("Panel de Usuarios")
        c_add, c_list = st.columns(2)
        with c_add:
            with st.form("add_user"):
                u = st.text_input("Usuario"); n = st.text_input("Nombre"); p = st.text_input("Clave", type="password")
                if st.form_submit_button("Crear"):
                    ok, msg = admin_tools.agregar_usuario(u, n, p)
                    if ok: st.success(msg)
                    else: st.error(msg)
        with c_list:
            users = admin_tools.cargar_config()['credentials']['usernames']
            st.dataframe(pd.DataFrame([{"User": k, "Nombre": v['name']} for k,v in users.items()]))