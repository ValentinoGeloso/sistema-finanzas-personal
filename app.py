import streamlit as st
from supabase import create_client, Client
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
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
def cargar_tabla(nombre_tabla):
    res = supabase.table(nombre_tabla).select("*").execute()
    return pd.DataFrame(res.data) if res.data else pd.DataFrame()

df_transacciones = cargar_tabla("transacciones")
df_categorias = cargar_tabla("categorias")
df_recurrentes = cargar_tabla("recurrentes")

if not df_transacciones.empty:
    df_transacciones['fecha'] = pd.to_datetime(df_transacciones['fecha'])
    df_transacciones['mes_año'] = df_transacciones['fecha'].dt.strftime('%Y-%m')

# --- ESTRUCTURA DE PESTAÑAS ---
st.title("📈 Sistema de Gestión Financiera")
tab1, tab2, tab3 = st.tabs(["📊 Dashboard & Proyección", "➕ Cargar Movimiento", "⚙️ Configuración"])

# ==========================================
# PESTAÑA 1: DASHBOARD Y PROYECCIONES
# ==========================================
with tab1:
    if df_transacciones.empty:
        st.info("No hay datos. Cargá tu primer movimiento en la pestaña 'Cargar Movimiento'.")
    else:
        meses_disponibles = sorted(df_transacciones['mes_año'].unique(), reverse=True)
        mes_seleccionado = st.selectbox("📅 Seleccionar Mes", meses_disponibles)
        
        df_mes = df_transacciones[df_transacciones['mes_año'] == mes_seleccionado]
        
        ingresos = df_mes[df_mes['tipo'].str.contains("Ingreso")]['monto'].sum()
        gastos = df_mes[df_mes['tipo'].str.contains("Gasto")]['monto'].sum()
        ahorro = ingresos - gastos
        
        # Tarjetas de resumen
        col1, col2, col3 = st.columns(3)
        col1.metric("Ingresos del Mes", f"${ingresos:,.2f}")
        col2.metric("Gastos del Mes", f"${gastos:,.2f}")
        col3.metric("Ahorro / Ganancia Neta", f"${ahorro:,.2f}")
        
        st.markdown("---")
        
        # Gráficos de estado actual
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Estructura de Gastos")
            df_gastos = df_mes[df_mes['tipo'].str.contains("Gasto")]
            if not df_gastos.empty:
                fig_pie = px.pie(df_gastos, values='monto', names='categoria', hole=0.4)
                st.plotly_chart(fig_pie, use_container_width=True)
        
        with c2:
            st.subheader("Evolución de Ahorro Mensual")
            df_hist = df_transacciones.copy()
            df_hist['valor'] = df_hist.apply(lambda x: x['monto'] if 'Ingreso' in x['tipo'] else -x['monto'], axis=1)
            ahorro_historico = df_hist.groupby('mes_año')['valor'].sum().reset_index()
            fig_bar = px.bar(ahorro_historico, x='mes_año', y='valor', color='valor', color_continuous_scale='RdYlGn')
            st.plotly_chart(fig_bar, use_container_width=True)

        st.markdown("---")
        
        # MOTOR DE PROYECCIONES FINANCIERAS
        st.header("🚀 Proyección de Riqueza y Ahorro")
        st.write("Calculá cuánto podrías acumular si invertís tu ahorro mensual (Ej: Fondos Comunes, CEDEARs, Cripto estable).")
        
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            ahorro_proyectado = st.number_input("Ahorro Mensual a Invertir ($)", value=float(max(ahorro, 0)), step=10000.0)
        with col_p2:
            tasa_anual = st.number_input("Tasa de Interés Anual Estimada (%)", value=40.0, step=1.0)
        
        if ahorro_proyectado > 0:
            meses_proyeccion = 60 # 5 años
            tasa_mensual = (tasa_anual / 100) / 12
            
            capital_acumulado = []
            aporte_total = []
            meses_labels = []
            
            total = 0
            aportes = 0
            for i in range(1, meses_proyeccion + 1):
                total = (total + ahorro_proyectado) * (1 + tasa_mensual)
                aportes += ahorro_proyectado
                capital_acumulado.append(total)
                aporte_total.append(aportes)
                meses_labels.append(f"Mes {i}")
                
            df_proyeccion = pd.DataFrame({
                'Mes': meses_labels,
                'Capital con Interés Compuesto': capital_acumulado,
                'Dinero Puesto por Vos': aporte_total
            })
            
            fig_proj = go.Figure()
            fig_proj.add_trace(go.Scatter(x=df_proyeccion['Mes'], y=df_proyeccion['Dinero Puesto por Vos'], fill='tozeroy', name='Aportes Totales'))
            fig_proj.add_trace(go.Scatter(x=df_proyeccion['Mes'], y=df_proyeccion['Capital con Interés Compuesto'], fill='tonexty', name='Capital Final (Interés Compuesto)'))
            st.plotly_chart(fig_proj, use_container_width=True)
            
            st.success(f"💡 Invirtiendo **${ahorro_proyectado:,.2f}** al mes con una tasa del {tasa_anual}%, en 5 años tendrías **${total:,.2f}**.")

