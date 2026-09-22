import streamlit as st
from supabase import create_client
import pandas as pd
import plotly.express as px
from datetime import datetime, date, timedelta
import calendar
import time

st.set_page_config(page_title="Finanzas Pro", page_icon="📈", layout="wide")

# --- CONEXIÓN A SUPABASE ---
@st.cache_resource
def init_connection():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

try:
    supabase = init_connection()
except Exception as e:
    st.error("Error conectando a Supabase. Verificá tus secretos en Streamlit Cloud.")
    st.stop()

# --- FUNCIONES DE UTILIDAD ---
def primer_viernes_mes_siguiente(fecha_base=None):
    if fecha_base is None:
        fecha_base = date.today()
    if fecha_base.month == 12:
        year = fecha_base.year + 1
        month = 1
    else:
        year = fecha_base.year
        month = fecha_base.month + 1
    c = calendar.monthcalendar(year, month)
    for week in c:
        if week[calendar.FRIDAY] != 0:
            return date(year, month, week[calendar.FRIDAY])

def ultimo_domingo():
    hoy = date.today()
    offset = (hoy.weekday() - 6) % 7
    return hoy - timedelta(days=offset)

def recargar_app(mensaje="✅ Acción completada"):
    st.toast(mensaje, icon="✅")
    time.sleep(1.2)
    st.rerun()

# --- CARGA ROBUSTA DE DATOS (CON REINTENTOS) ---
def cargar_tabla(nombre_tabla, order_by="id", desc=False):
    for intento in range(3):
        try:
            res = supabase.table(nombre_tabla).select("*").order(order_by, desc=desc).execute()
            return pd.DataFrame(res.data) if res.data else pd.DataFrame()
        except Exception:
            time.sleep(0.5)
    return pd.DataFrame()

df_transacciones = cargar_tabla("transacciones", order_by="fecha", desc=True)
df_categorias = cargar_tabla("categorias")
df_partidos_aaa = cargar_tabla("partidos_aaa", order_by="fecha", desc=True)
df_metas = cargar_tabla("metas_ahorro")
df_vencimientos = cargar_tabla("vencimientos", order_by="fecha_vencimiento")
df_deudas = cargar_tabla("deudas")

# --- PROCESAMIENTO INICIAL CON RESILIENCIA ---
if not df_transacciones.empty and 'tipo' in df_transacciones.columns and 'fecha' in df_transacciones.columns:
    df_transacciones['fecha'] = pd.to_datetime(df_transacciones['fecha']).dt.date
    df_transacciones['mes_año'] = pd.to_datetime(df_transacciones['fecha']).dt.strftime('%Y-%m')
    df_transacciones['tipo_general'] = df_transacciones['tipo'].apply(lambda x: 'Ingreso' if 'Ingreso' in str(x) else 'Gasto')
else:
    df_transacciones = pd.DataFrame(columns=['id', 'fecha', 'tipo', 'categoria', 'monto', 'descripcion', 'mes_año', 'tipo_general'])

# --- ESTRUCTURA DE PESTAÑAS ---
st.title("📈 Mi Ecosistema Financiero Pro")
st.caption("💡 *Todos los balances e ingresos se contabilizan estrictamente por su **Fecha de Cobro/Pago Real** (Criterio de Caja).*")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Dashboards", 
    "➕ Carga Rápida", 
    "💼 Automatizaciones", 
    "🎯 Metas & Vencimientos", 
    "📝 Historial & Excel", 
    "⚙️ Configuración"
])

