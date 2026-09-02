import json
import os
import requests
import pandas as pd
from utils import redondear_excel

class GestorParametros:
    def __init__(self):
        self.archivo_db = "parametros_rrhh.json"
        self.api_url = "https://mindicador.cl/api"
        self.datos_base = {
            "mes_referencia": "",
            "indicadores": {"UF": 36679.00, "UTM": 69542.00},
            "parametros": {
                "sueldo_minimo":553553.0, "factor_tope_afp": 90.0, "factor_tope_cesantia": 135.2,
                "factor_gratificacion_legal": 4.75, "tasa_sis": 1.49, "sanna": 0.03,
                "mutual": 0.9, "tasa_expectativa_vida": 0.9
            }
        }
        self.datos = self.cargar_datos()
        self._actualizar_indicadores_silencioso() # Llamada automática al inicio

    def _actualizar_indicadores_silencioso(self):
        # Actualiza sin mostrar mensajes. Si falla, se queda con los del JSON.
        try:
            resp = requests.get(self.api_url, timeout=3).json()
            self.datos["indicadores"]["UF"] = resp['uf']['valor']
            self.datos["indicadores"]["UTM"] = resp['utm']['valor']
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
        # Esta es la que usa el botón, se queda igual
        try:
            resp = requests.get(self.api_url, timeout=5).json()
            self.datos["indicadores"]["UF"] = resp['uf']['valor']
            self.datos["indicadores"]["UTM"] = resp['utm']['valor']
            self.guardar_cambios()
            return True, "Indicadores actualizados"
        except Exception as e:
            return False, f"Error: {e}"

    def obtener_valor(self, key): return self.datos["parametros"].get(key, 0)
    def obtener_uf(self): return self.datos["indicadores"]["UF"]
    def obtener_utm(self): return self.datos["indicadores"]["UTM"]


