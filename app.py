import calendar
from datetime import date, datetime, timedelta
import time
import pandas as pd
import plotly.express as px
import streamlit as st
from supabase import create_client

st.set_page_config(page_title="Finanzas Pro", page_icon="📈", layout="wide")


# --- CONEXIÓN A SUPABASE ---
@st.cache_resource
def init_connection():
  return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


try:
  supabase = init_connection()
except Exception as e:
  st.error(
      "Error conectando a Supabase. Verificá tus secretos en Streamlit Cloud."
  )
  st.stop()


# --- ESTADOS DE SESIÓN PARA CONFIGURACIONES LOCALES ---
if "aaa_mes_cobro_custom" not in st.session_state:
    st.session_state.aaa_mes_cobro_custom = {}


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


def sumar_meses(fecha_base, cantidad_meses):
  year = fecha_base.year
  month = fecha_base.month + cantidad_meses - 1
  year += month // 12
  month = (month % 12) + 1
  max_days = calendar.monthrange(year, month)[1]
  return date(year, month, min(fecha_base.day, max_days))


# --- CARGA ROBUSTA DE DATOS ---
def cargar_tabla(nombre_tabla, order_by="id", desc=False):
  for intento in range(3):
    try:
      res = (
          supabase.table(nombre_tabla)
          .select("*")
          .order(order_by, desc=desc)
          .execute()
      )
      return pd.DataFrame(res.data) if res.data else pd.DataFrame()
    except Exception:
      time.sleep(0.5)
  return pd.DataFrame()


df_transacciones = cargar_tabla("transacciones", order_by="fecha", desc=True)
df_categorias = cargar_tabla("categorias")
df_partidos_aaa = cargar_tabla("partidos_aaa", order_by="fecha", desc=True)
df_metas = cargar_tabla("metas_ahorro")
df_vencimientos = cargar_tabla("vencimientos", order_by="fecha_vencimiento")
df_deudas = cargar_tabla("deudas", order_by="id", desc=True)
df_recurrentes = cargar_tabla("recurrentes")

if not df_recurrentes.empty and "frecuencia_meses" not in df_recurrentes.columns:
    df_recurrentes["frecuencia_meses"] = 1

# --- PROCESAMIENTO DE TRANSACCIONES REALES ---
if (
    not df_transacciones.empty
    and "tipo" in df_transacciones.columns
    and "fecha" in df_transacciones.columns
):
  df_transacciones["fecha"] = pd.to_datetime(
      df_transacciones["fecha"]
  ).dt.date
  df_transacciones["mes_año"] = pd.to_datetime(
      df_transacciones["fecha"]
  ).dt.strftime("%Y-%m")
  df_transacciones["tipo_general"] = df_transacciones["tipo"].apply(
      lambda x: "Ingreso" if "Ingreso" in str(x) else "Gasto"
  )
else:
  df_transacciones = pd.DataFrame(
      columns=[
          "id",
          "fecha",
          "tipo",
          "categoria",
          "monto",
          "descripcion",
          "mes_año",
          "tipo_general",
      ]
  )

# --- PROCESAMIENTO DE DEUDAS ---
if not df_deudas.empty:
  if "fecha_pago" in df_deudas.columns and df_deudas["fecha_pago"].notna().any():
    df_deudas["fecha_pago"] = pd.to_datetime(df_deudas["fecha_pago"]).dt.date
    df_deudas["mes_año"] = pd.to_datetime(df_deudas["fecha_pago"]).dt.strftime(
        "%Y-%m"
    )
  else:
    df_deudas["fecha_pago"] = date.today()
    df_deudas["mes_año"] = date.today().strftime("%Y-%m")
else:
  df_deudas = pd.DataFrame(
      columns=[
          "id",
          "persona",
          "tipo",
          "monto",
          "detalle",
          "estado",
          "fecha_pago",
          "mes_año",
      ]
  )


# --- FUNCIÓN DE PROYECCIÓN DE RECURRENTES (CON FRECUENCIA) ---
def obtener_recurrentes_para_mes(año, mes):
  if df_recurrentes.empty:
    return pd.DataFrame()

  inicio_mes = date(año, mes, 1)
  ultimo_dia_mes = calendar.monthrange(año, mes)[1]
  fin_mes = date(año, mes, ultimo_dia_mes)

  recurrentes_validos = []
  for _, row in df_recurrentes.iterrows():
    f_ini = (
        pd.to_datetime(row["fecha_inicio"]).date()
        if pd.notna(row.get("fecha_inicio"))
        else date(2024, 1, 1)
    )
    f_fin = (
        pd.to_datetime(row["fecha_fin"]).date()
        if pd.notna(row.get("fecha_fin"))
        else None
    )
    
    frec = int(row.get("frecuencia_meses", 1)) if pd.notna(row.get("frecuencia_meses")) else 1
    meses_diff = (año - f_ini.year) * 12 + (mes - f_ini.month)

    if f_ini <= fin_mes and (f_fin is None or f_fin >= inicio_mes):
      if meses_diff >= 0 and (meses_diff % frec) == 0:
        dia_m = int(row["dia_mes"]) if pd.notna(row.get("dia_mes")) else 1
        dia_real = min(dia_m, ultimo_dia_mes)
        fecha_evento = date(año, mes, dia_real)

        c_tot = (
            int(row["cuotas_totales"])
            if pd.notna(row.get("cuotas_totales"))
            else None
        )

        desc_base = str(row.get("descripcion", ""))
        if c_tot and c_tot > 0:
          desc_final = f"{desc_base} (Cuota en plan de {c_tot})"
        else:
          if frec > 1:
            desc_final = f"{desc_base} (Fijo - Cada {frec} meses)" if desc_base else "Fijo Proyectado"
          else:
            desc_final = f"{desc_base} (Fijo)" if desc_base else "Fijo Proyectado"

        recurrentes_validos.append({
            "id_recurrente": row["id"],
            "fecha": fecha_evento,
            "tipo": row["tipo"],
            "categoria": row["categoria"],
            "monto": float(row["monto"]),
            "descripcion": desc_final,
            "mes_año": f"{año}-{mes:02d}",
            "tipo_general": (
                "Ingreso" if "Ingreso" in str(row["tipo"]) else "Gasto"
            ),
            "es_proyectado": True,
        })
  return pd.DataFrame(recurrentes_validos)


# --- CÁLCULO DE VENCIMIENTOS (CON FRECUENCIA BIMESTRAL/ETC) ---
def calcular_vencimientos_fijos(hoy=None):
  if hoy is None:
    hoy = date.today()

  if df_recurrentes.empty:
    return []

  vencimientos_info = []
  gastos_fijos = (
      df_recurrentes[df_recurrentes["tipo"].str.contains("Gasto", na=False)]
      if "tipo" in df_recurrentes.columns
      else df_recurrentes
  )

  for _, row in gastos_fijos.iterrows():
    dia_m = int(row.get("dia_mes", 1)) if pd.notna(row.get("dia_mes")) else 1
    cat = str(row["categoria"])
    monto = float(row["monto"])
    desc = str(row.get("descripcion", ""))
    id_rec = row["id"]
    frec = int(row.get("frecuencia_meses", 1)) if pd.notna(row.get("frecuencia_meses")) else 1

    c_tot = (
        int(row["cuotas_totales"])
        if pd.notna(row.get("cuotas_totales"))
        else None
    )
    c_pag = (
        int(row["cuotas_pagadas"])
        if pd.notna(row.get("cuotas_pagadas"))
        else 0
    )

    f_ini = (
        pd.to_datetime(row["fecha_inicio"]).date()
        if pd.notna(row.get("fecha_inicio"))
        else date(2024, 1, 1)
    )
    f_fin = (
        pd.to_datetime(row["fecha_fin"]).date()
        if pd.notna(row.get("fecha_fin"))
        else None
    )

    cur_year = hoy.year
    cur_month = hoy.month

    # Buscar el ciclo de facturación actual según la frecuencia
    meses_diff = (cur_year - f_ini.year) * 12 + (cur_month - f_ini.month)
    if meses_diff < 0:
        cy = f_ini.year
        cm = f_ini.month
    else:
        resto = meses_diff % frec
        if resto == 0:
            cy = cur_year
            cm = cur_month
        else:
            meses_falt = frec - resto
            cy = cur_year + (cur_month + meses_falt - 1) // 12
            cm = (cur_month + meses_falt - 1) % 12 + 1

    max_days = calendar.monthrange(cy, cm)[1]
    due_date_curr = date(cy, cm, min(dia_m, max_days))

    if f_fin and due_date_curr > f_fin:
      continue

    mes_str_curr = f"{cy}-{cm:02d}"

    pagado_este_mes = False
    if not df_transacciones.empty and "mes_año" in df_transacciones.columns:
      df_pagado = df_transacciones[
          (df_transacciones["mes_año"] == mes_str_curr)
          & (df_transacciones["categoria"] == cat)
          & (df_transacciones["tipo_general"] == "Gasto")
      ]
      if not df_pagado.empty:
        pagado_este_mes = True

    cuota_txt = f" (Cuota {c_pag + 1}/{c_tot})" if c_tot else ""

    if not pagado_este_mes:
      dias_restantes = (due_date_curr - hoy).days
      vencimientos_info.append({
          "id_recurrente": id_rec,
          "categoria": cat,
          "monto": monto,
          "fecha_vencimiento": due_date_curr,
          "dias_restantes": dias_restantes,
          "descripcion": f"{desc}{cuota_txt}",
          "mes_año": mes_str_curr,
          "estado_pago": "Pendiente",
          "cuotas_totales": c_tot,
          "cuotas_pagadas": c_pag,
      })
    else:
      ny = cy + (cm + frec - 1) // 12
      nm = (cm + frec - 1) % 12 + 1
      max_days_next = calendar.monthrange(ny, nm)[1]
      due_date_next = date(ny, nm, min(dia_m, max_days_next))
      mes_str_next = f"{ny}-{nm:02d}"
      
      if f_fin and due_date_next > f_fin:
          continue
          
      dias_restantes = (due_date_next - hoy).days
      next_cuota_txt = f" (Cuota {c_pag + 1}/{c_tot})" if c_tot else ""
      vencimientos_info.append({
          "id_recurrente": id_rec,
          "categoria": cat,
          "monto": monto,
          "fecha_vencimiento": due_date_next,
          "dias_restantes": dias_restantes,
          "descripcion": f"{desc}{next_cuota_txt}",
          "mes_año": mes_str_next,
          "estado_pago": "Pagado este mes",
          "cuotas_totales": c_tot,
          "cuotas_pagadas": c_pag,
      })

  vencimientos_info.sort(key=lambda x: x["fecha_vencimiento"])
  return vencimientos_info