# ==========================================
# PESTAÑA 1: DASHBOARDS Y SIMULADOR
# ==========================================
with tab1:
    if df_transacciones.empty:
        st.info("No hay datos registrados aún o no se han cargado movimientos.")
    else:
        st.header("📊 Análisis Mensual (Por Fecha de Cobro)")
        meses_disponibles = sorted(df_transacciones['mes_año'].dropna().unique(), reverse=True)
        if meses_disponibles:
            mes_seleccionado = st.selectbox("📅 Seleccionar Mes", meses_disponibles, key="tab1_mes_sel")
            df_mes = df_transacciones[df_transacciones['mes_año'] == mes_seleccionado]
            
            ingresos = df_mes[df_mes['tipo_general'] == 'Ingreso']['monto'].sum()
            gastos = df_mes[df_mes['tipo_general'] == 'Gasto']['monto'].sum()
            ahorro = ingresos - gastos
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Ingresos Cobrados", f"${ingresos:,.2f}")
            col2.metric("Gastos Pagados", f"${gastos:,.2f}")
            col3.metric("Ahorro / Ganancia Neta", f"${ahorro:,.2f}", delta=f"{(ahorro/ingresos)*100:.1f}% del ingreso" if ingresos > 0 else "")
            
            st.markdown("---")
            
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                st.subheader("Ingresos vs Gastos (Evolución de Caja)")
                df_hist = df_transacciones.groupby(['mes_año', 'tipo_general'])['monto'].sum().reset_index()
                fig_hist = px.bar(df_hist, x='mes_año', y='monto', color='tipo_general', barmode='group',
                                  color_discrete_map={'Ingreso': '#2ecc71', 'Gasto': '#e74c3c'})
                st.plotly_chart(fig_hist, use_container_width=True)
                
            with col_g2:
                st.subheader(f"Desglose de Gastos ({mes_seleccionado})")
                df_gastos_mes = df_mes[df_mes['tipo_general'] == 'Gasto']
                if not df_gastos_mes.empty:
                    fig_gastos = px.pie(df_gastos_mes, names='categoria', values='monto', hole=0.4)
                    st.plotly_chart(fig_gastos, use_container_width=True)
                else:
                    st.write("No hay gastos registrados en este mes.")
                    
            st.subheader(f"Desglose de Ingresos Cobrados ({mes_seleccionado})")
            df_ingresos_mes = df_mes[df_mes['tipo_general'] == 'Ingreso']
            if not df_ingresos_mes.empty:
                fig_ingresos = px.pie(df_ingresos_mes, names='categoria', values='monto', hole=0.4)
                st.plotly_chart(fig_ingresos, use_container_width=True)

            st.markdown("---")
            st.header("🧮 Simulador de Rendimiento Diario (Interés Compuesto)")
            col_s1, col_s2, col_s3 = st.columns(3)
            with col_s1:
                cap_inicial = st.number_input("Capital a Invertir ($)", value=float(ahorro if 'ahorro' in locals() and ahorro > 0 else 100000), step=10000.0, key="tab1_cap_inicial")
            with col_s2:
                tna = st.number_input("TNA Actual Billetera (%)", value=38.0, step=1.0, key="tab1_tna")
            with col_s3:
                dias_inversion = st.number_input("Días de inversión", value=30, min_value=1, key="tab1_dias_inv")
                
            tasa_diaria = (tna / 100) / 365
            cap_final = cap_inicial * ((1 + tasa_diaria) ** dias_inversion)
            ganancia = cap_final - cap_inicial
            st.success(f"💸 **Dinero total al final:** ${cap_final:,.2f} (Ganaste **${ganancia:,.2f}** sin hacer nada)")

# ==========================================
# PESTAÑA 2: CARGA RÁPIDA
# ==========================================
with tab2:
    st.header("📝 Movimiento Único")
    tipo_mov = st.selectbox("Tipo", ["Ingreso Variable", "Ingreso Fijo", "Gasto Variable", "Gasto Fijo"], key="tab2_tipo_mov")
    tipo_general = "Ingreso" if "Ingreso" in tipo_mov else "Gasto"
    opciones_cat = df_categorias[df_categorias['tipo_general'] == tipo_general]['nombre'].tolist() if not df_categorias.empty and 'tipo_general' in df_categorias.columns else ["Sin categorías"]
    
    cat_mov = st.selectbox("Categoría", opciones_cat, key="tab2_cat_mov")
    monto_mov = st.number_input("Monto ($)", min_value=0.0, step=1000.0, key="tab2_monto_mov")
    fecha_mov = st.date_input("Fecha de Cobro / Pago Efectivo", datetime.today(), key="tab2_fecha_mov")
    desc_mov = st.text_input("Descripción (Ej: Nafta, Coto...)", key="tab2_desc_mov")
    
    if st.button("Guardar Movimiento", type="primary", key="tab2_btn_guardar"):
        if monto_mov > 0:
            try:
                nuevo = {"fecha": str(fecha_mov), "tipo": tipo_mov, "categoria": cat_mov, "monto": monto_mov, "descripcion": desc_mov}
                supabase.table("transacciones").insert(nuevo).execute()
                recargar_app("Movimiento guardado.")
            except Exception as e:
                st.error("Error de conexión al guardar el movimiento. Intentá de nuevo.")
        else:
            st.warning("El monto debe ser mayor a 0.")

