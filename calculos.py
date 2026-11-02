import json
import os
import requests
import pandas as pd
import datetime
from utils import redondear_excel

class GestorParametros:
    def __init__(self):
        self.archivo_db = "parametros_rrhh.json"
        self.api_url = "https://mindicador.cl/api"
        self.datos_base = {
            "mes_referencia": "",
            "indicadores": {"UF": 36679.00, "UTM": 69542.00},
            "parametros": {
                "sueldo_minimo": 553553.0, "factor_tope_afp": 90.0, "factor_tope_cesantia": 135.2,
                "factor_gratificacion_legal": 4.75, "tasa_sis": 1.78, "sanna": 0.03,
                "mutual": 0.9, "tasa_expectativa_vida": 0.0
            }
        }
        self.datos = self.cargar_datos()
        
        # Variables independientes (Fallback rápido al JSON)
        self.uf_inicio_mes = self.datos["indicadores"]["UF"]
        self.utm_inicio_mes = self.datos["indicadores"]["UTM"]
        
        self._actualizar_indicadores_silencioso()

    def _actualizar_indicadores_silencioso(self):
        try:
            # 1. Indicadores del DÍA (Siempre disponibles en el endpoint raíz)
            resp_hoy = requests.get(self.api_url, timeout=3).json()
            uf_actual = resp_hoy['uf']['valor']
            utm_actual = resp_hoy['utm']['valor']
            
            self.datos["indicadores"]["UF"] = uf_actual
            self.datos["indicadores"]["UTM"] = utm_actual
            
            # 2. Indicadores de INICIO DE MES
            hoy = datetime.date.today()
            fecha_inicio_mes = f"01-{hoy.strftime('%m-%Y')}"
            
            resp_inicio = requests.get(f"{self.api_url}/uf/{fecha_inicio_mes}", timeout=3).json()
            
            # Si la API tiene el día 1 (no es feriado/vacío), lo usa. Si no, usa el valor actual.
            if resp_inicio.get("serie") and len(resp_inicio["serie"]) > 0:
                self.uf_inicio_mes = resp_inicio["serie"][0]["valor"]
            else:
                self.uf_inicio_mes = uf_actual
                
            # La UTM es mensual, el valor de 'hoy' es exactamente el mismo de inicio de mes
            self.utm_inicio_mes = utm_actual
            
        except:
            pass

    def cargar_datos(self):
        if os.path.exists(self.archivo_db):
            try:
                with open(self.archivo_db, 'r') as f: return json.load(f)
            except: return self.datos_base
        return self.datos_base

    def guardar_cambios(self):
        with open(self.archivo_db, 'w') as f: json.dump(self.datos, f, indent=4)

    def obtener_indicadores_online(self):
        try:
            resp_hoy = requests.get(self.api_url, timeout=5).json()
            uf_actual = resp_hoy['uf']['valor']
            utm_actual = resp_hoy['utm']['valor']
            
            self.datos["indicadores"]["UF"] = uf_actual
            self.datos["indicadores"]["UTM"] = utm_actual
            
            hoy = datetime.date.today()
            fecha_inicio_mes = f"01-{hoy.strftime('%m-%Y')}"
            resp_inicio = requests.get(f"{self.api_url}/uf/{fecha_inicio_mes}", timeout=5).json()
            
            if resp_inicio.get("serie") and len(resp_inicio["serie"]) > 0:
                self.uf_inicio_mes = resp_inicio["serie"][0]["valor"]
            else:
                self.uf_inicio_mes = uf_actual
                
            self.utm_inicio_mes = utm_actual
                
            self.guardar_cambios()
            return True, "Indicadores actualizados"
        except Exception as e:
            return False, f"Error: {e}"

    def obtener_valor(self, key): return self.datos["parametros"].get(key, 0)
    def obtener_uf(self): return self.datos["indicadores"]["UF"]
    def obtener_utm(self): return self.datos["indicadores"]["UTM"]
    def obtener_uf_inicio_mes(self): return self.uf_inicio_mes
    def obtener_utm_inicio_mes(self): return self.utm_inicio_mes