# ==========================================
# PESTAÑA 2: CARGAR MOVIMIENTO
# ==========================================
with tab2:
    st.header("📝 Registrar Nuevo Movimiento")
    
    tipo_mov = st.selectbox("Tipo", ["Ingreso Fijo", "Ingreso Variable", "Gasto Fijo", "Gasto Variable"])
    
    # Filtrar categorías dinámicamente según el tipo
    tipo_general = "Ingreso" if "Ingreso" in tipo_mov else "Gasto"
    opciones_cat = df_categorias[df_categorias['tipo_general'] == tipo_general]['nombre'].tolist() if not df_categorias.empty else ["Sin categorías - Agregá en Configuración"]
    
    cat_mov = st.selectbox("Categoría", opciones_cat)
    monto_mov = st.number_input("Monto ($)", min_value=0.0, step=1000.0)
    desc_mov = st.text_input("Descripción (Opcional)")
    fecha_mov = st.date_input("Fecha", datetime.today())
    
    if st.button("Guardar Movimiento", type="primary"):
        nuevo = {"fecha": str(fecha_mov), "tipo": tipo_mov, "categoria": cat_mov, "monto": monto_mov, "descripcion": desc_mov}
        supabase.table("transacciones").insert(nuevo).execute()
        st.success("✅ Guardado exitosamente. Recargá la página para actualizar gráficos.")

# ==========================================
# PESTAÑA 3: CONFIGURACIÓN
# ==========================================
with tab3:
    st.header("⚙️ Administrar Sistema")
    
    col_conf1, col_conf2 = st.columns(2)
    
    # --- GESTIÓN DE CATEGORÍAS ---
    with col_conf1:
        st.subheader("1. Categorías")
        with st.expander("➕ Agregar Categoría"):
            nuevo_tipo_cat = st.selectbox("Tipo de Categoría", ["Ingreso", "Gasto"])
            nuevo_nom_cat = st.text_input("Nombre de la Categoría")
            if st.button("Guardar Categoría"):
                supabase.table("categorias").insert({"tipo_general": nuevo_tipo_cat, "nombre": nuevo_nom_cat}).execute()
                st.success("Agregada. Recargá la página.")
                
        with st.expander("🗑️ Borrar Categoría"):
            if not df_categorias.empty:
                cat_a_borrar = st.selectbox("Seleccionar para borrar", df_categorias['nombre'].tolist())
                if st.button("Borrar Seleccionada"):
                    supabase.table("categorias").delete().eq("nombre", cat_a_borrar).execute()
                    st.success("Borrada. Recargá la página.")
                    
    # --- GESTIÓN DE FIJOS AUTOMÁTICOS ---
    with col_conf2:
        st.subheader("2. Automatización de Fijos")
        st.write("Definí tus ingresos y gastos fijos para cargarlos todos juntos con un clic al inicio del mes.")
        
        with st.expander("➕ Crear Plantilla de Fijo"):
            f_tipo = st.selectbox("Tipo Fijo", ["Ingreso Fijo", "Gasto Fijo"])
            f_cat = st.selectbox("Categoría Fija", opciones_cat)
            f_monto = st.number_input("Monto Base ($)", min_value=0.0, step=1000.0)
            f_desc = st.text_input("Descripción Fija")
            if st.button("Guardar Plantilla"):
                supabase.table("recurrentes").insert({"tipo": f_tipo, "categoria": f_cat, "monto": f_monto, "descripcion": f_desc}).execute()
                st.success("Plantilla guardada. Recargá la página.")
        
        st.markdown("---")
        st.info("⬇️ Hacé clic acá el primer día del mes para insertar todos tus fijos.")
        if st.button("⚡ CARGAR FIJOS DEL MES ACTUAL", type="primary", use_container_width=True):
            if not df_recurrentes.empty:
                fijos_a_insertar = []
                for _, row in df_recurrentes.iterrows():
                    fijos_a_insertar.append({
                        "fecha": str(datetime.today().date()),
                        "tipo": row['tipo'],
                        "categoria": row['categoria'],
                        "monto": row['monto'],
                        "descripcion": row['descripcion']
                    })
                supabase.table("transacciones").insert(fijos_a_insertar).execute()
                st.success(f"✅ Se insertaron {len(fijos_a_insertar)} movimientos fijos exitosamente.")
            else:
                st.warning("No tenés movimientos fijos configurados.")