# ==========================================
# PESTAÑA 3: AUTOMATIZACIONES LABORALES
# ==========================================
with tab3:
    st.header("💼 Centros de Ingreso Automáticos")
    modo_trabajo = st.radio("Seleccioná tu actividad:", ["⚽ Arbitraje: AAA (Sábados/Mensual)", "⚽ Arbitraje: Argenliga (Domingos/Diario)", "🩺 Consultorio Méd. (Semanal)"], horizontal=True, key="tab3_modo_trabajo")
    
    # ------------------------------------
    # 1. ARBITRAJE AAA
    # ------------------------------------
    if "AAA" in modo_trabajo:
        col_aaa1, col_aaa2 = st.columns([1, 1.5])
        with col_aaa1:
            st.subheader("1. Registrar Partido Arbitrado")
            st.caption("Cargá el partido en la lista de pendientes (no impacta en ingresos hasta liquidarlo).")
            f_partido_aaa = st.date_input("Fecha del Partido", value=datetime.today(), key="tab3_f_partido_aaa")
            m_partido_aaa = st.number_input("Honorario del partido ($)", min_value=0.0, step=1000.0, key="tab3_m_partido_aaa")
            d_partido_aaa = st.text_input("Detalle (Ej: Cat. Juveniles Cancha 2)", key="tab3_d_partido_aaa")
            
            if st.button("Guardar Partido", key="tab3_btn_guardar_aaa"):
                if m_partido_aaa > 0:
                    try:
                        supabase.table("partidos_aaa").insert({
                            "fecha": str(f_partido_aaa), "detalle": d_partido_aaa, "monto": m_partido_aaa, "estado": "Pendiente"
                        }).execute()
                        recargar_app("Partido guardado en pendientes.")
                    except Exception as e:
                        st.error("Error de red al guardar el partido. Intentá nuevamente.")
                else:
                    st.warning("El monto debe ser mayor a 0.")
                
        with col_aaa2:
            st.subheader("2. Liquidación Mensual AAA (Cobro Efectivo)")
            if not df_partidos_aaa.empty and 'estado' in df_partidos_aaa.columns:
                df_pend = df_partidos_aaa[df_partidos_aaa['estado'] == 'Pendiente'].copy()
                if not df_pend.empty:
                    st.write("Seleccioná los partidos que entran en esta liquidación:")
                    df_pend['Incluir'] = True
                    df_pend = df_pend[['Incluir', 'id', 'fecha', 'detalle', 'monto']]
                    editado = st.data_editor(
                        df_pend,
                        column_config={"Incluir": st.column_config.CheckboxColumn("Cobrar ahora", default=True), "id": None},
                        hide_index=True, use_container_width=True, key="tab3_editor_aaa"
                    )
                    seleccionados = editado[editado['Incluir'] == True]
                    bruto_calculado = seleccionados['monto'].sum()
                    neto_calculado = bruto_calculado - 15000
                    
                    col_tot1, col_tot2, col_tot3 = st.columns(3)
                    col_tot1.metric("Bruto", f"${bruto_calculado:,.0f}")
                    col_tot2.metric("Cuota AAA", "-$15,000")
                    col_tot3.metric("NETO A COBRAR", f"${neto_calculado:,.0f}")
                    
                    fecha_proyectada = primer_viernes_mes_siguiente(date.today())
                    fecha_cobro_final = st.date_input("📅 Fecha de Cobro Real (Cuándo ingresa el dinero)", value=fecha_proyectada, key="tab3_f_cobro_aaa")
                    
                    st.info(f"💡 Esta ganancia de **${neto_calculado:,.0f}** se contabilizará en el Dashboard de **{fecha_cobro_final.strftime('%Y-%m')}** (Mes de cobro).")
                    
                    if st.button("Generar Liquidación Mensual AAA", type="primary", key="tab3_btn_liq_aaa"):
                        if neto_calculado > 0:
                            try:
                                supabase.table("transacciones").insert({
                                    "fecha": str(fecha_cobro_final), "tipo": "Ingreso Variable", "categoria": "Arbitraje",
                                    "monto": neto_calculado, "descripcion": f"Liquidación AAA ({len(seleccionados)} partidos - Cuota descontada)"
                                }).execute()
                                for p_id in seleccionados['id'].tolist():
                                    supabase.table("partidos_aaa").update({"estado": "Cobrado"}).eq("id", p_id).execute()
                                recargar_app(f"Liquidación agendada exitosamente para el {fecha_cobro_final}.")
                            except Exception as e:
                                st.error("Error al procesar la liquidación en Supabase. Intentá de nuevo.")
                        else:
                            st.warning("El neto calculado debe ser mayor a 0.")
                else:
                    st.info("No tenés partidos pendientes de cobrar.")
            else:
                st.info("No hay registro de partidos guardados.")

    # ------------------------------------
    # 2. ARBITRAJE ARGENLIGA
    # ------------------------------------
    elif "Argenliga" in modo_trabajo:
        st.subheader("Cobro Inmediato Argenliga (con Retención 5%)")
        fecha_arg = st.date_input("Fecha de cobro (Día del partido)", value=ultimo_domingo(), key="tab3_f_arg")
        monto_mano = st.number_input("Total cobrado en mano ($)", min_value=0.0, step=1000.0, key="tab3_monto_mano_arg")
        
        descuento_arg = monto_mano * 0.05
        neto_arg = monto_mano - descuento_arg
        
        col_arg1, col_arg2 = st.columns(2)
        col_arg1.warning(f"📉 **Retención (5%):** -${descuento_arg:,.2f}")
        col_arg2.success(f"💰 **Neto Real a Bolsillo:** ${neto_arg:,.2f}")
        
        desc_arg = st.text_input("Nota (Opcional)", placeholder="Ej: 2 partidos cancha 3", key="tab3_desc_arg")
        
        if st.button("Registrar Argenliga", type="primary", key="tab3_btn_guardar_arg"):
            if neto_arg > 0:
                try:
                    supabase.table("transacciones").insert({
                        "fecha": str(fecha_arg), "tipo": "Ingreso Variable", "categoria": "Arbitraje",
                        "monto": neto_arg, "descripcion": f"Argenliga: {desc_arg} (Mano: {monto_mano} - 5% retención)"
                    }).execute()
                    recargar_app("Ingreso Argenliga registrado correctamente.")
                except Exception as e:
                    st.error("Error de conexión al registrar Argenliga.")
            else:
                st.warning("El monto ingresado debe ser mayor a 0.")

    # ------------------------------------
    # 3. CONSULTORIO
    # ------------------------------------
    elif "Consultorio" in modo_trabajo:
        st.subheader("Generador de Turnos Consultorio")
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            c_mes = st.number_input("Mes de Trabajo", min_value=1, max_value=12, value=datetime.today().month, key="tab3_c_mes")
            c_anio = st.number_input("Año de Trabajo", min_value=2024, value=datetime.today().year, key="tab3_c_anio")
            c_monto = st.number_input("Pago por día normal ($)", value=50000.0, step=1000.0, key="tab3_c_monto")
        
        with col_c2:
            st.write("**¿Cuándo cobrás esta plata?**")
            tipo_cobro_cons = st.radio(
                "Modalidad de Cobro:",
                ["Cobro al mes siguiente (Ej: 1er día del mes sig.)", "Cobro el mismo día trabajado", "Fecha de cobro personalizada"],
                index=0, key="tab3_tipo_cobro_cons"
            )
            
            if "mes siguiente" in tipo_cobro_cons:
                f_default_cobro = date(c_anio + 1, 1, 1) if c_mes == 12 else date(c_anio, c_mes + 1, 1)
            elif "personalizada" in tipo_cobro_cons:
                f_default_cobro = st.date_input("Fecha de cobro fija", value=datetime.today(), key="tab3_f_cobro_cons_pers")
            else:
                f_default_cobro = None

        if st.button("🔍 Generar Planilla de Turnos", key="tab3_btn_gen_cons"):
            cal = calendar.monthcalendar(c_anio, c_mes)
            turnos = []
            for semana in cal:
                for i, dia in enumerate(semana):
                    if dia != 0 and i in [1, 4]:  # Martes (1) y Viernes (4)
                        f_trabajo = f"{c_anio}-{c_mes:02d}-{dia:02d}"
                        f_cobro = str(f_default_cobro) if f_default_cobro else f_trabajo
                        turnos.append({
                            "Fecha Trabajo": f_trabajo,
                            "Fecha Cobro": f_cobro,
                            "Categoría": "Consultorio", 
                            "Monto": float(c_monto), 
                            "Descripción": "Día laboral"
                        })
            if turnos:
                st.session_state['turnos_cons'] = pd.DataFrame(turnos)

        if 'turnos_cons' in st.session_state:
            st.info("💡 Podés modificar la columna **'Fecha Cobro'** individualmente si cobrás algún turno en un día distinto.")
            df_editado = st.data_editor(
                st.session_state['turnos_cons'],
                column_config={
                    "Fecha Trabajo": st.column_config.TextColumn("Día Trabajado", disabled=True),
                    "Fecha Cobro": st.column_config.TextColumn("Fecha de Cobro Real"),
                    "Monto": st.column_config.NumberColumn("Monto ($)", min_value=0.0)
                },
                num_rows="dynamic", use_container_width=True, key="tab3_editor_cons"
            )
            
            if st.button("💾 Guardar Planilla Mensual", type="primary", key="tab3_btn_guardar_cons"):
                try:
                    datos_a_insertar = []
                    for _, row in df_editado.iterrows():
                        datos_a_insertar.append({
                            "fecha": str(row['Fecha Cobro']), 
                            "tipo": "Ingreso Variable", 
                            "categoria": row['Categoría'],
                            "monto": row['Monto'], 
                            "descripcion": f"{row['Descripción']} (Trabajado: {row['Fecha Trabajo']})"
                        })
                    if datos_a_insertar:
                        supabase.table("transacciones").insert(datos_a_insertar).execute()
                        del st.session_state['turnos_cons']
                        recargar_app("Turnos del consultorio guardados con sus fechas de cobro real.")
                except Exception as e:
                    st.error("Error al guardar la planilla de turnos en Supabase.")

