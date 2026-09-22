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

# --- PROCESAMIENTO INICIAL ---
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

# Lista completa de categorías para selects
lista_todas_categorias = (
    df_categorias["nombre"].tolist()
    if not df_categorias.empty and "nombre" in df_categorias.columns
    else ["General"]
)

# --- ESTRUCTURA DE PESTAÑAS ---
st.title("📈 Mi Ecosistema Financiero Pro")
st.caption(
    "💡 *Todas las tablas son **editables en directo**: modificá cualquier"
    " valor y tocá el botón de guardar.*"
)

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "📊 Dashboards",
    "➕ Carga Rápida",
    "💼 Automatizaciones",
    "🎯 Metas & Vencimientos",
    "📝 Historial & Excel",
    "⚙️ Configuración",
])

# ==========================================
# PESTAÑA 1: DASHBOARDS Y SIMULADOR
# ==========================================
with tab1:
  st.header("📊 Análisis Mensual y Estado de Compromisos")

  meses_trans = (
      df_transacciones["mes_año"].dropna().unique().tolist()
      if not df_transacciones.empty
      else []
  )
  meses_deudas = (
      df_deudas["mes_año"].dropna().unique().tolist()
      if not df_deudas.empty
      else []
  )
  meses_disponibles = sorted(
      list(set(meses_trans + meses_deudas)), reverse=True
  )

  if not meses_disponibles:
    meses_disponibles = [date.today().strftime("%Y-%m")]

  mes_seleccionado = st.selectbox(
      "📅 Seleccionar Mes", meses_disponibles, key="tab1_mes_sel"
  )

  df_mes = (
      df_transacciones[df_transacciones["mes_año"] == mes_seleccionado]
      if not df_transacciones.empty
      else pd.DataFrame()
  )

  ingresos = (
      df_mes[df_mes["tipo_general"] == "Ingreso"]["monto"].sum()
      if not df_mes.empty
      else 0.0
  )
  gastos_pagados = (
      df_mes[df_mes["tipo_general"] == "Gasto"]["monto"].sum()
      if not df_mes.empty
      else 0.0
  )

  if not df_deudas.empty and "mes_año" in df_deudas.columns:
    df_deudas_mes_pend = df_deudas[
        (df_deudas["mes_año"] == mes_seleccionado)
        & (df_deudas["tipo"] == "Debo")
        & (df_deudas["estado"] == "Pendiente")
    ]
    deudas_pendientes_mes = df_deudas_mes_pend["monto"].sum()

    df_cobrar_mes_pend = df_deudas[
        (df_deudas["mes_año"] == mes_seleccionado)
        & (df_deudas["tipo"] == "Me deben")
        & (df_deudas["estado"] == "Pendiente")
    ]
    por_cobrar_mes = df_cobrar_mes_pend["monto"].sum()
  else:
    deudas_pendientes_mes = 0.0
    por_cobrar_mes = 0.0

  gastos_mas_deudas = gastos_pagados + deudas_pendientes_mes
  ahorro_caja = ingresos - gastos_pagados
  ahorro_neto_proyectado = (ingresos + por_cobrar_mes) - gastos_mas_deudas

  col1, col2, col3, col4 = st.columns(4)
  col1.metric("Ingresos Cobrados", f"${ingresos:,.2f}")
  col2.metric("Gastos Pagados", f"${gastos_pagados:,.2f}")
  col3.metric(
      "Deudas Pendientes (Debo)",
      f"${deudas_pendientes_mes:,.2f}",
      help="Deudas pendientes registradas para este mes.",
  )
  col4.metric(
      "Gastos + Deudas Totales",
      f"${gastos_mas_deudas:,.2f}",
      delta=(
          f"-${deudas_pendientes_mes:,.0f} pend."
          if deudas_pendientes_mes > 0
          else "Sin deudas pend."
      ),
      delta_color="inverse",
  )

  st.markdown("---")
  col_b1, col_b2, col_b3 = st.columns(3)
  col_b1.info(f"💵 **Ahorro Actual en Caja:** ${ahorro_caja:,.2f}")
  col_b2.warning(f"📩 **Por Cobrar (Me deben este mes):** ${por_cobrar_mes:,.2f}")
  col_b3.success(
      f"🎯 **Balance Final Proyectado:** ${ahorro_neto_proyectado:,.2f}"
  )

  st.markdown("---")
  col_g1, col_g2 = st.columns(2)
  with col_g1:
    st.subheader("Ingresos vs Gastos (Evolución de Caja)")
    if not df_transacciones.empty:
      df_hist = (
          df_transacciones.groupby(["mes_año", "tipo_general"])["monto"]
          .sum()
          .reset_index()
      )
      fig_hist = px.bar(
          df_hist,
          x="mes_año",
          y="monto",
          color="tipo_general",
          barmode="group",
          color_discrete_map={"Ingreso": "#2ecc71", "Gasto": "#e74c3c"},
      )
      st.plotly_chart(fig_hist, use_container_width=True)

  with col_g2:
    st.subheader(f"Desglose de Gastos ({mes_seleccionado})")
    if not df_mes.empty:
      df_gastos_mes = df_mes[df_mes["tipo_general"] == "Gasto"]
      if not df_gastos_mes.empty:
        fig_gastos = px.pie(
            df_gastos_mes, names="categoria", values="monto", hole=0.4
        )
        st.plotly_chart(fig_gastos, use_container_width=True)
      else:
        st.write("No hay gastos pagados en este mes.")

  st.markdown("---")
  st.header("🧮 Simulador de Rendimiento Diario (Interés Compuesto)")
  col_s1, col_s2, col_s3 = st.columns(3)
  with col_s1:
    cap_inicial = st.number_input(
        "Capital a Invertir ($)",
        value=float(ahorro_caja if ahorro_caja > 0 else 100000),
        step=10000.0,
        key="tab1_cap_inicial",
    )
  with col_s2:
    tna = st.number_input(
        "TNA Actual Billetera (%)",
        value=38.0,
        step=1.0,
        key="tab1_tna",
    )
  with col_s3:
    dias_inversion = st.number_input(
        "Días de inversión", value=30, min_value=1, key="tab1_dias_inv"
    )

  tasa_diaria = (tna / 100) / 365
  cap_final = cap_inicial * ((1 + tasa_diaria) ** dias_inversion)
  ganancia = cap_final - cap_inicial
  st.success(
      f"💸 **Dinero total al final:** ${cap_final:,.2f} (Ganaste"
      f" **${ganancia:,.2f}** sin hacer nada)"
  )