lista_todas_categorias = (
    df_categorias["nombre"].tolist()
    if not df_categorias.empty and "nombre" in df_categorias.columns
    else ["General"]
)

# --- ESTRUCTURA DE PESTAÑAS ---
st.title("📈 Mi Ecosistema Financiero Pro")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Dashboards & Proyección",
    "➕ Carga Rápida",
    "💼 Automatizaciones",
    "🎯 Metas, Vencimientos & Cuotas",
    "📝 Historial & Excel",
    "⚙️ Fijos y Configuración",
])

# ==========================================
# PESTAÑA 1: DASHBOARDS Y PROYECCIÓN FUTURA
# ==========================================
with tab1:
  hoy = date.today()
  
  col_tit1, col_tit2, col_tit3 = st.columns([1, 1, 2])
  with col_tit1:
      año_sel = st.number_input("📅 Año", min_value=2020, max_value=2100, value=hoy.year, step=1, key="tab1_anio_sel")
  with col_tit2:
      meses_lista = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
      mes_sel_nombre = st.selectbox("📆 Mes", meses_lista, index=hoy.month - 1, key="tab1_mes_sel")
      mes_sel = meses_lista.index(mes_sel_nombre) + 1

  mes_seleccionado = f"{año_sel}-{mes_sel:02d}"
  
  with col_tit3:
      st.markdown("<br>", unsafe_allow_html=True)
      st.markdown(f"### 📊 Mostrando proyecciones para: **{mes_sel_nombre} {año_sel}**")

  st.markdown("---")

  # --- PREPARACIÓN DE DATOS ---
  df_mes_real = (
      df_transacciones[df_transacciones["mes_año"] == mes_seleccionado]
      if not df_transacciones.empty
      else pd.DataFrame()
  )

  df_mes_fijos = obtener_recurrentes_para_mes(año_sel, mes_sel)

  df_fijos_pendientes = pd.DataFrame()
  if not df_mes_fijos.empty:
    if not df_mes_real.empty:
      cats_reales = df_mes_real["categoria"].unique()
      df_fijos_pendientes = df_mes_fijos[~df_mes_fijos["categoria"].isin(cats_reales)]
    else:
      df_fijos_pendientes = df_mes_fijos.copy()

  # --- CÁLCULO DE INGRESOS ---
  ingresos_reales = df_mes_real[df_mes_real["tipo_general"] == "Ingreso"]["monto"].sum() if not df_mes_real.empty else 0.0
  ingresos_fijos_pend = df_fijos_pendientes[df_fijos_pendientes["tipo_general"] == "Ingreso"]["monto"].sum() if not df_fijos_pendientes.empty else 0.0
  
  cobrar_pend_mes = 0.0
  if not df_deudas.empty and "mes_año" in df_deudas.columns:
    cobrar_pend_mes = df_deudas[(df_deudas["mes_año"] == mes_seleccionado) & (df_deudas["tipo"] == "Me deben") & (df_deudas["estado"] == "Pendiente")]["monto"].sum()

  # CÁLCULO DE AAA PENDIENTE USANDO FECHA PREDETERMINADA (PRIMER VIERNES DEL MES SIGUIENTE)
  aaa_pend = 0.0
  df_aaa_este_mes = pd.DataFrame()
  if not df_partidos_aaa.empty and "estado" in df_partidos_aaa.columns:
      df_aaa_pend = df_partidos_aaa[df_partidos_aaa["estado"] == "Pendiente"].copy()
      if not df_aaa_pend.empty:
          for _, r_aaa in df_aaa_pend.iterrows():
              p_id = r_aaa["id"]
              if p_id not in st.session_state.aaa_mes_cobro_custom:
                  f_partido = pd.to_datetime(r_aaa["fecha"]).date()
                  f_cobro_def = primer_viernes_mes_siguiente(f_partido)
                  st.session_state.aaa_mes_cobro_custom[p_id] = f"{f_cobro_def.year}-{f_cobro_def.month:02d}"

          def calcular_mes_cobro_aaa(row):
              return st.session_state.aaa_mes_cobro_custom.get(row["id"])
          
          df_aaa_pend["mes_cobro_estimado"] = df_aaa_pend.apply(calcular_mes_cobro_aaa, axis=1)
          df_aaa_este_mes = df_aaa_pend[df_aaa_pend["mes_cobro_estimado"] == mes_seleccionado]
          if not df_aaa_este_mes.empty:
              bruto_aaa_mes = df_aaa_este_mes["monto"].sum()
              aaa_pend = max(0, bruto_aaa_mes - 15000)

  ingresos_pendientes = ingresos_fijos_pend + cobrar_pend_mes + aaa_pend
  proyeccion_ingresos = ingresos_reales + ingresos_pendientes

  # --- CÁLCULO DE GASTOS ---
  gastos_reales = df_mes_real[df_mes_real["tipo_general"] == "Gasto"]["monto"].sum() if not df_mes_real.empty else 0.0
  gastos_fijos_pend = df_fijos_pendientes[df_fijos_pendientes["tipo_general"] == "Gasto"]["monto"].sum() if not df_fijos_pendientes.empty else 0.0
  
  deudas_pend_mes = 0.0
  if not df_deudas.empty and "mes_año" in df_deudas.columns:
    deudas_pend_mes = df_deudas[(df_deudas["mes_año"] == mes_seleccionado) & (df_deudas["tipo"] == "Debo") & (df_deudas["estado"] == "Pendiente")]["monto"].sum()

  venc_pend = 0.0
  if not df_vencimientos.empty and "estado" in df_vencimientos.columns:
      mes_año_v = pd.to_datetime(df_vencimientos["fecha_vencimiento"]).dt.strftime("%Y-%m")
      venc_pend = df_vencimientos[(mes_año_v == mes_seleccionado) & (df_vencimientos["estado"] == "Pendiente")]["monto"].sum()

  gastos_pendientes = gastos_fijos_pend + deudas_pend_mes + venc_pend
  proyeccion_gastos = gastos_reales + gastos_pendientes

  # --- SALDO TOTAL ---
  proyeccion_total = proyeccion_ingresos - proyeccion_gastos

  # --- INTERFAZ DEL DASHBOARD ---
  st.markdown("### 🟢 1. Proyección de Ingresos")
  c_i1, c_i2, c_i3 = st.columns(3)
  c_i1.metric("Ingresos Actuales (En mano)", f"${ingresos_reales:,.2f}")
  c_i2.metric("Ingresos Pendientes (A cobrar)", f"${ingresos_pendientes:,.2f}", help="Suma de fijos pendientes, arbitraje AAA que se cobra este mes y cuentas que te deben.")
  c_i3.metric("Total Proyección Ingresos", f"${proyeccion_ingresos:,.2f}")

  # --- EXPANDER PARA AUDITAR DE DÓNDE SALEN LOS INGRESOS PENDIENTES ---
  with st.expander("🔍 Ver de dónde salen estos Ingresos Pendientes (Detalle)"):
      df_fijos_ing_pend = df_fijos_pendientes[df_fijos_pendientes["tipo_general"] == "Ingreso"] if not df_fijos_pendientes.empty else pd.DataFrame()
      if not df_fijos_ing_pend.empty:
          st.markdown("##### 📅 Ingresos Fijos / Recurrentes Pendientes:")
          st.dataframe(df_fijos_ing_pend[["categoria", "descripcion", "monto"]], hide_index=True, use_container_width=True)
      
      df_cobrar_mes = pd.DataFrame()
      if not df_deudas.empty and "mes_año" in df_deudas.columns:
          df_cobrar_mes = df_deudas[(df_deudas["mes_año"] == mes_seleccionado) & (df_deudas["tipo"] == "Me deben") & (df_deudas["estado"] == "Pendiente")]
      if not df_cobrar_mes.empty:
          st.markdown("##### 📩 Cuentas por Cobrar ('Me deben'):")
          st.dataframe(df_cobrar_mes[["persona", "detalle", "monto"]], hide_index=True, use_container_width=True)

      if not df_aaa_este_mes.empty:
          st.markdown(f"##### ⚽ Partidos AAA a cobrar este mes (Bruto: ${df_aaa_este_mes['monto'].sum():,.2f} - Cuota AAA: $15,000 = Neto: ${aaa_pend:,.2f}):")
          cols_mostrar = [c for c in ["fecha", "detalle", "monto"] if c in df_aaa_este_mes.columns]
          st.dataframe(df_aaa_este_mes[cols_mostrar], hide_index=True, use_container_width=True)
          
      if df_fijos_ing_pend.empty and df_cobrar_mes.empty and df_aaa_este_mes.empty:
          st.info("No hay ingresos pendientes registrados para este mes.")

  st.markdown("### 🔴 2. Proyección de Gastos")
  c_g1, c_g2, c_g3 = st.columns(3)
  c_g1.metric("Gastos (Pagados)", f"${gastos_reales:,.2f}")
  c_g2.metric("Gastos Pendientes (A pagar)", f"${gastos_pendientes:,.2f}", help="Suma de fijos pendientes, cuotas, deudas y vencimientos eventuales.")
  c_g3.metric("Total Proyección Gastos", f"${proyeccion_gastos:,.2f}")

  # --- EXPANDER PARA AUDITAR DE DÓNDE SALEN LOS GASTOS PENDIENTES ---
  with st.expander("🔍 Ver de dónde salen estos Gastos Pendientes (Detalle)"):
      df_fijos_gast_pend = df_fijos_pendientes[df_fijos_pendientes["tipo_general"] == "Gasto"] if not df_fijos_pendientes.empty else pd.DataFrame()
      if not df_fijos_gast_pend.empty:
          st.markdown("##### 📅 Gastos Fijos / Recurrentes Pendientes:")
          st.dataframe(df_fijos_gast_pend[["categoria", "descripcion", "monto"]], hide_index=True, use_container_width=True)
      
      df_debo_mes = pd.DataFrame()
      if not df_deudas.empty and "mes_año" in df_deudas.columns:
          df_debo_mes = df_deudas[(df_deudas["mes_año"] == mes_seleccionado) & (df_deudas["tipo"] == "Debo") & (df_deudas["estado"] == "Pendiente")]
      if not df_debo_mes.empty:
          st.markdown("##### 💳 Cuentas por Pagar ('Debo'):")
          st.dataframe(df_debo_mes[["persona", "detalle", "monto"]], hide_index=True, use_container_width=True)

      df_venc_mes = pd.DataFrame()
      if not df_vencimientos.empty and "estado" in df_vencimientos.columns:
          mes_año_v = pd.to_datetime(df_vencimientos["fecha_vencimiento"]).dt.strftime("%Y-%m")
          df_venc_mes = df_vencimientos[(mes_año_v == mes_seleccionado) & (df_vencimientos["estado"] == "Pendiente")]
      if not df_venc_mes.empty:
          st.markdown("##### 🔔 Vencimientos Eventuales Pendientes:")
          st.dataframe(df_venc_mes[["concepto", "fecha_vencimiento", "monto"]], hide_index=True, use_container_width=True)

      if df_fijos_gast_pend.empty and df_debo_mes.empty and df_venc_mes.empty:
          st.info("No hay gastos pendientes registrados para este mes.")

  st.markdown("---")
  st.markdown("### 💎 3. Proyección Total (Saldo Final)")
  c_r1, c_r2 = st.columns(2)
  if proyeccion_total >= 0:
      c_r1.success(f"**Proyección Ingresos - Proyección Gastos = ${proyeccion_total:,.2f}**")
  else:
      c_r1.error(f"**Proyección Ingresos - Proyección Gastos = ${proyeccion_total:,.2f}**")
      
  if proyeccion_ingresos > 0:
      c_r2.info(f"🎯 **Ahorro Estimado:** {((proyeccion_total/proyeccion_ingresos)*100):.1f}%")

  st.markdown("---")
  
  # --- COMPOSICIÓN GRÁFICA ---
  if not df_mes_real.empty and not df_fijos_pendientes.empty:
    df_mes_combinado = pd.concat([df_mes_real, df_fijos_pendientes], ignore_index=True)
  elif not df_mes_real.empty:
    df_mes_combinado = df_mes_real.copy()
  else:
    df_mes_combinado = df_fijos_pendientes.copy()

  col_g1, col_g2 = st.columns(2)
  with col_g1:
    st.subheader(f"Distribución de Categorías")
    if not df_mes_combinado.empty:
      fig_hist = px.bar(
          df_mes_combinado,
          x="categoria",
          y="monto",
          color="tipo_general",
          barmode="group",
          color_discrete_map={"Ingreso": "#2ecc71", "Gasto": "#e74c3c"},
      )
      st.plotly_chart(fig_hist, use_container_width=True)
    else:
      st.info("No hay datos ni fijos cargados para este mes.")

  with col_g2:
    st.subheader("Desglose de Gastos Proyectados")
    if not df_mes_combinado.empty:
      df_gastos_pie = df_mes_combinado[
          df_mes_combinado["tipo_general"] == "Gasto"
      ]
      if not df_gastos_pie.empty:
        fig_gastos = px.pie(
            df_gastos_pie, names="categoria", values="monto", hole=0.4
        )
        st.plotly_chart(fig_gastos, use_container_width=True)