# ==========================================
# PESTAÑA 4: METAS, VENCIMIENTOS Y DEUDAS
# ==========================================
with tab4:
    st.header("🎯 Sobres de Ahorro, Vencimientos y Cuentas Corrientes")
    sub_t4 = st.radio("Sección:", ["Sobres / Metas", "Vencimientos (Corsa / Servicios)", "Me deben / Debo"], horizontal=True, key="tab4_sub_section")
    
    if sub_t4 == "Sobres / Metas":
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.subheader("Crear / Actualizar Sobres")
            n_meta = st.text_input("Nombre de la meta (Ej: Facultad 2027, Mantenimiento Corsa)", key="tab4_n_meta")
            obj_meta = st.number_input("Monto Objetivo ($)", min_value=1000.0, step=10000.0, key="tab4_obj_meta")
            act_meta = st.number_input("Monto Actual Ahorrado ($)", min_value=0.0, step=1000.0, key="tab4_act_meta")
            if st.button("Guardar Meta", key="tab4_btn_guardar_meta"):
                if n_meta:
                    try:
                        supabase.table("metas_ahorro").insert({"nombre": n_meta, "monto_objetivo": obj_meta, "monto_actual": act_meta}).execute()
                        recargar_app("Meta creada con éxito.")
                    except Exception as e:
                        st.error("Error al guardar la meta.")
                else:
                    st.warning("Ingresá un nombre para la meta.")
                
        with col_m2:
            st.subheader("Progreso de tus Metas")
            if not df_metas.empty and 'monto_actual' in df_metas.columns:
                for _, row in df_metas.iterrows():
                    porc = min(row['monto_actual'] / row['monto_objetivo'], 1.0) if row['monto_objetivo'] > 0 else 0
                    st.write(f"**{row['nombre']}**: ${row['monto_actual']:,.0f} / ${row['monto_objetivo']:,.0f}")
                    st.progress(porc)
            else:
                st.info("No hay metas creadas.")
                
    elif sub_t4 == "Vencimientos (Corsa / Servicios)":
        col_v1, col_v2 = st.columns(2)
        with col_v1:
            st.subheader("Nuevo Vencimiento")
            con_v = st.text_input("Concepto (Ej: Patente Corsa, VTV, Seguro)", key="tab4_con_v")
            f_v = st.date_input("Fecha de Vencimiento", value=datetime.today(), key="tab4_f_v")
            m_v = st.number_input("Monto estimado ($)", min_value=0.0, step=1000.0, key="tab4_m_v")
            if st.button("Registrar Vencimiento", key="tab4_btn_guardar_venc"):
                if con_v:
                    try:
                        supabase.table("vencimientos").insert({"concepto": con_v, "fecha_vencimiento": str(f_v), "monto": m_v, "estado": "Pendiente"}).execute()
                        recargar_app("Vencimiento registrado.")
                    except Exception as e:
                        st.error("Error al guardar el vencimiento.")
                else:
                    st.warning("Ingresá un concepto.")
                
        with col_v2:
            st.subheader("Próximos Vencimientos")
            if not df_vencimientos.empty and 'fecha_vencimiento' in df_vencimientos.columns:
                for _, row in df_vencimientos.iterrows():
                    try:
                        f_venc = datetime.strptime(str(row['fecha_vencimiento']), "%Y-%m-%d").date()
                        dias_restantes = (f_venc - date.today()).days
                        
                        if dias_restantes < 0:
                            st.error(f"🛑 **{row['concepto']}** venció hace {abs(dias_restantes)} días (${row['monto']:,.0f})")
                        elif dias_restantes <= 7:
                            st.warning(f"⚠️ **{row['concepto']}** vence en {dias_restantes} días ({row['fecha_vencimiento']}) - ${row['monto']:,.0f}")
                        else:
                            st.success(f"✅ **{row['concepto']}** vence el {row['fecha_vencimiento']} (${row['monto']:,.0f})")
                    except Exception:
                        pass
            else:
                st.info("No hay vencimientos cargados.")

    elif sub_t4 == "Me deben / Debo":
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.subheader("Registrar Cuenta Corriente")
            pers = st.text_input("Persona / Entidad", key="tab4_pers_deuda")
            t_deuda = st.selectbox("Tipo", ["Me deben", "Debo"], key="tab4_tipo_deuda")
            m_deuda = st.number_input("Monto ($)", min_value=0.0, step=1000.0, key="tab4_monto_deuda")
            det_deuda = st.text_input("Detalle (Ej: Entrada de cine, comida)", key="tab4_det_deuda")
            if st.button("Guardar Cuenta Corriente", key="tab4_btn_guardar_deuda"):
                if pers and m_deuda > 0:
                    try:
                        supabase.table("deudas").insert({"persona": pers, "tipo": t_deuda, "monto": m_deuda, "detalle": det_deuda, "estado": "Pendiente"}).execute()
                        recargar_app("Registrado correctamente.")
                    except Exception as e:
                        st.error("Error al guardar la deuda.")
                else:
                    st.warning("Completá el nombre de la persona y un monto mayor a 0.")
                
        with col_d2:
            st.subheader("Estado de Cuentas")
            if not df_deudas.empty and 'estado' in df_deudas.columns:
                df_d_pend = df_deudas[df_deudas['estado'] == 'Pendiente']
                if not df_d_pend.empty:
                    st.dataframe(df_d_pend[['id', 'persona', 'tipo', 'monto', 'detalle']], use_container_width=True, hide_index=True)
                    id_pago = st.number_input("ID de la deuda saldada", min_value=0, step=1, key="tab4_id_pago_deuda")
                    if st.button("Marcar como Saldado / Cobrado", key="tab4_btn_saldar_deuda"):
                        try:
                            supabase.table("deudas").update({"estado": "Saldado"}).eq("id", id_pago).execute()
                            recargar_app("Actualizado.")
                        except Exception as e:
                            st.error("Error al actualizar la deuda.")
                else:
                    st.info("No hay deudas pendientes.")
            else:
                st.info("No hay deudas cargadas.")

