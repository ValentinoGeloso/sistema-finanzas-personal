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
    st.error("Error conectando a Supabase.")
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
    time.sleep(1.5)
    st.rerun()

# --- CARGA DE DATOS ---
def cargar_tabla(nombre_tabla, order_by="id", desc=False):
    res = supabase.table(nombre_tabla).select("*").order(order_by, desc=desc).execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

df_transacciones = cargar_tabla("transacciones", order_by="fecha", desc=True)
df_categorias = cargar_tabla("categorias")
df_partidos_aaa = cargar_tabla("partidos_aaa", order_by="fecha", desc=True)
df_metas = cargar_tabla("metas_ahorro")
df_vencimientos = cargar_tabla("vencimientos", order_by="fecha_vencimiento")
df_deudas = cargar_tabla("deudas")

# --- PROCESAMIENTO INICIAL ---
if not df_transacciones.empty:
    df_transacciones['fecha'] = pd.to_datetime(df_transacciones['fecha']).dt.date
    df_transacciones['mes_año'] = pd.to_datetime(df_transacciones['fecha']).dt.strftime('%Y-%m')
    df_transacciones['tipo_general'] = df_transacciones['tipo'].apply(lambda x: 'Ingreso' if 'Ingreso' in x else 'Gasto')

# --- ESTRUCTURA DE PESTAÑAS ---
st.title("📈 Mi Ecosistema Financiero Pro")
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
        st.info("No hay datos registrados aún.")
    else:
        st.header("📊 Análisis Mensual")
        meses_disponibles = sorted(df_transacciones['mes_año'].unique(), reverse=True)
        mes_seleccionado = st.selectbox("📅 Seleccionar Mes", meses_disponibles)
        df_mes = df_transacciones[df_transacciones['mes_año'] == mes_seleccionado]
        
        ingresos = df_mes[df_mes['tipo_general'] == 'Ingreso']['monto'].sum()
        gastos = df_mes[df_mes['tipo_general'] == 'Gasto']['monto'].sum()
        ahorro = ingresos - gastos
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Ingresos Neta", f"${ingresos:,.2f}")
        col2.metric("Gastos Totales", f"${gastos:,.2f}")
        col3.metric("Ahorro / Inversión", f"${ahorro:,.2f}", delta=f"{(ahorro/ingresos)*100:.1f}% del ingreso" if ingresos>0 else "")
        
        st.markdown("---")
        
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.subheader("Ingresos vs Gastos (Evolución)")
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
                
        st.subheader(f"Desglose de Ingresos ({mes_seleccionado})")
        df_ingresos_mes = df_mes[df_mes['tipo_general'] == 'Ingreso']
        if not df_ingresos_mes.empty:
            fig_ingresos = px.pie(df_ingresos_mes, names='categoria', values='monto', hole=0.4)
            st.plotly_chart(fig_ingresos, use_container_width=True)

        st.markdown("---")
        st.header("🧮 Simulador de Rendimiento Diario (Interés Compuesto)")
        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            cap_inicial = st.number_input("Capital a Invertir ($)", value=float(ahorro if ahorro > 0 else 100000), step=10000.0)
        with col_s2:
            tna = st.number_input("TNA Actual Billetera (%)", value=38.0, step=1.0)
        with col_s3:
            dias_inversion = st.number_input("Días de inversión", value=30, min_value=1)
            
        tasa_diaria = (tna / 100) / 365
        cap_final = cap_inicial * ((1 + tasa_diaria) ** dias_inversion)
        ganancia = cap_final - cap_inicial
        st.success(f"💸 **Dinero total al final:** ${cap_final:,.2f} (Ganaste **${ganancia:,.2f}** sin hacer nada)")

