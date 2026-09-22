import streamlit as st
from supabase import create_client
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
import calendar

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

# --- FUNCIONES DE CARGA ---
def cargar_tabla(nombre_tabla, order_by="id", desc=False):
    res = supabase.table(nombre_tabla).select("*").order(order_by, desc=desc).execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

df_transacciones = cargar_tabla("transacciones", order_by="fecha", desc=True)
df_categorias = cargar_tabla("categorias")
df_recurrentes = cargar_tabla("recurrentes")

if not df_transacciones.empty:
    df_transacciones['fecha'] = pd.to_datetime(df_transacciones['fecha']).dt.date
    df_transacciones['mes_año'] = pd.to_datetime(df_transacciones['fecha']).dt.strftime('%Y-%m')

# --- ESTRUCTURA DE PESTAÑAS ---
st.title("📈 Sistema de Gestión Financiera Pro")
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 Dashboard", 
    "➕ Carga Única", 
    "🗓️ Carga de Turnos (Consultorio)", 
    "📝 Historial & Edición", 
    "⚙️ Configuración"
])

# ==========================================
# PESTAÑA 1: DASHBOARD
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
        col1.metric("Ingresos del Mes", f"${ingresos:,.2f}")
        col2.metric("Gastos del Mes", f"${gastos:,.2f}")
        col3.metric("Balance Mensual", f"${ahorro:,.2f}")
        
        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            df_gastos = df_mes[df_mes['tipo'].str.contains("Gasto")]
            if not df_gastos.empty:
                fig_pie = px.pie(df_gastos, values='monto', names='categoria', title="Distribución de Gastos", hole=0.4)
                st.plotly_chart(fig_pie, use_container_width=True)
        with c2:
            df_hist = df_transacciones.copy()
            df_hist['valor'] = df_hist.apply(lambda x: x['monto'] if 'Ingreso' in x['tipo'] else -x['monto'], axis=1)
            ahorro_historico = df_hist.groupby('mes_año')['valor'].sum().reset_index()
            fig_bar = px.bar(ahorro_historico, x='mes_año', y='valor', title="Evolución del Balance", color='valor', color_continuous_scale='RdYlGn')
            st.plotly_chart(fig_bar, use_container_width=True)

# ==========================================
# PESTAÑA 2: CARGA MANUAL (Movimiento Único)
# ==========================================
with tab2:
    st.header("📝 Registrar un Movimiento")
    tipo_mov = st.selectbox("Tipo", ["Ingreso Fijo", "Ingreso Variable", "Gasto Fijo", "Gasto Variable"], key="t_mov")
    
    tipo_general = "Ingreso" if "Ingreso" in tipo_mov else "Gasto"
    opciones_cat = df_categorias[df_categorias['tipo_general'] == tipo_general]['nombre'].tolist() if not df_categorias.empty else ["Sin categorías"]
    
    cat_mov = st.selectbox("Categoría", opciones_cat, key="c_mov")
    monto_mov = st.number_input("Monto ($)", min_value=0.0, step=1000.0)
    fecha_mov = st.date_input("Fecha exacta del movimiento", datetime.today())
    desc_mov = st.text_input("Descripción (Opcional)", placeholder="Ej: Nafta viaje Lobos, Compra súper...")
    
    if st.button("Guardar Movimiento", type="primary"):
        nuevo = {"fecha": str(fecha_mov), "tipo": tipo_mov, "categoria": cat_mov, "monto": monto_mov, "descripcion": desc_mov}
        supabase.table("transacciones").insert(nuevo).execute()
        st.success("✅ Guardado exitosamente. (Recargá la página con F5 si querés ver los gráficos actualizados al instante).")

# ==========================================
# PESTAÑA 3: CARGA MASIVA DE TURNOS (El Consultorio)
# ==========================================
with tab3:
    st.header("🗓️ Generador de Ingresos por Días de la Semana")
    st.write("Seleccioná los días que trabajás fijo (ej: Martes y Viernes en el consultorio). El sistema calculará todos los días del mes y te dejará borrar los feriados antes de guardar todo junto.")
    
    col_t1, col_t2 = st.columns(2)
    with col_t1:
        mes_turno = st.number_input("Mes (1-12)", min_value=1, max_value=12, value=datetime.today().month)
        anio_turno = st.number_input("Año", min_value=2024, max_value=2030, value=datetime.today().year)
        cat_turno = st.selectbox("Categoría a registrar", df_categorias[df_categorias['tipo_general'] == 'Ingreso']['nombre'].tolist() if not df_categorias.empty else ["Consultorio"])
    with col_t2:
        monto_turno = st.number_input("Pago por día ($)", min_value=0.0, value=50000.0, step=1000.0)
        dias_map = {"Lunes": 0, "Martes": 1, "Miércoles": 2, "Jueves": 3, "Viernes": 4, "Sábado": 5, "Domingo": 6}
        dias_elegidos = st.multiselect("Días laborales de la semana", list(dias_map.keys()), default=["Martes", "Viernes"])

    if st.button("🔍 Generar Calendario Prevío"):
        dias_int = [dias_map[d] for d in dias_elegidos]
        cal = calendar.monthcalendar(anio_turno, mes_turno)
        turnos = []
        for semana in cal:
            for i, dia in enumerate(semana):
                if dia != 0 and i in dias_int:
                    fecha_str = f"{anio_turno}-{mes_turno:02d}-{dia:02d}"
                    turnos.append({
                        "Fecha": fecha_str, 
                        "Categoría": cat_turno, 
                        "Monto": float(monto_turno), 
                        "Descripción": "Turno normal"
                    })
        
        if turnos:
            st.session_state['turnos_generados'] = pd.DataFrame(turnos)

    if 'turnos_generados' in st.session_state:
        st.info("💡 A continuación, si un día fue **feriado**, seleccioná la fila clickeando a la izquierda y apretá la tecla 'Suprimir' (Delete) para borrarla, o modificá el monto si trabajaste medio día.")
        
        # Tabla interactiva editable
        df_editado = st.data_editor(st.session_state['turnos_generados'], num_rows="dynamic", use_container_width=True)
        
        if st.button("💾 Guardar todos estos turnos", type="primary"):
            datos_a_insertar = []
            for _, row in df_editado.iterrows():
                datos_a_insertar.append({
                    "fecha": row['Fecha'],
                    "tipo": "Ingreso Variable",
                    "categoria": row['Categoría'],
                    "monto": row['Monto'],
                    "descripcion": row['Descripción']
                })
            supabase.table("transacciones").insert(datos_a_insertar).execute()
            st.success(f"✅ Se guardaron {len(datos_a_insertar)} ingresos en tu base de datos.")
            del st.session_state['turnos_generados']

