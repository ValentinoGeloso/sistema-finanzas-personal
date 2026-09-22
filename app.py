import streamlit as st
from supabase import create_client, Client
import pandas as pd
import plotly.express as px
from datetime import datetime

# 1. Configuración de la página
st.set_page_config(page_title="Sistema de Finanzas", page_icon="💰", layout="wide")
st.title("📊 Mi Panel Financiero")

# 2. Conexión a Supabase usando los Secretos de Streamlit
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase = init_connection()
except Exception as e:
    st.error("Error conectando a Supabase. Revisá tus credenciales.")
    st.stop()

# 3. Panel Lateral: Formulario de Ingreso de Datos (Ideal para el celular)
with st.sidebar:
    st.header("📝 Nueva Transacción")
    
    tipo = st.selectbox("Tipo de Movimiento", ["Ingreso Fijo", "Ingreso Variable", "Gasto Fijo", "Gasto Variable"])
    
    # Categorías dinámicas según el tipo
    if "Ingreso" in tipo:
        categoria = st.selectbox("Categoría", ["Consultorio", "Arbitraje", "Transferencias", "Otros"])
    else:
        categoria = st.selectbox("Categoría", ["Supermercado", "Mantenimiento Corsa", "Gata/Mascotas", "Salidas/Comida", "Servicios", "Otros"])
        
    monto = st.number_input("Monto ($)", min_value=0.0, step=1000.0)
    descripcion = st.text_input("Descripción (Opcional)")
    fecha = st.date_input("Fecha", datetime.today())
    
    if st.button("Guardar Transacción"):
        if monto > 0:
            nueva_transaccion = {
                "fecha": str(fecha),
                "tipo": tipo,
                "categoria": categoria,
                "monto": monto,
                "descripcion": descripcion
            }
            # Insertar en Supabase
            supabase.table("transacciones").insert(nueva_transaccion).execute()
            st.success("✅ ¡Guardado exitosamente!")
        else:
            st.warning("El monto debe ser mayor a 0.")

# 4. Obtener y Procesar Datos
def cargar_datos():
    respuesta = supabase.table("transacciones").select("*").execute()
    datos = respuesta.data
    if datos:
        df = pd.DataFrame(datos)
        df['fecha'] = pd.to_datetime(df['fecha'])
        df['mes_año'] = df['fecha'].dt.strftime('%Y-%m')
        return df
    return pd.DataFrame()

df = cargar_datos()

# 5. Dashboard y Gráficos (Solo se muestran si hay datos)
if not df.empty:
    st.markdown("---")
    
    # Filtro por mes
    meses_disponibles = sorted(df['mes_año'].unique(), reverse=True)
    mes_seleccionado = st.selectbox("Seleccionar Mes", meses_disponibles)
    
    # Filtrar el dataframe por el mes seleccionado
    df_mes = df[df['mes_año'] == mes_seleccionado]
    
    # Cálculos clave
    ingresos = df_mes[df_mes['tipo'].str.contains("Ingreso")]['monto'].sum()
    gastos = df_mes[df_mes['tipo'].str.contains("Gasto")]['monto'].sum()
    ahorro = ingresos - gastos
    
    # Mostrar Tarjetas de Resumen
    col1, col2, col3 = st.columns(3)
    col1.metric("Ingresos del Mes", f"${ingresos:,.2f}")
    col2.metric("Gastos del Mes", f"${gastos:,.2f}")
    col3.metric("Ahorro / Ganancia Neta", f"${ahorro:,.2f}")
    
    st.markdown("---")
    
    # Gráficos interactivos en dos columnas
    col_graf1, col_graf2 = st.columns(2)
    
    with col_graf1:
        st.subheader("Distribución de Gastos")
        df_gastos = df_mes[df_mes['tipo'].str.contains("Gasto")]
        if not df_gastos.empty:
            fig_gastos = px.pie(df_gastos, values='monto', names='categoria', hole=0.4)
            st.plotly_chart(fig_gastos, use_container_width=True)
        else:
            st.info("No hay gastos registrados este mes.")
            
    with col_graf2:
        st.subheader("Evolución Mes a Mes")
        # Agrupar todo el historial por mes y tipo
        df_historico = df.groupby(['mes_año', 'tipo'])['monto'].sum().reset_index()
        # Simplificar a Ingreso vs Gasto para el gráfico
        df_historico['Categoria General'] = df_historico['tipo'].apply(lambda x: 'Ingreso' if 'Ingreso' in x else 'Gasto')
        df_historico_agrupado = df_historico.groupby(['mes_año', 'Categoria General'])['monto'].sum().reset_index()
        
        fig_hist = px.bar(df_historico_agrupado, x='mes_año', y='monto', color='Categoria General', barmode='group')
        st.plotly_chart(fig_hist, use_container_width=True)

    # Tabla de movimientos recientes
    st.subheader("Últimos Movimientos")
    st.dataframe(df_mes[['fecha', 'tipo', 'categoria', 'descripcion', 'monto']].sort_values(by='fecha', ascending=False), use_container_width=True)

else:
    st.info("Aún no hay transacciones registradas. Cargá tu primer movimiento desde el menú lateral.")