# ==========================================
# PESTAÑA 2: CARGA RÁPIDA
# ==========================================
with tab2:
    st.header("📝 Movimiento Único")
    tipo_mov = st.selectbox("Tipo", ["Ingreso Variable", "Ingreso Fijo", "Gasto Variable", "Gasto Fijo"])
    tipo_general = "Ingreso" if "Ingreso" in tipo_mov else "Gasto"
    opciones_cat = df_categorias[df_categorias['tipo_general'] == tipo_general]['nombre'].tolist() if not df_categorias.empty else ["Sin categorías"]
    
    cat_mov = st.selectbox("Categoría", opciones_cat)
    monto_mov = st.number_input("Monto ($)", min_value=0.0, step=1000.0)
    fecha_mov = st.date_input("Fecha", datetime.today())
    desc_mov = st.text_input("Descripción (Ej: Nafta, Coto...)")
    
    if st.button("Guardar Movimiento", type="primary"):
        nuevo = {"fecha": str(fecha_mov), "tipo": tipo_mov, "categoria": cat_mov, "monto": monto_mov, "descripcion": desc_mov}
        supabase.table("transacciones").insert(nuevo).execute()
        recargar_app("Movimiento guardado.")

# ==========================================
# PESTAÑA 3: AUTOMATIZACIONES LABORALES
# ==========================================
with tab3:
    st.header("💼 Centros de Ingreso Automáticos")
    modo_trabajo = st.radio("Seleccioná tu actividad:", ["⚽ Arbitraje: AAA (Sábados/Mensual)", "⚽ Arbitraje: Argenliga (Domingos/Diario)", "🩺 Consultorio Méd. (Semanal)"], horizontal=True)
    
    if "AAA" in modo_trabajo:
        col_aaa1, col_aaa2 = st.columns([1, 1.5])
        with col_aaa1:
            st.subheader("1. Cargar Partido (Día a Día)")
            f_partido_aaa = st.date_input("Fecha del Partido", value=datetime.today())
            m_partido_aaa = st.number_input("Honorario del partido ($)", min_value=0.0, step=1000.0)
            d_partido_aaa = st.text_input("Detalle (Ej: Cat. Juveniles Cancha 2)")
            
            if st.button("Guardar Partido"):
                supabase.table("partidos_aaa").insert({
                    "fecha": str(f_partido_aaa), "detalle": d_partido_aaa, "monto": m_partido_aaa, "estado": "Pendiente"
                }).execute()
                recargar_app("Partido guardado en pendientes.")
                
        with col_aaa2:
            st.subheader("2. Liquidación / Cierre de Caja")
            if not df_partidos_aaa.empty:
                df_pend = df_partidos_aaa[df_partidos_aaa['estado'] == 'Pendiente'].copy()
                if not df_pend.empty:
                    st.write("Seleccioná partidos a cobrar (destildá si hubo cierre anticipado).")
                    df_pend['Incluir'] = True
                    df_pend = df_pend[['Incluir', 'id', 'fecha', 'detalle', 'monto']]
                    editado = st.data_editor(
                        df_pend,
                        column_config={"Incluir": st.column_config.CheckboxColumn("Cobrar ahora", default=True), "id": None},
                        hide_index=True, use_container_width=True
                    )
                    seleccionados = editado[editado['Incluir'] == True]
                    bruto_calculado = seleccionados['monto'].sum()
                    neto_calculado = bruto_calculado - 15000
                    
                    col_tot1, col_tot2, col_tot3 = st.columns(3)
                    col_tot1.metric("Bruto", f"${bruto_calculado:,.0f}")
                    col_tot2.metric("Cuota AAA", "-$15,000")
                    col_tot3.metric("NETO", f"${neto_calculado:,.0f}")
                    
                    fecha_proyectada = primer_viernes_mes_siguiente(date.today())
                    fecha_cobro_final = st.date_input("Fecha de cobro real", value=fecha_proyectada)
                    
                    if st.button("Generar Liquidación Mensual AAA", type="primary") and neto_calculado > 0:
                        supabase.table("transacciones").insert({
                            "fecha": str(fecha_cobro_final), "tipo": "Ingreso Variable", "categoria": "Arbitraje",
                            "monto": neto_calculado, "descripcion": f"Liquidación AAA ({len(seleccionados)} partidos)"
                        }).execute()
                        for p_id in seleccionados['id'].tolist():
                            supabase.table("partidos_aaa").update({"estado": "Cobrado"}).eq("id", p_id).execute()
                        recargar_app(f"Liquidación agendada para el {fecha_cobro_final}.")
                else:
                    st.info("No tenés partidos pendientes de cobrar.")

    elif "Argenliga" in modo_trabajo:
        st.subheader("Cobro Inmediato Argenliga")
        fecha_arg = st.date_input("Fecha del partido", value=ultimo_domingo())
        monto_arg = st.number_input("Total cobrado en mano ($)", step=1000.0)
        desc_arg = st.text_input("Nota (Opcional)", placeholder="Ej: 2 partidos cancha 3")
        
        if st.button("Registrar Argenliga", type="primary") and monto_arg > 0:
            supabase.table("transacciones").insert({
                "fecha": str(fecha_arg), "tipo": "Ingreso Variable", "categoria": "Arbitraje",
                "monto": monto_arg, "descripcion": f"Argenliga: {desc_arg}"
            }).execute()
            recargar_app("Ingreso Argenliga registrado.")

    elif "Consultorio" in modo_trabajo:
        st.subheader("Generador de Turnos (Martes y Viernes)")
        c_mes = st.number_input("Mes", min_value=1, max_value=12, value=datetime.today().month)
        c_anio = st.number_input("Año", min_value=2024, value=datetime.today().year)
        c_monto = st.number_input("Pago por día normal ($)", value=50000.0, step=1000.0)
        
        if st.button("🔍 Generar Días del Mes"):
            cal = calendar.monthcalendar(c_anio, c_mes)
            turnos = []
            for semana in cal:
                for i, dia in enumerate(semana):
                    if dia != 0 and i in [1, 4]:
                        turnos.append({
                            "Fecha": f"{c_anio}-{c_mes:02d}-{dia:02d}", 
                            "Categoría": "Consultorio", 
                            "Monto": float(c_monto), 
                            "Descripción": "Día laboral"
                        })
            if turnos:
                st.session_state['turnos_cons'] = pd.DataFrame(turnos)

        if 'turnos_cons' in st.session_state:
            df_editado = st.data_editor(st.session_state['turnos_cons'], num_rows="dynamic", use_container_width=True)
            if st.button("💾 Guardar Planilla Mensual", type="primary"):
                datos_a_insertar = []
                for _, row in df_editado.iterrows():
                    datos_a_insertar.append({
                        "fecha": row['Fecha'], "tipo": "Ingreso Fijo", "categoria": row['Categoría'],
                        "monto": row['Monto'], "descripcion": row['Descripción']
                    })
                supabase.table("transacciones").insert(datos_a_insertar).execute()
                del st.session_state['turnos_cons']
                recargar_app("Turnos guardados.")