# ==========================================
# PESTAÑA 2: CARGA RÁPIDA
# ==========================================
with tab2:
  st.header("📝 Carga Rápida de Operaciones")

  with st.expander("➕ ¿Querés crear una nueva Categoría para usar ahora?"):
    col_nc1, col_nc2, col_nc3, col_nc4 = st.columns([1.5, 1, 1, 1])
    with col_nc1:
      nc_nombre = st.text_input(
          "Nombre de la Categoría", key="tab2_exp_nc_nombre"
      )
    with col_nc2:
      nc_tipo = st.selectbox(
          "Tipo", ["Gasto", "Ingreso"], key="tab2_exp_nc_tipo"
      )
    with col_nc3:
      nc_clase = st.selectbox(
          "Clasificación 50/30/20",
          ["50-Necesidad", "30-Deseo", "Ingreso", "Ahorro/Inversión"],
          key="tab2_exp_nc_clase",
      )
    with col_nc4:
      st.write(" ")
      st.write(" ")
      if st.button("💾 Crear Categoría", key="tab2_btn_crear_cat_exp"):
        if nc_nombre.strip():
          try:
            supabase.table("categorias").insert({
                "nombre": nc_nombre.strip(),
                "tipo_general": nc_tipo,
                "clase_503020": nc_clase,
                "limite_mensual": 0,
            }).execute()
            recargar_app(f"Categoría '{nc_nombre.strip()}' creada con éxito.")
          except Exception as e:
            st.error(f"Error al crear categoría: {e}")
        else:
          st.warning("Escribí el nombre de la categoría.")

  st.markdown("---")

  sub_tab2 = st.radio(
      "¿Qué querés cargar?",
      [
          "💸 Registrar Pago / Movimiento Puntual",
          "📅 Configurar Nuevo Gasto / Ingreso Fijo",
          "🚗 Configurar Gasto en Cuotas (Auto, Electro, etc.)",
      ],
      horizontal=True,
      key="tab2_sub_option",
  )

  # -----------------------------------------------
  # OPCIÓN A: REGISTRAR UN PAGO / MOVIMIENTO PUNTUAL
  # -----------------------------------------------
  if "Pago / Movimiento Puntual" in sub_tab2:
    st.subheader("💸 Registrar Transacción Realizada")
    st.caption("Guarda el movimiento efectuado en la fecha seleccionada.")

    tipo_mov = st.selectbox(
        "Tipo de Movimiento",
        [
            "Gasto Variable",
            "Ingreso Variable",
            "Gasto Fijo (Pago del mes)",
            "Ingreso Fijo (Cobro del mes)",
        ],
        key="tab2_tipo_mov",
    )
    tipo_general = "Ingreso" if "Ingreso" in tipo_mov else "Gasto"

    opciones_cat = (
        df_categorias[df_categorias["tipo_general"] == tipo_general][
            "nombre"
        ].tolist()
        if not df_categorias.empty and "tipo_general" in df_categorias.columns
        else []
    )
    opciones_cat_select = ["➕ [ Crear nueva categoría... ]"] + opciones_cat

    cat_mov_sel = st.selectbox(
        "Categoría", opciones_cat_select, key="tab2_cat_mov_sel"
    )

    if cat_mov_sel == "➕ [ Crear nueva categoría... ]":
      col_ncat1, col_ncat2 = st.columns([2, 1])
      with col_ncat1:
        cat_mov = st.text_input(
            "Escribí el nombre de la nueva categoría:", key="tab2_custom_cat_a"
        )
      with col_ncat2:
        clase_custom = st.selectbox(
            "Clasificación 50/30/20",
            ["50-Necesidad", "30-Deseo", "Ingreso", "Ahorro/Inversión"],
            key="tab2_custom_clase_a",
        )
      es_nueva_cat = True
    else:
      cat_mov = cat_mov_sel
      es_nueva_cat = False

    monto_mov = st.number_input(
        "Monto ($)", min_value=0.0, step=1000.0, key="tab2_monto_mov"
    )
    fecha_mov = st.date_input(
        "Fecha Efectiva", datetime.today(), key="tab2_fecha_mov"
    )
    desc_mov = st.text_input(
        "Descripción (Ej: Nafta, Coto, Pago Luz...)", key="tab2_desc_mov"
    )

    if st.button("Guardar Movimiento", type="primary", key="tab2_btn_guardar"):
      if monto_mov > 0 and cat_mov.strip():
        try:
          if es_nueva_cat:
            cat_nombre_clean = cat_mov.strip()
            existe_cat = False
            if not df_categorias.empty and "nombre" in df_categorias.columns:
              existe_cat = cat_nombre_clean in df_categorias["nombre"].values

            if not existe_cat:
              supabase.table("categorias").insert({
                  "nombre": cat_nombre_clean,
                  "tipo_general": tipo_general,
                  "clase_503020": clase_custom,
                  "limite_mensual": 0,
              }).execute()
            cat_mov = cat_nombre_clean

          supabase.table("transacciones").insert({
              "fecha": str(fecha_mov),
              "tipo": tipo_mov,
              "categoria": cat_mov,
              "monto": monto_mov,
              "descripcion": desc_mov,
          }).execute()
          recargar_app("Movimiento registrado en el historial.")
        except Exception as e:
          st.error(f"Error al guardar movimiento: {e}")
      else:
        if not cat_mov.strip():
          st.warning("Escribí el nombre de la categoría.")
        else:
          st.warning("El monto debe ser mayor a 0.")

  # -----------------------------------------------
  # OPCIÓN B: CONFIGURAR REGLA FIJA RECURRENTE (Con Frecuencia)
  # -----------------------------------------------
  elif "Ingreso Fijo" in sub_tab2:
    st.subheader("📅 Configurar Regla Fija Recurrente")
    st.caption(
        "Esta carga **NO marca el pago como hecho**, sino que establece el día"
        " de vencimiento para que se proyecte al futuro."
    )

    r_tipo = st.selectbox(
        "Tipo de Fijo",
        ["Gasto Fijo", "Ingreso Fijo"],
        key="tab2_r_tipo",
    )
    tipo_gen_r = "Ingreso" if "Ingreso" in r_tipo else "Gasto"

    opciones_cat_r = (
        df_categorias[df_categorias["tipo_general"] == tipo_gen_r][
            "nombre"
        ].tolist()
        if not df_categorias.empty and "tipo_general" in df_categorias.columns
        else []
    )
    opciones_cat_r_select = ["➕ [ Crear nueva categoría... ]"] + opciones_cat_r

    r_cat_sel = st.selectbox(
        "Categoría", opciones_cat_r_select, key="tab2_r_cat_sel"
    )

    if r_cat_sel == "➕ [ Crear nueva categoría... ]":
      col_nr1, col_nr2 = st.columns([2, 1])
      with col_nr1:
        r_cat = st.text_input(
            "Escribí el nombre de la nueva categoría:", key="tab2_custom_cat_b"
        )
      with col_nr2:
        r_clase_custom = st.selectbox(
            "Clasificación 50/30/20",
            ["50-Necesidad", "30-Deseo", "Ingreso", "Ahorro/Inversión"],
            key="tab2_custom_clase_b",
        )
      r_es_nueva_cat = True
    else:
      r_cat = r_cat_sel
      r_es_nueva_cat = False

    col_rm1, col_rm2 = st.columns(2)
    with col_rm1:
      r_monto = st.number_input(
          "Monto ($)", min_value=0.0, step=1000.0, key="tab2_r_monto"
      )
    with col_rm2:
      opciones_frec = {
          "Mensual (Todos los meses)": 1,
          "Bimestral (Ej: Patente, 1 cada 2 meses)": 2,
          "Trimestral (1 cada 3 meses)": 3,
          "Semestral (2 por año)": 6,
          "Anual (1 por año)": 12
      }
      r_frec_str = st.selectbox("Frecuencia", list(opciones_frec.keys()), key="tab2_r_frec")
      r_frec = opciones_frec[r_frec_str]

    col_rd1, col_rd2 = st.columns(2)
    with col_rd1:
        r_dia = st.number_input(
            "Día del mes de vencimiento (1 a 31)",
            min_value=1,
            max_value=31,
            value=10,
            key="tab2_r_dia",
        )
    with col_rd2:
        r_fecha_ini = st.date_input(
            "Aplica a partir de", value=date.today(), key="tab2_r_fecha_ini"
        )
        
    r_desc = st.text_input(
        "Descripción (Ej: Alquiler, Internet, Patente Corsa)", key="tab2_r_desc"
    )

    if st.button(
        "⚙️ Crear Regla Fija Recurrente",
        type="primary",
        key="tab2_btn_guardar_rec",
    ):
      if r_monto > 0 and r_cat.strip():
        try:
          if r_es_nueva_cat:
            r_cat_clean = r_cat.strip()
            existe_cat = False
            if not df_categorias.empty and "nombre" in df_categorias.columns:
              existe_cat = r_cat_clean in df_categorias["nombre"].values

            if not existe_cat:
              supabase.table("categorias").insert({
                  "nombre": r_cat_clean,
                  "tipo_general": tipo_gen_r,
                  "clase_503020": r_clase_custom,
                  "limite_mensual": 0,
              }).execute()
            r_cat = r_cat_clean

          supabase.table("recurrentes").insert({
              "tipo": r_tipo,
              "categoria": r_cat,
              "monto": r_monto,
              "dia_mes": r_dia,
              "fecha_inicio": str(r_fecha_ini),
              "descripcion": r_desc,
              "frecuencia_meses": r_frec
          }).execute()
          recargar_app(
              f"Gasto configurado exitosamente."
          )
        except Exception as e:
          st.error(f"Error al crear regla fija: {e}")
      else:
        if not r_cat.strip():
          st.warning("Escribí el nombre de la categoría.")
        else:
          st.warning("El monto debe ser mayor a 0.")

  # -----------------------------------------------
  # OPCIÓN C: PLAN DE FINANCIACIÓN EN CUOTAS
  # -----------------------------------------------
  else:
    st.subheader("🚗 Configurar Gasto en Cuotas (Auto, Electrodomésticos, etc.)")
    st.caption(
        "Ingresá el valor mensual por cuota, cuántas cuotas pagaste y cuántas"
        " te faltan. La app **calculará automáticamente cuándo terminás de"
        " pagar**."
    )

    opciones_cat_cuotas = (
        df_categorias[df_categorias["tipo_general"] == "Gasto"][
            "nombre"
        ].tolist()
        if not df_categorias.empty and "tipo_general" in df_categorias.columns
        else ["Mantenimiento Corsa"]
    )
    opciones_cat_c_select = [
        "➕ [ Crear nueva categoría... ]"
    ] + opciones_cat_cuotas

    c_cat_sel = st.selectbox(
        "Categoría del Gasto", opciones_cat_c_select, key="tab2_c_cat_sel"
    )

    if c_cat_sel == "➕ [ Crear nueva categoría... ]":
      c_cat = st.text_input(
          "Nombre de la nueva categoría:", key="tab2_custom_cat_c"
      )
      c_es_nueva = True
    else:
      c_cat = c_cat_sel
      c_es_nueva = False

    col_cuo1, col_cuo2, col_cuo3 = st.columns(3)
    with col_cuo1:
      c_monto = st.number_input(
          "Monto de la Cuota ($ / USD)",
          min_value=0.0,
          value=100.0,
          step=10.0,
          key="tab2_c_monto",
      )
    with col_cuo2:
      c_totales = st.number_input(
          "Cantidad TOTAL de Cuotas",
          min_value=1,
          value=12,
          step=1,
          key="tab2_c_totales",
      )
    with col_cuo3:
      c_pagadas = st.number_input(
          "Cuotas Ya Pagadas Hasta Hoy",
          min_value=0,
          value=0,
          step=1,
          key="tab2_c_pagadas",
      )

    col_cuo4, col_cuo5 = st.columns(2)
    with col_cuo4:
      c_dia = st.number_input(
          "Día del mes de vencimiento (1 a 31)",
          min_value=1,
          max_value=31,
          value=10,
          key="tab2_c_dia",
      )
    with col_cuo5:
      c_fecha_ini = st.date_input(
          "Fecha de primera cuota / Inicio",
          value=date.today(),
          key="tab2_c_fecha_ini",
      )

    c_desc = st.text_input(
        "Descripción (Ej: Cuota Chevrolet Corsa, Cuota TV)",
        key="tab2_c_desc",
    )

    cuotas_restantes = max(0, c_totales - c_pagadas)
    saldo_restante = cuotas_restantes * c_monto
    fecha_fin_est = sumar_meses(date.today(), cuotas_restantes)

    st.info(
        f"📊 **Resumen del Plan:** Te quedan **{cuotas_restantes} cuotas** por"
        f" pagar. Total pendiente: **${saldo_restante:,.2f}**. Fecha estimada"
        f" de finalización: **{fecha_fin_est.strftime('%d/%m/%Y')}**."
    )

    if st.button(
        "🚗 Guardar Plan en Cuotas", type="primary", key="tab2_btn_guardar_cuota"
    ):
      if c_monto > 0 and c_cat.strip():
        try:
          if c_es_nueva:
            c_cat_clean = c_cat.strip()
            if not df_categorias.empty and "nombre" in df_categorias.columns:
              if c_cat_clean not in df_categorias["nombre"].values:
                supabase.table("categorias").insert({
                    "nombre": c_cat_clean,
                    "tipo_general": "Gasto",
                    "clase_503020": "50-Necesidad",
                    "limite_mensual": 0,
                }).execute()
            c_cat = c_cat_clean

          supabase.table("recurrentes").insert({
              "tipo": "Gasto Fijo",
              "categoria": c_cat,
              "monto": c_monto,
              "dia_mes": c_dia,
              "fecha_inicio": str(c_fecha_ini),
              "fecha_fin": str(fecha_fin_est),
              "descripcion": c_desc,
              "cuotas_totales": int(c_totales),
              "cuotas_pagadas": int(c_pagadas),
              "frecuencia_meses": 1
          }).execute()
          recargar_app(f"Plan de cuotas para '{c_desc}' guardado exitosamente.")
        except Exception as e:
          st.error(f"Error al guardar plan de cuotas: {e}")
      else:
        st.warning("Completá los campos correctamente.")