# ==========================================
# PESTAÑA 5: HISTORIAL Y EXCEL
# ==========================================
with tab5:
    st.header("📝 Historial, Control y Exportación")
    if not df_transacciones.empty:
        st.dataframe(df_transacciones[['id', 'fecha', 'tipo', 'categoria', 'monto', 'descripcion']], use_container_width=True, hide_index=True)
        
        csv_data = df_transacciones.to_csv(index=False, sep=';', encoding='utf-8-sig').encode('utf-8-sig')
        st.download_button(
            label="📥 Descargar Historial Completo en Excel (CSV)",
            data=csv_data,
            file_name=f"finanzas_pro_{date.today()}.csv",
            mime="text/csv",
            type="primary",
            key="tab5_btn_download_csv"
        )
        
        st.markdown("---")
        
        # HERRAMIENTA DE EDICIÓN DE FECHA DE COBRO DE MOVIMIENTOS EXISTENTES
        with st.expander("✏️ Cambiar Fecha de Cobro de un Movimiento Existente"):
            st.caption("Si cargaste un movimiento previamente con la fecha de trabajo y querés moverlo al mes de cobro real:")
            id_mod_fecha = st.number_input("ID del movimiento a reubicar", min_value=0, step=1, key="tab5_id_mod_fecha")
            nueva_fecha_cobro = st.date_input("Nueva Fecha de Cobro", value=datetime.today(), key="tab5_nueva_fecha_cobro")
            if st.button("Actualizar Fecha de Cobro", key="tab5_btn_mod_fecha"):
                if id_mod_fecha in df_transacciones['id'].values:
                    try:
                        supabase.table("transacciones").update({"fecha": str(nueva_fecha_cobro)}).eq("id", id_mod_fecha).execute()
                        recargar_app(f"Fecha del movimiento {id_mod_fecha} actualizada a {nueva_fecha_cobro}.")
                    except Exception as e:
                        st.error("Error al actualizar la fecha.")
                else:
                    st.error("ID no encontrado en el historial.")

        st.markdown("---")
        id_borrar = st.number_input("ID del movimiento a borrar por error", min_value=0, step=1, key="tab5_id_borrar")
        if st.button("🗑️ Borrar Movimiento", key="tab5_btn_borrar"):
            if 'id' in df_transacciones.columns and id_borrar in df_transacciones['id'].values:
                try:
                    supabase.table("transacciones").delete().eq("id", id_borrar).execute()
                    recargar_app(f"Movimiento {id_borrar} borrado.")
                except Exception as e:
                    st.error("Error al borrar el movimiento.")
            else:
                st.error("ID no encontrado.")
    else:
        st.info("No hay historial disponible.")

# ==========================================
# PESTAÑA 6: CONFIGURACIÓN
# ==========================================
with tab6:
    st.header("⚙️ Ajustes del Sistema")
    with st.expander("➕ Crear Nueva Categoría"):
        nuevo_t = st.selectbox("Tipo", ["Gasto", "Ingreso"], key="tab6_nuevo_tipo_cat")
        nuevo_n = st.text_input("Nombre", key="tab6_nuevo_nombre_cat")
        if st.button("Agregar Categoría", key="tab6_btn_agregar_cat"):
            if nuevo_n:
                try:
                    supabase.table("categorias").insert({"tipo_general": nuevo_t, "nombre": nuevo_n}).execute()
                    recargar_app("Categoría agregada.")
                except Exception as e:
                    st.error("Error al agregar categoría.")
            else:
                st.warning("Escribí el nombre de la categoría.")