# ==========================================
# PESTAÑA 2: CARGA RÁPIDA
# ==========================================
with tab2:
  st.header("📝 Movimiento Único")
  tipo_mov = st.selectbox(
      "Tipo",
      ["Ingreso Variable", "Ingreso Fijo", "Gasto Variable", "Gasto Fijo"],
      key="tab2_tipo_mov",
  )
  tipo_general = "Ingreso" if "Ingreso" in tipo_mov else "Gasto"
  opciones_cat = (
      df_categorias[df_categorias["tipo_general"] == tipo_general][
          "nombre"
      ].tolist()
      if not df_categorias.empty and "tipo_general" in df_categorias.columns
      else ["Sin categorías"]
  )

  cat_mov = st.selectbox("Categoría", opciones_cat, key="tab2_cat_mov")
  monto_mov = st.number_input(
      "Monto ($)", min_value=0.0, step=1000.0, key="tab2_monto_mov"
  )
  fecha_mov = st.date_input(
      "Fecha de Cobro / Pago Efectivo", datetime.today(), key="tab2_fecha_mov"
  )
  desc_mov = st.text_input(
      "Descripción (Ej: Nafta, Coto...)", key="tab2_desc_mov"
  )

  if st.button("Guardar Movimiento", type="primary", key="tab2_btn_guardar"):
    if monto_mov > 0:
      try:
        nuevo = {
            "fecha": str(fecha_mov),
            "tipo": tipo_mov,
            "categoria": cat_mov,
            "monto": monto_mov,
            "descripcion": desc_mov,
        }
        supabase.table("transacciones").insert(nuevo).execute()
        recargar_app("Movimiento guardado.")
      except Exception as e:
        st.error(
            "Error de conexión al guardar el movimiento. Intentá de nuevo."
        )
    else:
      st.warning("El monto debe ser mayor a 0.")

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
            st.error("Error al guardar el partido.")
        else:
          st.warning("El monto debe ser mayor a 0.")

    with col_aaa2:
      st.subheader("2. Liquidación Mensual AAA (Cobro Efectivo)")
      if not df_partidos_aaa.empty and "estado" in df_partidos_aaa.columns:
        df_pend = df_partidos_aaa[
            df_partidos_aaa["estado"] == "Pendiente"
        ].copy()
        if not df_pend.empty:
          st.write("Seleccioná y editá partidos que entran en la liquidación:")
          df_pend["Incluir"] = True
          df_pend = df_pend[["Incluir", "id", "fecha", "detalle", "monto"]]
          editado = st.data_editor(
              df_pend,
              column_config={
                  "Incluir": st.column_config.CheckboxColumn(
                      "Cobrar ahora", default=True
                  ),
                  "id": st.column_config.NumberColumn("ID", disabled=True),
                  "fecha": st.column_config.TextColumn("Fecha Partido"),
                  "monto": st.column_config.NumberColumn(
                      "Monto ($)", min_value=0.0
                  ),
              },
              hide_index=True,
              use_container_width=True,
              key="tab3_editor_aaa",
          )
          seleccionados = editado[editado["Incluir"] == True]
          bruto_calculado = seleccionados["monto"].sum()
          neto_calculado = bruto_calculado - 15000

          col_tot1, col_tot2, col_tot3 = st.columns(3)
          col_tot1.metric("Bruto", f"${bruto_calculado:,.0f}")
          col_tot2.metric("Cuota AAA", "-$15,000")
          col_tot3.metric("NETO A COBRAR", f"${neto_calculado:,.0f}")

          fecha_proyectada = primer_viernes_mes_siguiente(date.today())
          fecha_cobro_final = st.date_input(
              "📅 Fecha de Cobro Real",
              value=fecha_proyectada,
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
                for p_id in seleccionados["id"].tolist():
                  supabase.table("partidos_aaa").update(
                      {"estado": "Cobrado"}
                  ).eq("id", p_id).execute()
                recargar_app(
                    "Liquidación agendada exitosamente para el"
                    f" {fecha_cobro_final}."
                )
              except Exception as e:
                st.error("Error al procesar la liquidación.")
            else:
              st.warning("El neto calculado debe ser mayor a 0.")
        else:
          st.info("No tenés partidos pendientes de cobrar.")
      else:
        st.info("No hay registro de partidos guardados.")

  elif "Argenliga" in modo_trabajo:
    st.subheader("Cobro Inmediato Argenliga (con Retención 5%)")
    fecha_arg = st.date_input(
        "Fecha de cobro (Día del partido)",
        value=ultimo_domingo(),
        key="tab3_f_arg",
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
          recargar_app("Ingreso Argenliga registrado correctamente.")
        except Exception as e:
          st.error("Error al registrar Argenliga.")
      else:
        st.warning("El monto ingresado debe ser mayor a 0.")

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
              "Cobro al mes siguiente (Ej: 1er día del mes sig.)",
              "Cobro el mismo día trabajado",
              "Fecha de cobro personalizada",
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
      st.info("💡 Podés modificar las fechas y montos antes de guardar:")
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
# PESTAÑA 4: METAS, VENCIMIENTOS Y DEUDAS
# ==========================================
with tab4:
  st.header("🎯 Sobres de Ahorro, Vencimientos y Cuentas Corrientes")
  sub_t4 = st.radio(
      "Sección:",
      [
          "Me deben / Debo (Cuentas Corrientes)",
          "Vencimientos (Corsa / Servicios)",
          "Sobres / Metas de Ahorro",
      ],
      horizontal=True,
      key="tab4_sub_section",
  )

  # ------------------------------------
  # 1. ME DEBEN / DEBO (EDITABLE TOTAL)
  # ------------------------------------
  if "Me deben / Debo" in sub_t4:
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
            st.error(f"Error al guardar: {e}")
        else:
          st.warning("Completá el nombre de la persona y un monto mayor a 0.")

    with col_d2:
      st.subheader("✏️ Planilla Editable de Cuentas Corrientes")
      st.caption(
          "Podés editar cualquier celda (Monto, Persona, Fecha, Estado) y hacer"
          " clic en Guardar Cambios."
      )

      if not df_deudas.empty:
        # Preparamos los datos para editar
        df_deudas_edit = df_deudas[
            ["id", "persona", "tipo", "monto", "fecha_pago", "detalle", "estado"]
        ].copy()
        df_deudas_edit["fecha_pago"] = df_deudas_edit["fecha_pago"].astype(str)

        deudas_editadas = st.data_editor(
            df_deudas_edit,
            column_config={
                "id": st.column_config.NumberColumn("ID", disabled=True),
                "persona": st.column_config.TextColumn("Persona / Entidad"),
                "tipo": st.column_config.SelectboxColumn(
                    "Tipo", options=["Me deben", "Debo"]
                ),
                "monto": st.column_config.NumberColumn(
                    "Monto ($)", min_value=0.0, format="$%f"
                ),
                "fecha_pago": st.column_config.TextColumn(
                    "Fecha Est. (AAAA-MM-DD)"
                ),
                "detalle": st.column_config.TextColumn("Detalle"),
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
              "💾 Guardar Cambios en Deudas",
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
              recargar_app("Cuentas corrientes actualizadas exitosamente.")
            except Exception as e:
              st.error(f"Error al actualizar las deudas: {e}")

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
                recargar_app(f"Deuda ID {id_del_deuda} eliminada.")
              except Exception as e:
                st.error("Error al eliminar.")
            else:
                st.error("ID no encontrado.")
      else:
        st.info("No hay cuentas corrientes registradas.")

  # ------------------------------------
  # 2. VENCIMIENTOS (EDITABLE TOTAL)
  # ------------------------------------
  elif "Vencimientos" in sub_t4:
    col_v1, col_v2 = st.columns([1, 1.8])
    with col_v1:
      st.subheader("➕ Nuevo Vencimiento")
      con_v = st.text_input(
          "Concepto (Ej: Patente Corsa, VTV, Seguro)", key="tab4_con_v"
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
            st.error("Error al guardar el vencimiento.")
        else:
          st.warning("Ingresá un concepto.")

    with col_v2:
      st.subheader("✏️ Planilla Editable de Vencimientos")
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
                "fecha_vencimiento": st.column_config.TextColumn(
                    "Fecha Venc. (AAAA-MM-DD)"
                ),
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
              "💾 Guardar Cambios en Vencimientos",
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
              st.error(f"Error al actualizar vencimientos: {e}")

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
                recargar_app(f"Vencimiento {id_del_venc} eliminado.")
              except Exception as e:
                st.error("Error al eliminar.")
            else:
                st.error("ID no encontrado.")
      else:
        st.info("No hay vencimientos cargados.")

  # ------------------------------------
  # 3. METAS / SOBRES (EDITABLE TOTAL)
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
        else:
          st.warning("Ingresá un nombre para la meta.")

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
                "nombre": st.column_config.TextColumn("Nombre Meta"),
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

        col_bm1, col_bm2 = st.columns(2)
        with col_bm1:
          if st.button(
              "💾 Guardar Cambios en Metas",
              type="primary",
              key="tab4_btn_update_metas",
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
              st.error(f"Error al actualizar metas: {e}")

        with col_bm2:
          id_del_meta = st.number_input(
              "ID a Eliminar", min_value=0, step=1, key="tab4_id_del_meta"
          )
          if st.button("🗑️ Eliminar Meta", key="tab4_btn_del_meta"):
            if id_del_meta in df_metas["id"].values:
              try:
                supabase.table("metas_ahorro").delete().eq(
                    "id", id_del_meta
                ).execute()
                recargar_app(f"Meta {id_del_meta} eliminada.")
              except Exception as e:
                st.error("Error al eliminar.")
            else:
                st.error("ID no encontrado.")
      else:
        st.info("No hay metas creadas.")

# ==========================================
# PESTAÑA 5: HISTORIAL Y EXCEL (EDITABLE TOTAL)
# ==========================================
with tab5:
  st.header("📝 Historial Editable de Transacciones")
  st.caption(
      "✏️ **Planilla Interactiva:** Podés hacer doble clic en cualquier celda"
      " (Monto, Fecha, Categoría, Descripción) para corregirla y guardar los"
      " cambios directo en la base de datos."
  )

  if not df_transacciones.empty:
    df_trans_edit = df_transacciones[
        ["id", "fecha", "tipo", "categoria", "monto", "descripcion"]
    ].copy()
    df_trans_edit["fecha"] = df_trans_edit["fecha"].astype(str)

    transacciones_editadas = st.data_editor(
        df_trans_edit,
        column_config={
            "id": st.column_config.NumberColumn("ID", disabled=True),
            "fecha": st.column_config.TextColumn("Fecha (AAAA-MM-DD)"),
            "tipo": st.column_config.SelectboxColumn(
                "Tipo",
                options=[
                    "Ingreso Variable",
                    "Ingreso Fijo",
                    "Gasto Variable",
                    "Gasto Fijo",
                ],
            ),
            "categoria": st.column_config.SelectboxColumn(
                "Categoría", options=lista_todas_categorias
            ),
            "monto": st.column_config.NumberColumn(
                "Monto ($)", min_value=0.0, format="$%f"
            ),
            "descripcion": st.column_config.TextColumn("Descripción"),
        },
        hide_index=True,
        use_container_width=True,
        key="tab5_editor_transacciones",
    )

    col_ht1, col_ht2 = st.columns(2)
    with col_ht1:
      if st.button(
          "💾 GUARDAR CAMBIOS EN HISTORIAL",
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
          recargar_app("Historial de movimientos actualizado correctamente.")
        except Exception as e:
          st.error(f"Error al actualizar transacciones: {e}")

    with col_ht2:
      csv_data = df_transacciones.to_csv(
          index=False, sep=";", encoding="utf-8-sig"
      ).encode("utf-8-sig")
      st.download_button(
          label="📥 Descargar Copia en Excel (CSV)",
          data=csv_data,
          file_name=f"finanzas_pro_{date.today()}.csv",
          mime="text/csv",
          key="tab5_btn_download_csv",
      )

    st.markdown("---")
    col_del_t1, col_del_t2 = st.columns(2)
    with col_del_t1:
      id_borrar = st.number_input(
          "ID del movimiento a borrar por completo",
          min_value=0,
          step=1,
          key="tab5_id_borrar",
      )
      if st.button("🗑️ Borrar Movimiento", key="tab5_btn_borrar"):
        if (
            "id" in df_transacciones.columns
            and id_borrar in df_transacciones["id"].values
        ):
          try:
            supabase.table("transacciones").delete().eq(
                "id", id_borrar
            ).execute()
            recargar_app(f"Movimiento {id_borrar} borrado.")
          except Exception as e:
            st.error("Error al borrar el movimiento.")
        else:
          st.error("ID no encontrado en el historial.")
  else:
    st.info("No hay historial de transacciones disponible.")

# ==========================================
# PESTAÑA 6: CONFIGURACIÓN (EDITABLE TOTAL)
# ==========================================
with tab6:
  st.header("⚙️ Ajustes de Categorías y Presupuestos")

  col_cat1, col_cat2 = st.columns([1, 1.8])
  with col_cat1:
    st.subheader("➕ Crear Categoría")
    nuevo_t = st.selectbox(
        "Tipo", ["Gasto", "Ingreso"], key="tab6_nuevo_tipo_cat"
    )
    nuevo_n = st.text_input("Nombre", key="tab6_nuevo_nombre_cat")
    nuevo_c = st.selectbox(
        "Clasificación 50/30/20",
        ["50-Necesidad", "30-Deseo", "Ingreso", "Ahorro/Inversión"],
        key="tab6_nuevo_clase_cat",
    )
    nuevo_l = st.number_input(
        "Límite Mensual ($)",
        min_value=0.0,
        step=1000.0,
        key="tab6_nuevo_limite_cat",
    )

    if st.button("Agregar Categoría", key="tab6_btn_agregar_cat"):
      if nuevo_n:
        try:
          supabase.table("categorias").insert({
              "tipo_general": nuevo_t,
              "nombre": nuevo_n,
              "clase_503020": nuevo_c,
              "limite_mensual": nuevo_l,
          }).execute()
          recargar_app("Categoría agregada.")
        except Exception as e:
          st.error("Error al agregar categoría.")
      else:
        st.warning("Escribí el nombre de la categoría.")

  with col_cat2:
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
            "💾 Guardar Cambios en Categorías",
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