# ==========================================
# PESTAÑA 4: METAS, VENCIMIENTOS Y DEUDAS
# ==========================================
with tab4:
    st.header("🎯 Sobres de Ahorro, Vencimientos y Cuentas Corrientes")
    sub_t4 = st.radio("Sección:", ["Sobres / Metas", "Vencimientos (Corsa / Servicios)", "Me deben / Debo"], horizontal=True)
    
    if sub_t4 == "Sobres / Metas":
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            st.subheader("Crear / Actualizar Sobres")
            n_meta = st.text_input("Nombre de la meta (Ej: Facultad 2027, Mantenimiento Corsa)")
            obj_meta = st.number_input("Monto Objetivo ($)", min_value=1000.0, step=10000.0)
            act_meta = st.number_input("Monto Actual Ahorrado ($)", min_value=0.0, step=1000.0)
            if st.button("Guardar Meta"):
                supabase.table("metas_ahorro").insert({"nombre": n_meta, "monto_objetivo": obj_meta, "monto_actual": act_meta}).execute()
                recargar_app("Meta creada con éxito.")
                
        with col_m2:
            st.subheader("Progreso de tus Metas")
            if not df_metas.empty:
                for _, row in df_metas.iterrows():
                    porc = min(row['monto_actual'] / row['monto_objetivo'], 1.0)
                    st.write(f"**{row['nombre']}**: ${row['monto_actual']:,.0f} / ${row['monto_objetivo']:,.0f}")
                    st.progress(porc)
            else:
                st.info("No hay metas creadas.")
                
    elif sub_t4 == "Vencimientos (Corsa / Servicios)":
        col_v1, col_v2 = st.columns(2)
        with col_v1:
            st.subheader("Nuevo Vencimiento")
            con_v = st.text_input("Concepto (Ej: Patente Corsa, VTV, Seguro)")
            f_v = st.date_input("Fecha de Vencimiento", value=datetime.today())
            m_v = st.number_input("Monto estimado ($)", step=1000.0)
            if st.button("Registrar Vencimiento"):
                supabase.table("vencimientos").insert({"concepto": con_v, "fecha_vencimiento": str(f_v), "monto": m_v, "estado": "Pendiente"}).execute()
                recargar_app("Vencimiento registrado.")
                
        with col_v2:
            st.subheader("Próximos Vencimientos")
            if not df_vencimientos.empty:
                for _, row in df_vencimientos.iterrows():
                    f_venc = datetime.strptime(row['fecha_vencimiento'], "%Y-%m-%d").date()
                    dias_restantes = (f_venc - date.today()).days
                    
                    if dias_restantes < 0:
                        st.error(f"🛑 **{row['concepto']}** venció hace {abs(dias_restantes)} días (${row['monto']:,.0f})")
                    elif dias_restantes <= 7:
                        st.warning(f"⚠️ **{row['concepto']}** vence en {dias_restantes} días ({row['fecha_vencimiento']}) - ${row['monto']:,.0f}")
                    else:
                        st.success(f"✅ **{row['concepto']}** vence el {row['fecha_vencimiento']} (${row['monto']:,.0f})")
            else:
                st.info("No hay vencimientos cargados.")

    elif sub_t4 == "Me deben / Debo":
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            st.subheader("Registrar Cuenta Corriente")
            pers = st.text_input("Persona / Entidad")
            t_deuda = st.selectbox("Tipo", ["Me deben", "Debo"])
            m_deuda = st.number_input("Monto ($)", step=1000.0)
            det_deuda = st.text_input("Detalle (Ej: Entrada de cine, comida)")
            if st.button("Guardar Cuenta Corriente"):
                supabase.table("deudas").insert({"persona": pers, "tipo": t_deuda, "monto": m_deuda, "detalle": det_deuda, "estado": "Pendiente"}).execute()
                recargar_app("Registrado correctamente.")
                
        with col_d2:
            st.subheader("Estado de Cuentas")
            if not df_deudas.empty:
                df_d_pend = df_deudas[df_deudas['estado'] == 'Pendiente']
                if not df_d_pend.empty:
                    st.dataframe(df_d_pend[['persona', 'tipo', 'monto', 'detalle']], use_container_width=True, hide_index=True)
                    id_pago = st.number_input("ID de la deuda saldada", min_value=0, step=1)
                    if st.button("Marcar como Saldado / Cobrado"):
                        supabase.table("deudas").update({"estado": "Saldado"}).eq("id", id_pago).execute()
                        recargar_app("Actualizado.")
                else:
                    st.info("No hay deudas pendientes.")