# ==========================================
# PESTAÑA 3: AUTOMATIZACIONES LABORALES
# ==========================================
with tab3:
  st.header("💼 Centros de Ingreso Automáticos")
  modo_trabajo = st.radio(
      "Seleccioná tu actividad:",
      [
          "⚽ Arbitraje: AAA (Sábados/Mensual)",
          "⚽ Arbitraje: Argenliga (Domingos/Diario)",
          "🩺 Consultorio Méd. (Semanal)",
      ],
      horizontal=True,
      key="tab3_modo_trabajo",
  )

  if "AAA" in modo_trabajo:
    col_aaa1, col_aaa2 = st.columns([1, 1.5])
    with col_aaa1:
      st.subheader("1. Registrar Partido Arbitrado")
      f_partido_aaa = st.date_input(
          "Fecha del Partido", value=datetime.today(), key="tab3_f_partido_aaa"
      )
      m_partido_aaa = st.number_input(
          "Honorario del partido ($)",
          min_value=0.0,
          step=1000.0,
          key="tab3_m_partido_aaa",
      )
      d_partido_aaa = st.text_input(
          "Detalle (Ej: Cat. Juveniles Cancha 2)", key="tab3_d_partido_aaa"
      )

      if st.button("Guardar Partido", key="tab3_btn_guardar_aaa"):
        if m_partido_aaa > 0:
          try:
            supabase.table("partidos_aaa").insert({
                "fecha": str(f_partido_aaa),
                "detalle": d_partido_aaa,
                "monto": m_partido_aaa,
                "estado": "Pendiente",
            }).execute()
            recargar_app("Partido guardado en pendientes.")
          except Exception as e:
            st.error(f"Error al guardar el partido: {e}")
        else:
          st.warning("El monto debe ser mayor a 0.")

    with col_aaa2:
      st.subheader("2. Liquidación Mensual AAA")
      if not df_partidos_aaa.empty and "estado" in df_partidos_aaa.columns:
        df_pend = df_partidos_aaa[
            df_partidos_aaa["estado"] == "Pendiente"
        ].copy()
        if not df_pend.empty:
          def obtener_mes_cobro_def(row):
              p_id = row["id"]
              if p_id not in st.session_state.aaa_mes_cobro_custom:
                  f_p = pd.to_datetime(row["fecha"]).date()
                  f_cob = primer_viernes_mes_siguiente(f_p)
                  st.session_state.aaa_mes_cobro_custom[p_id] = f"{f_cob.year}-{f_cob.month:02d}"
              return st.session_state.aaa_mes_cobro_custom[p_id]

          df_pend["Mes de Cobro (AAAA-MM)"] = df_pend.apply(obtener_mes_cobro_def, axis=1)

          st.write("Seleccioná los partidos que querés incluir en el cobro y **modificá el mes de cobro** si querés pasarlo de mes:")
          df_pend["Incluir"] = True
          df_pend_view = df_pend[["Incluir", "id", "fecha", "detalle", "monto", "Mes de Cobro (AAAA-MM)"]]
          
          editado = st.data_editor(
              df_pend_view,
              column_config={
                  "Incluir": st.column_config.CheckboxColumn(
                      "Cobrar ahora", default=True
                  ),
                  "id": st.column_config.NumberColumn("ID", disabled=True),
                  "Mes de Cobro (AAAA-MM)": st.column_config.TextColumn("Mes Asignado (AAAA-MM)"),
              },
              hide_index=True,
              use_container_width=True,
              key="tab3_editor_aaa",
          )
          
          if st.button("💾 Guardar Asignación de Meses", key="tab3_btn_guardar_meses_aaa"):
              for _, r_ed in editado.iterrows():
                  p_id = r_ed["id"]
                  nuevo_mes = str(r_ed["Mes de Cobro (AAAA-MM)"]).strip()
                  st.session_state.aaa_mes_cobro_custom[p_id] = nuevo_mes
              recargar_app("Meses de cobro actualizados correctamente.")

          seleccionados = editado[editado["Incluir"] == True]
          bruto_calculado = seleccionados["monto"].sum()
          neto_calculado = bruto_calculado - 15000

          col_tot1, col_tot2, col_tot3 = st.columns(3)
          col_tot1.metric("Bruto", f"${bruto_calculado:,.0f}")
          col_tot2.metric("Cuota AAA", "-$15,000")
          col_tot3.metric("NETO A COBRAR", f"${neto_calculado:,.0f}")

          fecha_cobro_final = st.date_input(
              "📅 Fecha de Cobro Real / Depósito",
              value=date.today(),
              key="tab3_f_cobro_aaa",
          )

          if st.button(
              "Generar Liquidación Mensual AAA",
              type="primary",
              key="tab3_btn_liq_aaa",
          ):
            if neto_calculado > 0:
              try:
                supabase.table("transacciones").insert({
                    "fecha": str(fecha_cobro_final),
                    "tipo": "Ingreso Variable",
                    "categoria": "Arbitraje",
                    "monto": neto_calculado,
                    "descripcion": (
                        f"Liquidación AAA ({len(seleccionados)} partidos -"
                        " Cuota descontada)"
                    ),
                }).execute()
                for _, row_sel in seleccionados.iterrows():
                  p_id = row_sel["id"]
                  supabase.table("partidos_aaa").update(
                      {"estado": "Cobrado"}
                  ).eq("id", p_id).execute()
                  if p_id in st.session_state.aaa_mes_cobro_custom:
                      del st.session_state.aaa_mes_cobro_custom[p_id]

                recargar_app("Liquidación registrada.")
              except Exception as e:
                st.error(f"Error al procesar la liquidación: {e}")
            else:
              st.warning("El neto debe ser mayor a 0.")
        else:
          st.info("No tenés partidos pendientes de cobrar.")
      else:
        st.info("No hay partidos guardados.")

  elif "Argenliga" in modo_trabajo:
    st.subheader("Cobro Inmediato Argenliga (con Retención 5%)")
    fecha_arg = st.date_input(
        "Fecha de cobro", value=ultimo_domingo(), key="tab3_f_arg"
    )
    monto_mano = st.number_input(
        "Total cobrado en mano ($)",
        min_value=0.0,
        step=1000.0,
        key="tab3_monto_mano_arg",
    )

    descuento_arg = monto_mano * 0.05
    neto_arg = monto_mano - descuento_arg

    col_arg1, col_arg2 = st.columns(2)
    col_arg1.warning(f"📉 **Retención (5%):** -${descuento_arg:,.2f}")
    col_arg2.success(f"💰 **Neto Real a Bolsillo:** ${neto_arg:,.2f}")

    desc_arg = st.text_input(
        "Nota (Opcional)",
        placeholder="Ej: 2 partidos cancha 3",
        key="tab3_desc_arg",
    )

    if st.button(
        "Registrar Argenliga", type="primary", key="tab3_btn_guardar_arg"
    ):
      if neto_arg > 0:
        try:
          supabase.table("transacciones").insert({
              "fecha": str(fecha_arg),
              "tipo": "Ingreso Variable",
              "categoria": "Arbitraje",
              "monto": neto_arg,
              "descripcion": (
                  f"Argenliga: {desc_arg} (Mano: {monto_mano} - 5% retención)"
              ),
          }).execute()
          recargar_app("Ingreso Argenliga registrado.")
        except Exception as e:
          st.error("Error al registrar.")

  elif "Consultorio" in modo_trabajo:
    st.subheader("Generador de Turnos Consultorio")
    col_c1, col_c2 = st.columns(2)
    with col_c1:
      c_mes = st.number_input(
          "Mes de Trabajo",
          min_value=1,
          max_value=12,
          value=datetime.today().month,
          key="tab3_c_mes",
      )
      c_anio = st.number_input(
          "Año de Trabajo",
          min_value=2024,
          value=datetime.today().year,
          key="tab3_c_anio",
      )
      c_monto = st.number_input(
          "Pago por día normal ($)",
          value=50000.0,
          step=1000.0,
          key="tab3_c_monto",
      )

    with col_c2:
      st.write("**¿Cuándo cobrás esta plata?**")
      tipo_cobro_cons = st.radio(
          "Modalidad de Cobro:",
          [
              "Cobro al mes siguiente",
              "Cobro el mismo día trabajado",
              "Fecha personalizada",
          ],
          index=0,
          key="tab3_tipo_cobro_cons",
      )

      if "mes siguiente" in tipo_cobro_cons:
        f_default_cobro = (
            date(c_anio + 1, 1, 1)
            if c_mes == 12
            else date(c_anio, c_mes + 1, 1)
        )
      elif "personalizada" in tipo_cobro_cons:
        f_default_cobro = st.date_input(
            "Fecha de cobro fija",
            value=datetime.today(),
            key="tab3_f_cobro_cons_pers",
        )
      else:
        f_default_cobro = None

    if st.button("🔍 Generar Planilla de Turnos", key="tab3_btn_gen_cons"):
      cal = calendar.monthcalendar(c_anio, c_mes)
      turnos = []
      for semana in cal:
        for i, dia in enumerate(semana):
          if dia != 0 and i in [1, 4]:
            f_trabajo = f"{c_anio}-{c_mes:02d}-{dia:02d}"
            f_cobro = str(f_default_cobro) if f_default_cobro else f_trabajo
            turnos.append({
                "Fecha Trabajo": f_trabajo,
                "Fecha Cobro": f_cobro,
                "Categoría": "Consultorio",
                "Monto": float(c_monto),
                "Descripción": "Día laboral",
            })
      if turnos:
        st.session_state["turnos_cons"] = pd.DataFrame(turnos)

    if "turnos_cons" in st.session_state:
      df_editado = st.data_editor(
          st.session_state["turnos_cons"],
          column_config={
              "Fecha Trabajo": st.column_config.TextColumn(
                  "Día Trabajado", disabled=True
              ),
              "Fecha Cobro": st.column_config.TextColumn("Fecha de Cobro Real"),
              "Monto": st.column_config.NumberColumn("Monto ($)", min_value=0.0),
          },
          num_rows="dynamic",
          use_container_width=True,
          key="tab3_editor_cons",
      )

      if st.button(
          "💾 Guardar Planilla Mensual",
          type="primary",
          key="tab3_btn_guardar_cons",
      ):
        try:
          datos_a_insertar = []
          for _, row in df_editado.iterrows():
            datos_a_insertar.append({
                "fecha": str(row["Fecha Cobro"]),
                "tipo": "Ingreso Variable",
                "categoria": row["Categoría"],
                "monto": row["Monto"],
                "descripcion": (
                    f"{row['Descripción']} (Trabajado: {row['Fecha Trabajo']})"
                ),
            })
          if datos_a_insertar:
            supabase.table("transacciones").insert(datos_a_insertar).execute()
            del st.session_state["turnos_cons"]
            recargar_app("Turnos del consultorio guardados.")
        except Exception as e:
          st.error("Error al guardar la planilla.")