class CalculadoraCostos:
    def __init__(self, gestor_params):
        self.params = gestor_params

    def round(self, valor, decimales=0): return redondear_excel(valor, decimales)

    def formula_impuesto_unico(self, base, utm):
        base = self.round(base, 0)
        if base <= 0: return 0
        if base <= (13.5 * utm): return 0
        elif base <= (30 * utm): return self.round((base * 0.04) - self.round(0.54 * utm, 2), 0)
        elif base <= (50 * utm): return self.round((base * 0.08) - self.round(1.74 * utm, 2), 0)
        elif base <= (70 * utm): return self.round((base * 0.135) - self.round(4.49 * utm, 2), 0)
        elif base <= (90 * utm): return self.round((base * 0.23) - self.round(11.14 * utm, 2), 0)
        elif base <= (120 * utm): return self.round((base * 0.304) - self.round(17.80 * utm, 2), 0)
        elif base <= (310 * utm): return self.round((base * 0.35) - self.round(23.32 * utm, 2), 0)
        else: return self.round((base * 0.40) - self.round(38.82 * utm, 2), 0)

    # ================= MÉTODOS MODULARES DE CÁLCULO =================
    
    def _calcular_haberes(self, sueldo_base, colacion, movilizacion, otros_no_imp, bonos_imp, otros_imp):
        sueldo_min = self.params.obtener_valor("sueldo_minimo")
        factor_grati = self.params.obtener_valor("factor_gratificacion_legal")
        
        tope_grati_clp = self.round((sueldo_min * factor_grati) / 12)
        val_grati = self.round(min((sueldo_base + bonos_imp + otros_imp) * 0.25, tope_grati_clp))
        
        total_imponible = sueldo_base + val_grati + bonos_imp + otros_imp
        total_no_imponible = colacion + movilizacion + otros_no_imp
        total_haberes = total_imponible + total_no_imponible
        
        return val_grati, total_imponible, total_no_imponible, total_haberes

    def _calcular_descuentos_trabajador(self, total_imponible, uf_dia, es_indefinido, afp_tasa, salud_tasa, apv, isapre_uf):
        tope_afp_uf = self.params.obtener_valor("factor_tope_afp")
        tope_ces_uf = self.params.obtener_valor("factor_tope_cesantia")
        utm_inicio_mes = self.params.obtener_utm_inicio_mes()
        
        base_imponible_topada = self.round(min(total_imponible, tope_afp_uf * uf_dia))
        
        tasa_trab_ces = 0.006 if es_indefinido else 0.0
        seg_ces_trab = self.round(min(total_imponible * tasa_trab_ces, tope_ces_uf * uf_dia * tasa_trab_ces))
        
        monto_afp = self.round(base_imponible_topada * (afp_tasa / 100) + apv)
        salud_legal = self.round(base_imponible_topada * (salud_tasa / 100))
        plan_pactado = self.round(uf_dia * isapre_uf)
        salud_total = max(salud_legal, plan_pactado)
        adic_salud = max(0, salud_total - salud_legal)
        
        # Base Tributable (restando tope 7% salud)
        base_trib = self.round(total_imponible - seg_ces_trab - monto_afp - min(salud_total, tope_afp_uf * uf_dia * 0.07))
        imp_unico = self.formula_impuesto_unico(base_trib, utm_inicio_mes)
        
        total_desc = seg_ces_trab + monto_afp + salud_total + imp_unico
        
        return base_imponible_topada, seg_ces_trab, monto_afp, salud_total, imp_unico, total_desc

    def _calcular_aportes_empresa(self, total_imponible, base_imponible_topada, uf_dia, es_indefinido):
        tope_ces_uf = self.params.obtener_valor("factor_tope_cesantia")
        tope_afp_uf = self.params.obtener_valor("factor_tope_afp")
        
        tasa_emp_ces = 0.024 if es_indefinido else 0.03
        base_ces = min(total_imponible, tope_ces_uf * uf_dia)
        seg_ces_emp = self.round(tasa_emp_ces * base_ces)
        
        t_sis = self.params.obtener_valor("tasa_sis") / 100
        t_mut = self.params.obtener_valor("mutual") / 100
        t_san = self.params.obtener_valor("sanna") / 100
        
        c_sis = t_sis * base_imponible_topada
        c_mut = t_mut * base_imponible_topada
        c_san = t_san * base_imponible_topada
        
        aporte_pat = c_san + c_mut + c_sis + seg_ces_emp
        
        base_tope_calc = min(base_imponible_topada, uf_dia * tope_afp_uf)
        aporte_adic = (0.1/100) * base_tope_calc + (0.9/100) * base_tope_calc
        
        return c_san, c_mut, c_sis, seg_ces_emp, aporte_pat, aporte_adic

    def _calcular_provisiones(self, sueldo_base, val_grati, colacion, total_imponible, uf_dia, es_indefinido, incluir_bono_anual):
        tope_afp_uf = self.params.obtener_valor("factor_tope_afp")
        
        # 1. Vacaciones: Solo base y gratificación (sin colación ni movilización)
        prov_vac = ((sueldo_base + val_grati) / 30) * 1.75
        
        # 2. Indemnización (IAS): Topada a 90 UF y eliminando duplicidad del 1.6% AFC
        base_indemnizacion = min(total_imponible, tope_afp_uf * uf_dia)
        prov_ind_bruta = base_indemnizacion / 12
        
        descuento_afc_ias = (base_indemnizacion * 0.016) if es_indefinido else 0
        prov_ind = max(0, prov_ind_bruta - descuento_afc_ias) if es_indefinido else 0
        
        seg_sal = self.round(uf_dia * 1.41)
        prov_bono = self.round((colacion + val_grati + sueldo_base) * 0.05) if incluir_bono_anual else 0
        
        return prov_vac, prov_ind, prov_bono, seg_sal

    # ================= ORQUESTADOR PRINCIPAL =================

    def calcular_costo_empresa(self, sueldo_base, es_indefinido, colacion, movilizacion, otros_no_imp,
                               bonos_imp, otros_imp, admin_input, admin_es_pct, mgmt_input, incluir_bono_anual,
                               afp_tasa, salud_tasa, apv, isapre_uf):
        
        uf_dia = self.params.obtener_uf()
        
        val_grati, total_imponible, total_no_imponible, total_haberes = self._calcular_haberes(
            sueldo_base, colacion, movilizacion, otros_no_imp, bonos_imp, otros_imp
        )
        
        base_imponible_topada, seg_ces_trab, monto_afp, salud_total, imp_unico, total_desc = self._calcular_descuentos_trabajador(
            total_imponible, uf_dia, es_indefinido, afp_tasa, salud_tasa, apv, isapre_uf
        )
        
        sueldo_liq = total_haberes - total_desc
        
        c_san, c_mut, c_sis, seg_ces_emp, aporte_pat, aporte_adic = self._calcular_aportes_empresa(
            total_imponible, base_imponible_topada, uf_dia, es_indefinido
        )
        
        prov_vac, prov_ind, prov_bono, seg_sal = self._calcular_provisiones(
            sueldo_base, val_grati, colacion, total_imponible, uf_dia, es_indefinido, incluir_bono_anual
        )
        
        # COSTO 1: Sin Indemnización
        costo_serv = total_haberes + aporte_pat + aporte_adic + prov_bono + prov_vac + seg_sal
        # COSTO 2: Con Indemnización
        costo_serv2 = total_haberes + aporte_pat + aporte_adic + prov_bono + prov_vac + prov_ind + seg_sal
        
        val_admin = self.round(costo_serv * (admin_input/100)) if admin_es_pct else admin_input
        
        costo_fin = costo_serv + val_admin + mgmt_input
        costo_fin2 = costo_serv2 + val_admin + mgmt_input
        
        return {
            "Sueldo bruto": int(sueldo_base),
            "Colación": colacion,
            "Movilización": movilizacion,
            "Gratificación": val_grati,
            "Total Imponible": total_imponible,
            "TOTAL HABERES": total_haberes,
            "AFP": monto_afp,
            "Salud Total": salud_total,
            "Seguro Cesantía": seg_ces_trab,
            "Impuesto Único": imp_unico,
            "Total Descuentos": total_desc,
            "SUELDO LÍQUIDO": sueldo_liq,
            "Renta líquida": sueldo_liq, 
            "Aporte Patronal Total": aporte_pat,
            "Ley SANNA": c_san, "Mutual": c_mut, "SIS": c_sis, "Seguro Cesantía (Empresa)": seg_ces_emp,
            "Provisión Vacaciones": prov_vac,
            "Provisión Indemnización": prov_ind,
            "Provisión Bono Anual": prov_bono,
            "Seguro Salud (1.41 UF)": seg_sal,
            "COSTO FINANCIERO SERVICIO sin ind": costo_serv,
            "Costo financiero": costo_serv2,
            "Costo Admin": val_admin,
            "Costo Mgmt": mgmt_input,
            "COSTO FINANCIERO TOTAL sin ind": costo_fin,
            "COSTO FINANCIERO TOTAL": costo_fin2
        }

    def encontrar_sueldo_base_iterativo(self, valor_objetivo, es_indefinido, colacion, movilizacion, otros_no_imp,
                               bonos_imp, otros_imp, admin_input, admin_es_pct, mgmt_input, incluir_bono_anual,
                               afp_tasa, salud_tasa, apv, isapre_uf, campo_objetivo="SUELDO LÍQUIDO"):
        
        bajo, alto = 0, int(valor_objetivo * 2.5); candidato = 0
        
        for _ in range(50):
            medio = (bajo + alto) // 2
            if medio < 0: medio = 0
            
            res = self.calcular_costo_empresa(medio, es_indefinido, colacion, movilizacion, otros_no_imp,
                               bonos_imp, otros_imp, admin_input, admin_es_pct, mgmt_input, incluir_bono_anual,
                               afp_tasa, salud_tasa, apv, isapre_uf)
            
            valor_calculado = res[campo_objetivo]
            
            if valor_calculado == valor_objetivo: return res
            
            if valor_calculado < valor_objetivo: bajo = medio + 1
            else: alto = medio - 1
            candidato = medio
        
        mejor_res = None; menor_dif = float('inf')
        rango_busqueda = range(max(0, candidato - 2000), candidato + 2000)
        
        for base in rango_busqueda:
            res = self.calcular_costo_empresa(base, es_indefinido, colacion, movilizacion, otros_no_imp,
                               bonos_imp, otros_imp, admin_input, admin_es_pct, mgmt_input, incluir_bono_anual,
                               afp_tasa, salud_tasa, apv, isapre_uf)
            
            valor_calculado = res[campo_objetivo]
            dif = abs(valor_calculado - valor_objetivo)
            
            if dif < menor_dif:
                menor_dif = dif
                mejor_res = res
            if dif == 0: return res
            
        return mejor_res
        
    def obtener_tabla_impuesto_visual(self):
        utm_inicio_mes = self.params.obtener_utm_inicio_mes()
        tramos = [
            (1, 0, 13.5, 0.00, 0.00), (2, 13.5, 30.0, 0.04, 0.54),
            (3, 30.0, 50.0, 0.08, 1.74), (4, 50.0, 70.0, 0.135, 4.49),
            (5, 70.0, 90.0, 0.23, 11.14), (6, 90.0, 120.0, 0.304, 17.80),
            (7, 120.0, 310.0, 0.35, 23.32), (8, 310.0, None, 0.40, 38.82)
        ]
        data = []
        for tramo, d, h, f, r in tramos:
            desde = f"${redondear_excel(d * utm_inicio_mes):,.0f}"
            hasta = f"${redondear_excel(h * utm_inicio_mes):,.0f}" if h else "Y MÁS"
            rebaja = f"${redondear_excel(r * utm_inicio_mes):,.0f}"
            data.append({"Tramo": tramo, "Factor": f"{f:.3f}", "Rebaja (UTM)": f"{r:.2f}", "Desde": desde, "Hasta": hasta, "Rebaja ($)": rebaja})
        return pd.DataFrame(data)