# ==========================================
# PESTAÑA 5: HISTORIAL Y EXCEL
# ==========================================
with tab5:
    st.header("📝 Historial, Control y Exportación")
    if not df_transacciones.empty:
        st.dataframe(df_transacciones[['id', 'fecha', 'tipo', 'categoria', 'monto', 'descripcion']], use_container_width=True, hide_index=True)
        
        # Botón para exportar a Excel (CSV)
        csv_data = df_transacciones.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar Historial Completo en Excel (CSV)",
            data=csv_data,
            file_name=f"finanzas_pro_{date.today()}.csv",
            mime="text/csv",
            type="primary"
        )
        
        st.markdown("---")
        id_borrar = st.number_input("ID del movimiento a borrar por error", min_value=0, step=1)
        if st.button("🗑️ Borrar Movimiento"):
            if id_borrar in df_transacciones['id'].values:
                supabase.table("transacciones").delete().eq("id", id_borrar).execute()
                recargar_app(f"Movimiento {id_borrar} borrado.")
            else:
                st.error("ID no encontrado.")

# ==========================================
# PESTAÑA 6: CONFIGURACIÓN
# ==========================================
with tab6:
    st.header("⚙️ Ajustes del Sistema")
    with st.expander("➕ Crear Nueva Categoría"):
        nuevo_t = st.selectbox("Tipo", ["Gasto", "Ingreso"])
        nuevo_n = st.text_input("Nombre")
        if st.button("Agregar Categoría"):
            supabase.table("categorias").insert({"tipo_general": nuevo_t, "nombre": nuevo_n}).execute()
            recargar_app("Categoría agregada.")