# ==========================================
# PESTAÑA 4: HISTORIAL Y BORRADO
# ==========================================
with tab4:
    st.header("📝 Historial de Movimientos")
    if not df_transacciones.empty:
        st.dataframe(
            df_transacciones[['id', 'fecha', 'tipo', 'categoria', 'monto', 'descripcion']].sort_values(by='fecha', ascending=False),
            use_container_width=True,
            hide_index=True
        )
        
        st.markdown("---")
        st.subheader("🗑️ Borrar un movimiento por error")
        st.write("Buscá el ID del movimiento en la tabla de arriba e ingresalo para eliminarlo.")
        id_borrar = st.number_input("ID del movimiento a borrar", min_value=0, step=1)
        if st.button("Borrar Movimiento", type="primary"):
            # Verificar si el ID existe
            if id_borrar in df_transacciones['id'].values:
                supabase.table("transacciones").delete().eq("id", id_borrar).execute()
                st.success(f"Movimiento {id_borrar} borrado. Recargá la página para actualizar (F5).")
            else:
                st.error("Ese ID no existe o ya fue borrado.")
    else:
        st.info("No hay historial disponible.")

# ==========================================
# PESTAÑA 5: CONFIGURACIÓN Y EDICIÓN
# ==========================================
with tab5:
    st.header("⚙️ Configuración General")
    col_c1, col_c2 = st.columns(2)
    
    with col_c1:
        st.subheader("Categorías")
        with st.expander("➕ Crear Nueva"):
            nuevo_t = st.selectbox("Tipo de Categoría", ["Ingreso", "Gasto"], key="new_cat_t")
            nuevo_n = st.text_input("Nombre de la Categoría")
            if st.button("Guardar Categoría"):
                supabase.table("categorias").insert({"tipo_general": nuevo_t, "nombre": nuevo_n}).execute()
                st.success("Guardada. (F5 para recargar)")
                
        with st.expander("✏️ Editar Categoría Existente"):
            if not df_categorias.empty:
                cat_vieja = st.selectbox("Categoría a modificar", df_categorias['nombre'].tolist())
                cat_nueva = st.text_input("Nuevo nombre", value=cat_vieja)
                if st.button("Actualizar Nombre"):
                    # Actualiza la categoría
                    supabase.table("categorias").update({"nombre": cat_nueva}).eq("nombre", cat_vieja).execute()
                    # Actualiza el historial para no perder la sincronización
                    supabase.table("transacciones").update({"categoria": cat_nueva}).eq("categoria", cat_vieja).execute()
                    st.success(f"Se cambió '{cat_vieja}' por '{cat_nueva}' en todo el sistema.")
    
    with col_c2:
        st.subheader("Gastos Fijos Mensuales")
        st.info("Para alquileres o servicios que se cobran el mismo día una vez al mes.")
        with st.expander("Crear Gasto Fijo"):
            f_cat = st.selectbox("Categoría", df_categorias[df_categorias['tipo_general'] == 'Gasto']['nombre'].tolist() if not df_categorias.empty else [])
            f_monto = st.number_input("Monto Mensual", step=1000.0)
            f_desc = st.text_input("Descripción Fija", placeholder="Ej: Expensas, Internet...")
            if st.button("Guardar Gasto Fijo"):
                supabase.table("recurrentes").insert({"tipo": "Gasto Fijo", "categoria": f_cat, "monto": f_monto, "descripcion": f_desc}).execute()
                st.success("Guardado.")

        if st.button("⚡ Ejecutar Gasto Fijos del Mes"):
            if not df_recurrentes.empty:
                fijos_a_insertar = []
                for _, row in df_recurrentes.iterrows():
                    fijos_a_insertar.append({
                        "fecha": str(datetime.today().date()), "tipo": row['tipo'],
                        "categoria": row['categoria'], "monto": row['monto'], "descripcion": row['descripcion']
                    })
                supabase.table("transacciones").insert(fijos_a_insertar).execute()
                st.success(f"Insertados {len(fijos_a_insertar)} gastos fijos para hoy.")