class CalculadoraCostos:
    def __init__(self, gestor_params):
        self.params = gestor_params

    def round(self, valor, decimales=0): return redondear_excel(valor, decimales)
    
    # Fórmulas básicas
    def formula_gratificacion(self, sb, tope, b, o): return self.round(min((b+sb+o) * 0.25, tope))
    def formula_base_imponible(self, tot, uf, tope): return self.round(min(tot, tope * uf))
    def Formula_haberes(self, sb, grat, bon, otr): return sb + grat + bon + otr
    def formula_no_haberes(self, col, mov, otr): return col + mov + otr
    def formula_afp(self, imp, tasa, apv): return self.round(imp * (tasa / 100) + apv)
    def formula_salud_legal(self, imp, tasa): return self.round(imp * (tasa / 100))
    def formula_plan_isapre_pesos(self, uf, plan): return self.round(uf * plan)
    def formula_salud_total(self, leg, pac): return max(leg, pac)
    def formula_adicional_salud(self, tot, leg): return max(0, tot - leg)
    def Base_tributable(self, sc, afp, sal, ad, tot, uf, tope): return self.round(tot - sc - afp - min(sal + ad, tope * uf * 7 / 100))
    def formula_seg_cesatia(self, hab, ces, tope, uf): return min(hab*ces, tope*ces*uf)
    def formula_seguro_cesantia(self, pct, base): return self.round(pct*base)
    def Aporte_patronal(self, san, mut, sis, ces): return san + mut + sis + ces

    def formula_impuesto_unico(self, base, utm):
        if base <= 0: return 0
        if base <= (13.5 * utm): return 0
        elif base <= (30 * utm): return self.round((base * 0.04) - (0.54 * utm), 3)
        elif base <= (50 * utm): return self.round((base * 0.08) - (1.74 * utm), 3)
        elif base <= (70 * utm): return self.round((base * 0.135) - (4.49 * utm), 3)
        elif base <= (90 * utm): return self.round((base * 0.23) - (11.14 * utm), 3)
        elif base <= (120 * utm): return self.round((base * 0.304) - (17.80 * utm), 3)
        elif base <= (310 * utm): return self.round((base * 0.35) - (23.32 * utm), 3)
        else: return self.round((base * 0.40) - (38.82 * utm), 3)

    def calcular_costo_empresa(self, sueldo_base, es_indefinido, colacion, movilizacion, otros_no_imp,
                               bonos_imp, otros_imp, admin_input, admin_es_pct, mgmt_input, incluir_bono_anual,
                               afp_tasa, salud_tasa, apv, isapre_uf, otros_costos=0):
        
        utm = self.params.obtener_utm(); uf = self.params.obtener_uf(); sueldo_min = self.params.obtener_valor("sueldo_minimo")
        tope_afp_uf = self.params.obtener_valor("factor_tope_afp"); tope_ces_uf = self.params.obtener_valor("factor_tope_cesantia")
        factor_grati = self.params.obtener_valor("factor_gratificacion_legal")
        
        tope_grati_clp = self.round((sueldo_min * factor_grati) / 12)
        val_grati = self.formula_gratificacion(sueldo_base, tope_grati_clp,bonos_imp,otros_imp)
        
        total_imponible = self.Formula_haberes(sueldo_base, val_grati, bonos_imp, otros_imp)
        total_no_imponible = self.formula_no_haberes(colacion, movilizacion, otros_no_imp)
        total_haberes = total_imponible + total_no_imponible
        
        base_imponible_topada = self.formula_base_imponible(total_imponible, uf, tope_afp_uf)
        
        if es_indefinido: tasa_trab_ces = 0.006; tasa_emp_ces = 0.03
        else: tasa_trab_ces = 0.0; tasa_emp_ces = 0.024
        
        seg_ces_trab = self.formula_seg_cesatia(total_imponible,tasa_trab_ces,tope_ces_uf,uf)
        monto_afp = self.formula_afp(base_imponible_topada, afp_tasa, apv)
        salud_legal = self.formula_salud_legal(base_imponible_topada, salud_tasa)
        plan_pactado = self.formula_plan_isapre_pesos(uf, isapre_uf)
        salud_total = self.formula_salud_total(salud_legal, plan_pactado)
        adic_salud = self.formula_adicional_salud(salud_total, salud_legal)
        
        base_trib = self.Base_tributable(seg_ces_trab, monto_afp, salud_legal, adic_salud, total_imponible, uf, tope_afp_uf)
        imp_unico = self.formula_impuesto_unico(base_trib, utm)
        total_desc = seg_ces_trab + monto_afp + salud_total + imp_unico
        sueldo_liq = self.round(total_haberes - total_desc)

        base_ces = min(total_imponible, tope_ces_uf * uf)
        seg_ces_emp = self.formula_seguro_cesantia(tasa_emp_ces, base_ces)
        
        t_sis = self.params.obtener_valor("tasa_sis")/100; t_mut = self.params.obtener_valor("mutual")/100; t_san = self.params.obtener_valor("sanna")/100
        c_sis = t_sis*base_imponible_topada; c_mut = t_mut*base_imponible_topada; c_san = t_san*base_imponible_topada
        aporte_pat = self.Aporte_patronal(c_san, c_mut, c_sis, seg_ces_emp)
        
        base_tope_calc = min(base_imponible_topada, uf * tope_afp_uf)
        aporte_adic = (0.1/100)*base_tope_calc + (0.9/100)*base_tope_calc # Aporte adicional
        
        prov_vac = ((sueldo_base + colacion + movilizacion + otros_no_imp)/30)*1.75
        prov_ind = total_haberes/12
        seg_sal = uf
        prov_bono = self.round((colacion + val_grati + sueldo_base)*0.05) if incluir_bono_anual else 0

        # COSTO 1: Sin Indemnización
        costo_serv = total_haberes + aporte_pat + aporte_adic + prov_bono + prov_vac + seg_sal
        # COSTO 2: Con Indemnización
        costo_serv2 = total_haberes + aporte_pat + aporte_adic + prov_bono + prov_vac + prov_ind + seg_sal
        
        val_admin = self.round(costo_serv * (admin_input/100)) if admin_es_pct else admin_input
        
        costo_fin = costo_serv + val_admin + mgmt_input + otros_costos
        costo_fin2 = costo_serv2 + val_admin + mgmt_input + otros_costos
        
        return {
            "Sueldo bruto": int(sueldo_base),
            "Colación": colacion,            
            "Movilización": movilizacion,
            "Gratificación": val_grati,
            "Total Imponible": total_imponible,
            "TOTAL HABERES": total_haberes,
            "AFP": monto_afp,
            "Salud Total": salud_total,
            "Seguro Cesantía(Trabajador)": seg_ces_trab,
            "Impuesto Único": imp_unico,
            "Total Descuentos": total_desc,
            "SUELDO LÍQUIDO": sueldo_liq,
            "Aporte Patronal Total": aporte_pat,
            "aporte adicional": aporte_adic,
            "Ley SANNA": c_san, "Mutual": c_mut, "SIS": c_sis, "Seguro Cesantía (Empresa)": seg_ces_emp,
            "Provisión Vacaciones": prov_vac,
            "Provisión Indemnización": prov_ind,
            "Provisión Bono Anual": prov_bono,
            "Seguro Salud (1 UF)": seg_sal,
            "COSTO FINANCIERO SERVICIO sin ind": costo_serv,
            "Costo financiero": costo_serv2,
            "Costo Admin": val_admin,
            "Costo Mgmt": mgmt_input,
            "Otros Costos": otros_costos,
            "Costo Empresa Supplynet": costo_fin,
            "Costo Total(IAS)": costo_fin2
        }

    def encontrar_sueldo_base_iterativo(self, valor_objetivo, es_indefinido, colacion, movilizacion, otros_no_imp,
                               bonos_imp, otros_imp, admin_input, admin_es_pct, mgmt_input, incluir_bono_anual,
                               afp_tasa, salud_tasa, apv, isapre_uf, otros_costos=0, campo_objetivo="SUELDO LÍQUIDO"):
        
        bajo, alto = 0, int(valor_objetivo * 2.5); candidato = 0
        
        # 1. Búsqueda Binaria (Aproximación rápida)
        for _ in range(50):
            medio = (bajo + alto) // 2
            if medio < 0: medio = 0
            
            res = self.calcular_costo_empresa(medio, es_indefinido, colacion, movilizacion, otros_no_imp,
                               bonos_imp, otros_imp, admin_input, admin_es_pct, mgmt_input, incluir_bono_anual,
                               afp_tasa, salud_tasa, apv, isapre_uf, otros_costos)
            
            valor_calculado = res[campo_objetivo]
            
            if valor_calculado == valor_objetivo: return res
            
            if valor_calculado < valor_objetivo: bajo = medio + 1
            else: alto = medio - 1
            candidato = medio
        
        # 2. Ajuste Fino (Paso a paso para precisión exacta)
        mejor_res = None; menor_dif = float('inf')
        rango_busqueda = range(max(0, candidato - 2000), candidato + 2000)
        
        for base in rango_busqueda:
            res = self.calcular_costo_empresa(base, es_indefinido, colacion, movilizacion, otros_no_imp,
                               bonos_imp, otros_imp, admin_input, admin_es_pct, mgmt_input, incluir_bono_anual,
                               afp_tasa, salud_tasa, apv, isapre_uf, otros_costos)
            
            valor_calculado = res[campo_objetivo]
            dif = abs(valor_calculado - valor_objetivo)
            
            if dif < menor_dif:
                menor_dif = dif
                mejor_res = res
            if dif == 0: return res
            
        return mejor_res
        
    def obtener_tabla_impuesto_visual(self):
        utm = self.params.obtener_utm()
        tramos = [
            (1, 0, 13.5, 0.00, 0.00), (2, 13.5, 30.0, 0.04, 0.54),
            (3, 30.0, 50.0, 0.08, 1.74), (4, 50.0, 70.0, 0.135, 4.49),
            (5, 70.0, 90.0, 0.23, 11.14), (6, 90.0, 120.0, 0.304, 17.80),
            (7, 120.0, 310.0, 0.35, 23.32), (8, 310.0, None, 0.40, 38.82)
        ]
        data = []
        for tramo, d, h, f, r in tramos:
            desde = f"${redondear_excel(d * utm):,.0f}"
            hasta = f"${redondear_excel(h * utm):,.0f}" if h else "Y MÁS"
            rebaja = f"${redondear_excel(r * utm):,.0f}"
            data.append({"Tramo": tramo, "Factor": f"{f:.3f}", "Rebaja (UTM)": f"{r:.2f}", "Desde": desde, "Hasta": hasta, "Rebaja ($)": rebaja})
        return pd.DataFrame(data)