# ==========================================
# PESTAÑA 4: METAS, VENCIMIENTOS Y PLANES EN CUOTAS
# ==========================================
with tab4:
  st.header("🎯 Sobres, Vencimientos y Planes en Cuotas")
  sub_t4 = st.radio(
      "Sección:",
      [
          "Vencimientos (Fijos + Eventuales)",
          "🚗 Planes de Cuotas Activos",
          "Me deben / Debo (Cuentas Corrientes)",
          "Sobres / Metas de Ahorro",
      ],
      horizontal=True,
      key="tab4_sub_section",
  )

  # ------------------------------------
  # 1. VENCIMIENTOS DINÁMICOS
  # ------------------------------------
  if "Vencimientos" in sub_t4:
    col_v1, col_v2 = st.columns([1, 1.8])
    with col_v1:
      st.subheader("➕ Agregar Vencimiento Eventual")
      con_v = st.text_input(
          "Concepto (Ej: VTV Corsa, Tarjeta Crédito)", key="tab4_con_v"
      )
      f_v = st.date_input(
          "Fecha de Vencimiento", value=datetime.today(), key="tab4_f_v"
      )
      m_v = st.number_input(
          "Monto estimado ($)", min_value=0.0, step=1000.0, key="tab4_m_v"
      )
      if st.button("Registrar Vencimiento", key="tab4_btn_guardar_venc"):
        if con_v:
          try:
            supabase.table("vencimientos").insert({
                "concepto": con_v,
                "fecha_vencimiento": str(f_v),
                "monto": m_v,
                "estado": "Pendiente",
            }).execute()
            recargar_app("Vencimiento registrado.")
          except Exception as e:
            st.error("Error al guardar.")
        else:
          st.warning("Ingresá un concepto.")

    with col_v2:
      st.subheader("🔔 Estado de Vencimientos de Gastos Fijos")
      fijos_info = calcular_vencimientos_fijos()

      if fijos_info:
        for item in fijos_info:
          col_item1, col_item2 = st.columns([3, 1])
          dias = item["dias_restantes"]
          fecha_fmt = item["fecha_vencimiento"].strftime("%d/%m/%Y")
          estado_pago = item["estado_pago"]

          with col_item1:
            if estado_pago == "Pendiente":
              if dias < 0:
                st.error(
                    f"🛑 **{item['categoria']}** ({item['descripcion']}):"
                    f" **PENDIENTE** - Venció hace {abs(dias)} días ({fecha_fmt})"
                    f" - ${item['monto']:,.0f}"
                )
              elif dias <= 7:
                st.warning(
                    f"⚠️ **{item['categoria']}** ({item['descripcion']}):"
                    f" **PENDIENTE** - Vence en {dias} días ({fecha_fmt}) -"
                    f" ${item['monto']:,.0f}"
                )
              else:
                st.info(
                    f"📅 **{item['categoria']}** ({item['descripcion']}):"
                    f" **PENDIENTE** - Vence el {fecha_fmt} (en {dias} días) -"
                    f" ${item['monto']:,.0f}"
                )
            else:
              st.success(
                  f"✅ **{item['categoria']}** ({item['descripcion']}):"
                  f" **PAGADO ESTE MES**. Próximo vencimiento: {fecha_fmt} (en"
                  f" {dias} días) - ${item['monto']:,.0f}"
              )

          with col_item2:
            if estado_pago == "Pendiente":
              if st.button(
                  "💳 Marcar Pagado",
                  key=f"pay_rec_{item['id_recurrente']}_{item['mes_año']}",
              ):
                try:
                  supabase.table("transacciones").insert({
                      "fecha": str(item["fecha_vencimiento"]),
                      "tipo": "Gasto Fijo",
                      "categoria": item["categoria"],
                      "monto": item["monto"],
                      "descripcion": (
                          f"Pago Fijo {item['mes_año']} -"
                          f" {item['descripcion']}"
                      ),
                  }).execute()

                  if item.get("cuotas_totales"):
                    nuevas_pagadas = (item.get("cuotas_pagadas") or 0) + 1
                    nuevas_restantes = max(
                        0, item["cuotas_totales"] - nuevas_pagadas
                    )
                    nueva_f_fin = sumar_meses(date.today(), nuevas_restantes)
                    supabase.table("recurrentes").update({
                        "cuotas_pagadas": nuevas_pagadas,
                        "fecha_fin": str(nueva_f_fin),
                    }).eq("id", item["id_recurrente"]).execute()

                  recargar_app(
                      f"Pago de {item['categoria']} registrado para"
                      f" {item['mes_año']}."
                  )
                except Exception as e:
                  st.error(f"Error al registrar pago: {e}")
      else:
        st.info("No hay gastos fijos configurados.")

      st.markdown("---")
      st.markdown("##### **Vencimientos Eventuales Registrados:**")
      if not df_vencimientos.empty:
        df_venc_edit = df_vencimientos[
            ["id", "concepto", "fecha_vencimiento", "monto", "estado"]
        ].copy()
        df_venc_edit["fecha_vencimiento"] = df_venc_edit[
            "fecha_vencimiento"
        ].astype(str)

        venc_editados = st.data_editor(
            df_venc_edit,
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True),
                "concepto": st.column_config.TextColumn("Concepto"),
                "fecha_vencimiento": st.column_config.TextColumn("Fecha Venc."),
                "monto": st.column_config.NumberColumn(
                    "Monto ($)", min_value=0.0, format="$%f"
                ),
                "estado": st.column_config.SelectboxColumn(
                    "Estado", options=["Pendiente", "Pagado"]
                ),
            },
            hide_index=True,
            use_container_width=True,
            key="tab4_editor_venc",
        )

        col_bv1, col_bv2 = st.columns(2)
        with col_bv1:
          if st.button(
              "💾 Guardar Vencimientos Eventuales",
              type="primary",
              key="tab4_btn_update_venc",
          ):
            try:
              for _, row in venc_editados.iterrows():
                supabase.table("vencimientos").update({
                    "concepto": str(row["concepto"]),
                    "fecha_vencimiento": str(row["fecha_vencimiento"]),
                    "monto": float(row["monto"]),
                    "estado": str(row["estado"]),
                }).eq("id", row["id"]).execute()
              recargar_app("Vencimientos actualizados.")
            except Exception as e:
              st.error(f"Error: {e}")

        with col_bv2:
          id_del_venc = st.number_input(
              "ID a Eliminar", min_value=0, step=1, key="tab4_id_del_venc"
          )
          if st.button("🗑️ Eliminar Vencimiento", key="tab4_btn_del_venc"):
            if id_del_venc in df_vencimientos["id"].values:
              try:
                supabase.table("vencimientos").delete().eq(
                    "id", id_del_venc
                ).execute()
                recargar_app("Eliminado.")
              except Exception as e:
                st.error("Error al eliminar.")
      else:
        st.info("No hay vencimientos eventuales cargados.")

  # ------------------------------------
  # 2. PLANES DE CUOTAS ACTIVOS (EDITABLE EN DIRECTO)
  # ------------------------------------
  elif "Planes de Cuotas" in sub_t4:
    st.subheader("🚗 Planes de Financiación en Cuotas Activos")
    st.info(
        "✏️ **Planilla Editable:** Podés cambiar directamente el **Monto de la Cuota** si te aplicaron intereses. "
        "✅ Al cambiarlo acá, los recibos viejos del Historial no se modifican, pero las cuotas restantes empezarán a usar este valor."
    )

    if not df_recurrentes.empty and "cuotas_totales" in df_recurrentes.columns:
      df_cuotas = df_recurrentes[
          df_recurrentes["cuotas_totales"].notna()
          & (df_recurrentes["cuotas_totales"] > 0)
      ].copy()

      if not df_cuotas.empty:
        df_cuotas_edit = df_cuotas[[
            "id",
            "categoria",
            "descripcion",
            "monto",
            "cuotas_pagadas",
            "cuotas_totales",
            "dia_mes",
            "fecha_fin",
        ]].copy()
        df_cuotas_edit["fecha_fin"] = df_cuotas_edit["fecha_fin"].astype(str)

        cuotas_editadas = st.data_editor(
            df_cuotas_edit,
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True),
                "categoria": st.column_config.SelectboxColumn(
                    "Categoría", options=lista_todas_categorias
                ),
                "descripcion": st.column_config.TextColumn("Descripción / Plan"),
                "monto": st.column_config.NumberColumn(
                    "Monto Cuota NUEVA ($)", min_value=0.0, format="$%f"
                ),
                "cuotas_pagadas": st.column_config.NumberColumn(
                    "Cuotas Pagadas", min_value=0, step=1
                ),
                "cuotas_totales": st.column_config.NumberColumn(
                    "Cuotas Totales", min_value=1, step=1
                ),
                "dia_mes": st.column_config.NumberColumn(
                    "Día Vencimiento", min_value=1, max_value=31
                ),
                "fecha_fin": st.column_config.TextColumn("Fin Est. (AAAA-MM-DD)"),
            },
            hide_index=True,
            use_container_width=True,
            key="tab4_editor_cuotas_directo",
        )

        col_bcuo1, col_bcuo2 = st.columns(2)
        with col_bcuo1:
          if st.button(
              "💾 GUARDAR CAMBIOS EN CUOTAS",
              type="primary",
              key="tab4_btn_save_cuotas",
          ):
            try:
              for _, row in cuotas_editadas.iterrows():
                c_tot = int(row["cuotas_totales"])
                c_pag = int(row["cuotas_pagadas"])
                c_rest = max(0, c_tot - c_pag)
                nueva_f_fin = str(sumar_meses(date.today(), c_rest))

                supabase.table("recurrentes").update({
                    "categoria": str(row["categoria"]),
                    "descripcion": str(row["descripcion"]),
                    "monto": float(row["monto"]),
                    "cuotas_pagadas": c_pag,
                    "cuotas_totales": c_tot,
                    "dia_mes": int(row["dia_mes"]),
                    "fecha_fin": nueva_f_fin,
                }).eq("id", row["id"]).execute()

              recargar_app("Planes de cuotas actualizados.")
            except Exception as e:
              st.error(f"Error al actualizar cuotas: {e}")

        with col_bcuo2:
          id_del_plan = st.number_input(
              "ID Plan a Eliminar", min_value=0, step=1, key="tab4_id_del_plan"
          )
          if st.button("🗑️ Eliminar Plan de Cuotas", key="tab4_btn_del_plan"):
            if id_del_plan in df_cuotas["id"].values:
              try:
                supabase.table("recurrentes").delete().eq(
                    "id", id_del_plan
                ).execute()
                recargar_app("Plan de cuotas eliminado.")
              except Exception as e:
                st.error("Error al eliminar plan.")

        st.warning("⚠️ **ATENCIÓN:** Si tocaste el botón rojo de *Eliminar Plan de Cuotas* porque te habías equivocado al cargarlo, recordá ir también a la pestaña **📝 Historial** para borrar el recibo del pago, así no te suma dinero fantasma en tu total del mes.")

        st.markdown("---")
        st.markdown("##### 📊 **Tarjetas de Avance Visual:**")
        for _, row in df_cuotas.iterrows():
          c_tot = int(row["cuotas_totales"])
          c_pag = int(row["cuotas_pagadas"]) if pd.notna(row["cuotas_pagadas"]) else 0
          c_rest = max(0, c_tot - c_pag)
          monto_c = float(row["monto"])
          saldo_pend = c_rest * monto_c
          progreso = min(1.0, c_pag / c_tot) if c_tot > 0 else 1.0

          f_fin_str = (
              str(row["fecha_fin"])
              if pd.notna(row.get("fecha_fin"))
              else "No definida"
          )

          st.markdown(
              f"**{row['categoria']}** - {row.get('descripcion', 'Plan')}:"
              f" Cuota **${monto_c:,.2f}** ({c_pag}/{c_tot} cuotas pagadas) -"
              f" Pendiente **${saldo_pend:,.2f}** (Finaliza: {f_fin_str})"
          )
          st.progress(progreso)
      else:
        st.info("No hay planes de cuotas activos configurados.")
    else:
      st.info("No hay planes de cuotas configurados aún.")

  # ------------------------------------
  # 3. ME DEBEN / DEBO
  # ------------------------------------
  elif "Me deben / Debo" in sub_t4:
    col_d1, col_d2 = st.columns([1, 1.8])
    with col_d1:
      st.subheader("➕ Nueva Cuenta Corriente")
      pers = st.text_input("Persona / Entidad", key="tab4_pers_deuda")
      t_deuda = st.selectbox(
          "Tipo", ["Me deben", "Debo"], key="tab4_tipo_deuda"
      )
      m_deuda = st.number_input(
          "Monto ($)", min_value=0.0, step=1000.0, key="tab4_monto_deuda"
      )
      fecha_pago_deuda = st.date_input(
          "Fecha Estimada de Pago / Cobro",
          value=datetime.today(),
          key="tab4_fecha_pago_deuda",
      )
      det_deuda = st.text_input(
          "Detalle (Ej: Entrada, préstamo)", key="tab4_det_deuda"
      )

      if st.button("Guardar Registro", key="tab4_btn_guardar_deuda"):
        if pers and m_deuda > 0:
          try:
            supabase.table("deudas").insert({
                "persona": pers,
                "tipo": t_deuda,
                "monto": m_deuda,
                "detalle": det_deuda,
                "estado": "Pendiente",
                "fecha_pago": str(fecha_pago_deuda),
            }).execute()
            recargar_app("Cuenta corriente guardada.")
          except Exception as e:
            st.error(f"Error: {e}")
        else:
          st.warning("Completá el nombre de la persona y un monto mayor a 0.")

    with col_d2:
      st.subheader("✏️ Planilla Editable de Cuentas Corrientes")
      if not df_deudas.empty:
        df_deudas_edit = df_deudas[
            ["id", "persona", "tipo", "monto", "fecha_pago", "detalle", "estado"]
        ].copy()
        df_deudas_edit["fecha_pago"] = df_deudas_edit["fecha_pago"].astype(str)

        deudas_editadas = st.data_editor(
            df_deudas_edit,
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True),
                "monto": st.column_config.NumberColumn(
                    "Monto ($)", min_value=0.0, format="$%f"
                ),
                "estado": st.column_config.SelectboxColumn(
                    "Estado", options=["Pendiente", "Saldado"]
                ),
            },
            hide_index=True,
            use_container_width=True,
            key="tab4_editor_deudas",
        )

        col_btn_d1, col_btn_d2 = st.columns(2)
        with col_btn_d1:
          if st.button(
              "💾 Guardar Deudas",
              type="primary",
              key="tab4_btn_update_deudas",
          ):
            try:
              for _, row in deudas_editadas.iterrows():
                supabase.table("deudas").update({
                    "persona": str(row["persona"]),
                    "tipo": str(row["tipo"]),
                    "monto": float(row["monto"]),
                    "fecha_pago": str(row["fecha_pago"]),
                    "detalle": str(row["detalle"]) if row["detalle"] else "",
                    "estado": str(row["estado"]),
                }).eq("id", row["id"]).execute()
              recargar_app("Cuentas corrientes actualizadas.")
            except Exception as e:
              st.error(f"Error: {e}")

        with col_btn_d2:
          id_del_deuda = st.number_input(
              "ID a Eliminar",
              min_value=0,
              step=1,
              key="tab4_id_del_deuda",
          )
          if st.button("🗑️ Eliminar Fila", key="tab4_btn_del_deuda"):
            if id_del_deuda in df_deudas["id"].values:
              try:
                supabase.table("deudas").delete().eq(
                    "id", id_del_deuda
                ).execute()
                recargar_app("Eliminado.")
              except Exception as e:
                st.error("Error.")
      else:
        st.info("No hay cuentas corrientes registradas.")

  # ------------------------------------
  # 4. METAS / SOBRES
  # ------------------------------------
  elif "Sobres / Metas" in sub_t4:
    col_m1, col_m2 = st.columns([1, 1.8])
    with col_m1:
      st.subheader("➕ Crear Sobre de Ahorro")
      n_meta = st.text_input(
          "Nombre de la meta (Ej: Facultad 2027, Mantenimiento Corsa)",
          key="tab4_n_meta",
      )
      obj_meta = st.number_input(
          "Monto Objetivo ($)",
          min_value=1000.0,
          step=10000.0,
          key="tab4_obj_meta",
      )
      act_meta = st.number_input(
          "Monto Actual Ahorrado ($)",
          min_value=0.0,
          step=1000.0,
          key="tab4_act_meta",
      )
      if st.button("Guardar Meta", key="tab4_btn_guardar_meta"):
        if n_meta:
          try:
            supabase.table("metas_ahorro").insert({
                "nombre": n_meta,
                "monto_objetivo": obj_meta,
                "monto_actual": act_meta,
            }).execute()
            recargar_app("Meta creada con éxito.")
          except Exception as e:
            st.error("Error al guardar la meta.")

    with col_m2:
      st.subheader("✏️ Planilla Editable de Metas")
      if not df_metas.empty:
        df_metas_edit = df_metas[
            ["id", "nombre", "monto_objetivo", "monto_actual"]
        ].copy()

        metas_editadas = st.data_editor(
            df_metas_edit,
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True),
                "monto_objetivo": st.column_config.NumberColumn(
                    "Monto Objetivo ($)", min_value=0.0, format="$%f"
                ),
                "monto_actual": st.column_config.NumberColumn(
                    "Monto Actual ($)", min_value=0.0, format="$%f"
                ),
            },
            hide_index=True,
            use_container_width=True,
            key="tab4_editor_metas",
        )

        if st.button(
            "💾 Guardar Metas", type="primary", key="tab4_btn_update_metas"
        ):
          try:
            for _, row in metas_editadas.iterrows():
              supabase.table("metas_ahorro").update({
                  "nombre": str(row["nombre"]),
                  "monto_objetivo": float(row["monto_objetivo"]),
                  "monto_actual": float(row["monto_actual"]),
              }).eq("id", row["id"]).execute()
            recargar_app("Metas actualizadas.")
          except Exception as e:
            st.error(f"Error: {e}")
      else:
        st.info("No hay metas creadas.")

