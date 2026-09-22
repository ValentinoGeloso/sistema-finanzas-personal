import streamlit as st
from supabase import create_client
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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
def primer_viernes_del_mes(year, month):
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
    time.sleep(1) # Da tiempo a que se vea el mensaje
    st.rerun()

# --- CARGA DE DATOS ---
def cargar_tabla(nombre_tabla, order_by="id", desc=False):
    res = supabase.table(nombre_tabla).select("*").order(order_by, desc=desc).execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

df_transacciones = cargar_tabla("transacciones", order_by="fecha", desc=True)
df_categorias = cargar_tabla("categorias")

# --- PROCESAMIENTO INICIAL ---
if not df_transacciones.empty:
    df_transacciones['fecha'] = pd.to_datetime(df_transacciones['fecha']).dt.date
    df_transacciones['mes_año'] = pd.to_datetime(df_transacciones['fecha']).dt.strftime('%Y-%m')

# --- ESTRUCTURA DE PESTAÑAS ---
st.title("📈 Mi Ecosistema Financiero")
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Dashboard & 50/30/20", 
    "➕ Carga Rápida", 
    "💼 Automatizaciones Laborales", 
    "📝 Historial", 
    "⚙️ Configuración"
])

# ==========================================
# PESTAÑA 1: DASHBOARD, PRESUPUESTOS Y 50/30/20
# ==========================================
with tab1:
    if df_transacciones.empty:
        st.info("No hay datos registrados aún.")
    else:
        meses_disponibles = sorted(df_transacciones['mes_año'].unique(), reverse=True)
        mes_seleccionado = st.selectbox("📅 Mes a analizar", meses_disponibles)
        df_mes = df_transacciones[df_transacciones['mes_año'] == mes_seleccionado]
        
        ingresos = df_mes[df_mes['tipo'].str.contains("Ingreso")]['monto'].sum()
        gastos = df_mes[df_mes['tipo'].str.contains("Gasto")]['monto'].sum()
        ahorro = ingresos - gastos
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Ingresos Neta", f"${ingresos:,.2f}")
        col2.metric("Gastos Totales", f"${gastos:,.2f}")
        col3.metric("Ahorro / Inversión", f"${ahorro:,.2f}")
        st.markdown("---")
        
        # --- ANÁLISIS 50/30/20 ---
        st.subheader("⚖️ Termómetro Financiero: Regla 50/30/20")
        if ingresos > 0 and not df_categorias.empty and 'clase_503020' in df_categorias.columns:
            # Unir gastos con sus categorías para saber si es 50 o 30
            df_gastos = df_mes[df_mes['tipo'].str.contains("Gasto")].copy()
            if not df_gastos.empty:
                df_gastos = df_gastos.merge(df_categorias[['nombre', 'clase_503020']], left_on='categoria', right_on='nombre', how='left')
                
                gastos_50 = df_gastos[df_gastos['clase_503020'] == '50-Necesidad']['monto'].sum()
                gastos_30 = df_gastos[df_gastos['clase_503020'] == '30-Deseo']['monto'].sum()
                
                pct_50 = (gastos_50 / ingresos) * 100
                pct_30 = (gastos_30 / ingresos) * 100
                pct_20 = (ahorro / ingresos) * 100 if ahorro > 0 else 0
                
                c_50, c_30, c_20 = st.columns(3)
                c_50.progress(min(pct_50 / 100, 1.0))
                c_50.caption(f"**Necesidades (Ideal 50%):** {pct_50:.1f}% (${gastos_50:,.0f})")
                
                c_30.progress(min(pct_30 / 100, 1.0))
                c_30.caption(f"**Deseos (Ideal 30%):** {pct_30:.1f}% (${gastos_30:,.0f})")
                
                c_20.progress(min(pct_20 / 100, 1.0))
                c_20.caption(f"**Ahorro (Ideal 20%):** {pct_20:.1f}% (${ahorro:,.0f})")
            else:
                st.write("Aún no hay gastos este mes para analizar.")
        
        st.markdown("---")
        
        # --- ALARMAS DE PRESUPUESTO ---
        st.subheader("🚨 Control de Presupuestos")
        if 'limite_mensual' in df_categorias.columns:
            categorias_con_limite = df_categorias[df_categorias['limite_mensual'] > 0]
            for _, row in categorias_con_limite.iterrows():
                gastado = df_mes[df_mes['categoria'] == row['nombre']]['monto'].sum()
                limite = row['limite_mensual']
                porcentaje = (gastado / limite) * 100
                
                if porcentaje >= 90:
                    st.error(f"**{row['nombre']}**: Gastaste ${gastado:,.0f} de ${limite:,.0f} ({porcentaje:.0f}%). ¡ALERTA ROJA! 🛑")
                elif porcentaje >= 75:
                    st.warning(f"**{row['nombre']}**: Gastaste ${gastado:,.0f} de ${limite:,.0f} ({porcentaje:.0f}%). Cuidado. ⚠️")
                else:
                    st.success(f"**{row['nombre']}**: Gastaste ${gastado:,.0f} de ${limite:,.0f} ({porcentaje:.0f}%). Viene bien. ✅")

