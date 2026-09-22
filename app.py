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
    
    # Calcular mes siguiente
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

# --- PROCESAMIENTO INICIAL ---
if not df_transacciones.empty:
    df_transacciones['fecha'] = pd.to_datetime(df_transacciones['fecha']).dt.date
    df_transacciones['mes_año'] = pd.to_datetime(df_transacciones['fecha']).dt.strftime('%Y-%m')
    df_transacciones['tipo_general'] = df_transacciones['tipo'].apply(lambda x: 'Ingreso' if 'Ingreso' in x else 'Gasto')

# --- ESTRUCTURA DE PESTAÑAS ---
st.title("📈 Mi Ecosistema Financiero")
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Dashboards", 
    "➕ Carga Rápida", 
    "💼 Automatizaciones Laborales", 
    "📝 Historial", 
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
        
        # --- GRÁFICOS COMPARATIVOS ---
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
        
        # --- SIMULADOR DE RENDIMIENTO (MERCADO PAGO) ---
        st.header("🧮 Simulador de Rendimiento Diario (Interés Compuesto)")
        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            cap_inicial = st.number_input("Capital a Invertir ($)", value=float(ahorro if ahorro > 0 else 100000), step=10000.0)
        with col_s2:
            tna = st.number_input("TNA Actual de la Billetera (%)", value=38.0, step=1.0)
        with col_s3:
            dias_inversion = st.number_input("Días de inversión", value=30, min_value=1)
            
        # Fórmula de interés compuesto diario
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
    
    # ------------------------------------
    # 1. ARBITRAJE AAA (NUEVO SISTEMA)
    # ------------------------------------
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
                    st.write("Seleccioná los partidos que entran en este cobro (si cerraron antes la caja, destildá los últimos).")
                    
                    df_pend['Incluir'] = True
                    df_pend = df_pend[['Incluir', 'id', 'fecha', 'detalle', 'monto']]
                    
                    # Tabla interactiva con checkboxes
                    editado = st.data_editor(
                        df_pend,
                        column_config={"Incluir": st.column_config.CheckboxColumn("Cobrar ahora", default=True), "id": None},
                        hide_index=True, use_container_width=True
                    )
                    
                    # Cálculo de liquidación
                    seleccionados = editado[editado['Incluir'] == True]
                    bruto_calculado = seleccionados['monto'].sum()
                    neto_calculado = bruto_calculado - 15000
                    
                    col_tot1, col_tot2, col_tot3 = st.columns(3)
                    col_tot1.metric("Bruto a cobrar", f"${bruto_calculado:,.0f}")
                    col_tot2.metric("Cuota Social AAA", "-$15,000")
                    col_tot3.metric("NETO FINAL", f"${neto_calculado:,.0f}")
                    
                    fecha_proyectada = primer_viernes_mes_siguiente(date.today())
                    fecha_cobro_final = st.date_input("Fecha de cobro real (Automático: 1er viernes mes sig.)", value=fecha_proyectada)
                    
                    if st.button("Generar Liquidación Mensual AAA", type="primary") and neto_calculado > 0:
                        # 1. Guardar como ingreso en transacciones
                        supabase.table("transacciones").insert({
                            "fecha": str(fecha_cobro_final), "tipo": "Ingreso Variable", "categoria": "Arbitraje",
                            "monto": neto_calculado, "descripcion": f"Liquidación AAA ({len(seleccionados)} partidos - Cuota descontada)"
                        }).execute()
                        
                        # 2. Marcar los partidos elegidos como 'Cobrado'
                        ids_cobrados = seleccionados['id'].tolist()
                        for p_id in ids_cobrados:
                            supabase.table("partidos_aaa").update({"estado": "Cobrado"}).eq("id", p_id).execute()
                            
                        recargar_app(f"Liquidación agendada para el {fecha_cobro_final}.")
                else:
                    st.info("No tenés partidos pendientes de cobrar.")

    # ------------------------------------
    # 2. ARBITRAJE ARGENLIGA
    # ------------------------------------
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

    # ------------------------------------
    # 3. CONSULTORIO
    # ------------------------------------
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
                recargar_app("Turnos del consultorio guardados.")

# ==========================================
# PESTAÑA 4 y 5: HISTORIAL Y CONFIGURACIÓN (Se mantienen igual pero limpias)
# ==========================================
with tab4:
    st.header("📝 Historial y Control")
    if not df_transacciones.empty:
        st.dataframe(df_transacciones[['id', 'fecha', 'tipo', 'categoria', 'monto', 'descripcion']], use_container_width=True, hide_index=True)
        id_borrar = st.number_input("ID del movimiento a borrar (por error)", min_value=0, step=1)
        if st.button("🗑️ Borrar Movimiento"):
            if id_borrar in df_transacciones['id'].values:
                supabase.table("transacciones").delete().eq("id", id_borrar).execute()
                recargar_app(f"Movimiento {id_borrar} borrado.")

with tab5:
    st.header("⚙️ Ajustes del Sistema")
    with st.expander("➕ Crear Nueva Categoría"):
        nuevo_t = st.selectbox("Tipo", ["Gasto", "Ingreso"])
        nuevo_n = st.text_input("Nombre")
        if st.button("Agregar Categoría"):
            supabase.table("categorias").insert({"tipo_general": nuevo_t, "nombre": nuevo_n}).execute()
            recargar_app("Categoría agregada.")