# ==========================================
# PESTAÑA 5: HISTORIAL Y EXCEL
# ==========================================
with tab5:
  st.header("📝 Historial Editable de Transacciones")

  if not df_transacciones.empty:
    df_trans_edit = df_transacciones[
        ["id", "fecha", "tipo", "categoria", "monto", "descripcion"]
    ].copy()
    df_trans_edit["fecha"] = df_trans_edit["fecha"].astype(str)

    transacciones_editadas = st.data_editor(
        df_trans_edit,
        column_config={
            "id": st.column_config.NumberColumn("ID", disabled=True),
            "categoria": st.column_config.SelectboxColumn(
                "Categoría", options=lista_todas_categorias
            ),
            "monto": st.column_config.NumberColumn(
                "Monto ($)", min_value=0.0, format="$%f"
            ),
        },
        hide_index=True,
        use_container_width=True,
        key="tab5_editor_transacciones",
    )

    col_ht1, col_ht2 = st.columns(2)
    with col_ht1:
      if st.button(
          "💾 GUARDAR HISTORIAL",
          type="primary",
          key="tab5_btn_save_trans",
      ):
        try:
          for _, row in transacciones_editadas.iterrows():
            supabase.table("transacciones").update({
                "fecha": str(row["fecha"]),
                "tipo": str(row["tipo"]),
                "categoria": str(row["categoria"]),
                "monto": float(row["monto"]),
                "descripcion": (
                    str(row["descripcion"]) if row["descripcion"] else ""
                ),
            }).eq("id", row["id"]).execute()
          recargar_app("Historial actualizado.")
        except Exception as e:
          st.error(f"Error: {e}")

    with col_ht2:
      csv_data = df_transacciones.to_csv(
          index=False, sep=";", encoding="utf-8-sig"
      ).encode("utf-8-sig")
      st.download_button(
          label="📥 Descargar Excel (CSV)",
          data=csv_data,
          file_name=f"finanzas_pro_{date.today()}.csv",
          mime="text/csv",
          key="tab5_btn_download_csv",
      )

    st.markdown("---")
    st.subheader("🗑️ Eliminar Movimiento del Historial")
    st.info("💡 **Solución para Gastos Fantasmas:** Si en tu panel aparece un monto de más porque marcaste un gasto fijo como pagado por error, buscalo en esta lista y **borralo**. El dinero total se va a descontar automáticamente.")
    
    opciones_borrar = {
        int(row["id"]): (
            f"ID {int(row['id'])} | {row['fecha']} | {row['categoria']} |"
            f" ${row['monto']:,.0f} | {row['descripcion']}"
        )
        for _, row in df_transacciones.iterrows()
    }

    col_del_1, col_del_2 = st.columns([2, 1])
    with col_del_1:
      id_sel_borrar = st.selectbox(
          "Seleccioná el recibo/movimiento que querés borrar:",
          options=list(opciones_borrar.keys()),
          format_func=lambda x: opciones_borrar[x],
          key="tab5_sel_borrar",
      )
    with col_del_2:
      st.write(" ")
      st.write(" ")
      if st.button(
          "🗑️ Borrar Movimiento Seleccionado",
          type="primary",
          key="tab5_btn_borrar_sel",
      ):
        try:
          supabase.table("transacciones").delete().eq(
              "id", int(id_sel_borrar)
          ).execute()
          recargar_app(f"Movimiento ID {id_sel_borrar} borrado con éxito.")
        except Exception as e:
          st.error(f"Error al borrar en Supabase: {e}")
  else:
    st.info("No hay historial disponible.")