# ==========================================
# PESTAÑA 2: CARGA RÁPIDA (Común)
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
    # 1. ARBITRAJE AAA
    # ------------------------------------
    if "AAA" in modo_trabajo:
        st.subheader("Cierre Mensual AAA")
        st.write("Se calcula automáticamente la fecha de pago (1er Viernes del mes seleccionado) y se descuenta la cuota social de $15,000.")
        
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            mes_cobro = st.number_input("Mes de cobro", min_value=1, max_value=12, value=datetime.today().month)
            anio_cobro = st.number_input("Año de cobro", min_value=2024, max_value=2030, value=datetime.today().year)
        with col_a2:
            bruto_aaa = st.number_input("Monto BRUTO generado en los partidos ($)", step=5000.0)
            
        fecha_pago_aaa = primer_viernes_del_mes(anio_cobro, mes_cobro)
        neto_aaa = bruto_aaa - 15000 if bruto_aaa > 0 else 0
        
        st.info(f"📅 **Fecha de pago calculada:** {fecha_pago_aaa.strftime('%A %d/%m/%Y')}")
        st.warning(f"📉 **Descuento Cuota AAA:** -$15,000")
        st.success(f"💰 **Neto a depositar/cobrar:** ${neto_aaa:,.2f}")
        
        if st.button("Registrar Liquidación AAA", type="primary", use_container_width=True) and neto_aaa > 0:
            nuevo_aaa = {
                "fecha": str(fecha_pago_aaa), "tipo": "Ingreso Variable", "categoria": "Arbitraje",
                "monto": neto_aaa, "descripcion": f"Liquidación AAA (Bruto: {bruto_aaa} - Cuota: 15000)"
            }
            supabase.table("transacciones").insert(nuevo_aaa).execute()
            recargar_app("Liquidación AAA registrada.")

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
                    # 1 = Martes, 4 = Viernes
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
            st.write("💡 Modificá el monto si un día trabajaste menos, o seleccioná y borrá la fila con 'Suprimir' si fue feriado.")
            df_editado = st.data_editor(st.session_state['turnos_cons'], num_rows="dynamic", use_container_width=True)
            
            if st.button("💾 Guardar Planilla Mensual", type="primary"):
                datos_a_insertar = []
                for _, row in df_editado.iterrows():
                    datos_a_insertar.append({
                        "fecha": row['Fecha'], "tipo": "Ingreso Variable", "categoria": row['Categoría'],
                        "monto": row['Monto'], "descripcion": row['Descripción']
                    })
                supabase.table("transacciones").insert(datos_a_insertar).execute()
                del st.session_state['turnos_cons']
                recargar_app(f"{len(datos_a_insertar)} turnos guardados.")

# ==========================================
# PESTAÑA 4: HISTORIAL
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
            else:
                st.error("ID no encontrado.")

# ==========================================
# PESTAÑA 5: CONFIGURACIÓN
# ==========================================
with tab5:
    st.header("⚙️ Ajustes del Sistema")
    
    st.subheader("Configurar Categorías, Presupuestos y 50/30/20")
    if not df_categorias.empty and 'limite_mensual' in df_categorias.columns:
        st.write("Definí tus límites mensuales y clasificá tus gastos para que el termómetro 50/30/20 funcione perfecto.")
        
        # Hacemos el DataFrame editable para actualizar directamente a la base
        df_cat_editar = df_categorias[['id', 'nombre', 'tipo_general', 'clase_503020', 'limite_mensual']]
        df_cat_editado = st.data_editor(
            df_cat_editar, 
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True),
                "tipo_general": st.column_config.SelectboxColumn("Tipo", options=["Ingreso", "Gasto"]),
                "clase_503020": st.column_config.SelectboxColumn("Regla 50/30", options=["50-Necesidad", "30-Deseo", "Ingreso", "Ahorro/Inversión"]),
                "limite_mensual": st.column_config.NumberColumn("Límite Mensual ($)", min_value=0.0)
            },
            hide_index=True, use_container_width=True
        )
        
        if st.button("💾 Guardar Cambios en Categorías"):
            # Actualiza cada fila iterando
            for index, row in df_cat_editado.iterrows():
                supabase.table("categorias").update({
                    "nombre": row['nombre'],
                    "tipo_general": row['tipo_general'],
                    "clase_503020": row['clase_503020'],
                    "limite_mensual": row['limite_mensual']
                }).eq("id", row['id']).execute()
            recargar_app("Categorías y presupuestos actualizados.")
            
    with st.expander("➕ Crear Nueva Categoría"):
        nuevo_t = st.selectbox("Tipo", ["Gasto", "Ingreso"])
        nuevo_n = st.text_input("Nombre")
        nuevo_c = st.selectbox("Clasificación (50/30/20)", ["50-Necesidad", "30-Deseo", "Ingreso"])
        nuevo_l = st.number_input("Límite Mensual (0 = sin límite)", min_value=0.0)
        
        if st.button("Agregar"):
            supabase.table("categorias").insert({
                "tipo_general": nuevo_t, "nombre": nuevo_n, 
                "clase_503020": nuevo_c, "limite_mensual": nuevo_l
            }).execute()
            recargar_app("Categoría agregada.")