# ==========================================
# PESTAÑA 6: GESTIÓN DE FIJOS Y CONFIGURACIÓN
# ==========================================
with tab6:
  st.header("⚙️ Gestión de Fijos, Cuotas y Categorías")

  col_t6_a, col_t6_b = st.columns([1.5, 1])

  with col_t6_a:
    st.subheader("✏️ Planilla Editable de Fijos y Planes de Cuotas")
    st.caption(
        "Podés modificar montos, días de vencimiento, descripciones o cuotas y"
        " hacer clic en guardar."
    )

    if not df_recurrentes.empty:
      df_rec_full = df_recurrentes.copy()
      for c in [
          "cuotas_totales",
          "cuotas_pagadas",
          "fecha_fin",
          "fecha_inicio",
          "dia_mes",
          "frecuencia_meses"
      ]:
        if c not in df_rec_full.columns:
          df_rec_full[c] = None

      df_rec_full["fecha_inicio"] = (
          df_rec_full["fecha_inicio"].astype(str).fillna("")
      )
      df_rec_full["fecha_fin"] = df_rec_full["fecha_fin"].astype(str).fillna("")

      rec_editados = st.data_editor(
          df_rec_full[[
              "id",
              "tipo",
              "categoria",
              "monto",
              "frecuencia_meses",
              "dia_mes",
              "cuotas_pagadas",
              "cuotas_totales",
              "descripcion",
              "fecha_inicio",
              "fecha_fin",
          ]],
          column_config={
              "id": st.column_config.NumberColumn("ID", disabled=True),
              "tipo": st.column_config.SelectboxColumn(
                  "Tipo", options=["Gasto Fijo", "Ingreso Fijo"]
              ),
              "categoria": st.column_config.SelectboxColumn(
                  "Categoría", options=lista_todas_categorias
              ),
              "monto": st.column_config.NumberColumn(
                  "Monto ($)", min_value=0.0, format="$%f"
              ),
              "frecuencia_meses": st.column_config.NumberColumn(
                  "Frec. (Meses)", min_value=1, max_value=12, step=1
              ),
              "dia_mes": st.column_config.NumberColumn(
                  "Día Mes", min_value=1, max_value=31
              ),
              "cuotas_pagadas": st.column_config.NumberColumn(
                  "Cuotas Pagadas", min_value=0
              ),
              "cuotas_totales": st.column_config.NumberColumn(
                  "Cuotas Totales", min_value=0
              ),
              "descripcion": st.column_config.TextColumn("Descripción"),
              "fecha_inicio": st.column_config.TextColumn("Inicio"),
              "fecha_fin": st.column_config.TextColumn("Fin Est."),
          },
          hide_index=True,
          use_container_width=True,
          key="tab6_editor_recurrentes",
      )

      col_br1, col_br2 = st.columns(2)
      with col_br1:
        if st.button(
            "💾 GUARDAR CAMBIOS EN FIJOS Y CUOTAS",
            type="primary",
            key="tab6_btn_save_rec",
        ):
          try:
            for _, row in rec_editados.iterrows():
              c_tot_val = (
                  int(row["cuotas_totales"])
                  if pd.notna(row["cuotas_totales"])
                  and int(row["cuotas_totales"]) > 0
                  else None
              )
              c_pag_val = (
                  int(row["cuotas_pagadas"])
                  if pd.notna(row["cuotas_pagadas"])
                  else 0
              )
              f_fin_val = (
                  str(row["fecha_fin"]).strip()
                  if pd.notna(row["fecha_fin"])
                  and str(row["fecha_fin"]).strip() not in ["None", "nan", ""]
                  else None
              )
              frec_val = (
                  int(row["frecuencia_meses"])
                  if pd.notna(row["frecuencia_meses"]) and int(row["frecuencia_meses"]) > 0
                  else 1
              )

              supabase.table("recurrentes").update({
                  "tipo": str(row["tipo"]),
                  "categoria": str(row["categoria"]),
                  "monto": float(row["monto"]),
                  "frecuencia_meses": frec_val,
                  "dia_mes": int(row["dia_mes"]),
                  "fecha_inicio": str(row["fecha_inicio"]),
                  "fecha_fin": f_fin_val,
                  "descripcion": (
                      str(row["descripcion"]) if row["descripcion"] else ""
                  ),
                  "cuotas_totales": c_tot_val,
                  "cuotas_pagadas": c_pag_val,
              }).eq("id", row["id"]).execute()

            recargar_app("Movimientos fijos y cuotas actualizados.")
          except Exception as e:
            st.error(f"Error al guardar fijos: {e}")

      with col_br2:
        id_del_rec_t6 = st.number_input(
            "ID Fijo/Cuota a Eliminar",
            min_value=0,
            step=1,
            key="tab6_id_del_rec_t6",
        )
        if st.button("🗑️ Eliminar Fijo/Cuota", key="tab6_btn_del_rec_t6"):
          if id_del_rec_t6 in df_recurrentes["id"].values:
            try:
              supabase.table("recurrentes").delete().eq(
                  "id", id_del_rec_t6
              ).execute()
              recargar_app(f"Registro ID {id_del_rec_t6} eliminado.")
            except Exception as e:
              st.error("Error al eliminar.")
              
      st.warning("⚠️ Recuerda que si tocaste *Eliminar Fijo/Cuota* también deberás ir a la pestaña **📝 Historial** para borrar el comprobante real de pago si es que ya lo habías marcado como pagado por error.")

    else:
      st.info("No hay movimientos fijos ni cuotas configurados aún.")

  with col_t6_b:
    st.subheader("✏️ Planilla Editable de Categorías")
    if not df_categorias.empty:
      df_cat_edit = df_categorias[
          ["id", "nombre", "tipo_general", "clase_503020", "limite_mensual"]
      ].copy()

      cat_editadas = st.data_editor(
          df_cat_edit,
          column_config={
              "id": st.column_config.NumberColumn("ID", disabled=True),
              "nombre": st.column_config.TextColumn("Nombre Categoría"),
              "tipo_general": st.column_config.SelectboxColumn(
                  "Tipo", options=["Gasto", "Ingreso"]
              ),
              "clase_503020": st.column_config.SelectboxColumn(
                  "Clasificación 50/30",
                  options=[
                      "50-Necesidad",
                      "30-Deseo",
                      "Ingreso",
                      "Ahorro/Inversión",
                  ],
              ),
              "limite_mensual": st.column_config.NumberColumn(
                  "Límite Mensual ($)", min_value=0.0, format="$%f"
              ),
          },
          hide_index=True,
          use_container_width=True,
          key="tab6_editor_cat",
      )

      col_bcat1, col_bcat2 = st.columns(2)
      with col_bcat1:
        if st.button(
            "💾 Guardar Categorías",
            type="primary",
            key="tab6_btn_update_cat",
        ):
          try:
            for _, row in cat_editadas.iterrows():
              supabase.table("categorias").update({
                  "nombre": str(row["nombre"]),
                  "tipo_general": str(row["tipo_general"]),
                  "clase_503020": str(row["clase_503020"]),
                  "limite_mensual": float(row["limite_mensual"]),
              }).eq("id", row["id"]).execute()
            recargar_app("Categorías actualizadas correctamente.")
          except Exception as e:
            st.error(f"Error al actualizar categorías: {e}")

      with col_bcat2:
        id_del_cat = st.number_input(
            "ID Categoría a Eliminar",
            min_value=0,
            step=1,
            key="tab6_id_del_cat",
        )
        if st.button("🗑️ Eliminar Categoría", key="tab6_btn_del_cat"):
          if id_del_cat in df_categorias["id"].values:
            try:
              supabase.table("categorias").delete().eq(
                  "id", id_del_cat
              ).execute()
              recargar_app(f"Categoría {id_del_cat} eliminada.")
            except Exception as e:
              st.error("Error al eliminar categoría.")
          else:
            st.error("ID no encontrado.")
