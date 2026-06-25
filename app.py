import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import io

# Configuración de la página
st.set_page_config(
    page_title="Dashboard de Envíos",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Título principal
st.title("📊 Dashboard de Envíos a Clientes y Sucursales")
st.markdown("---")

# -------------------------------
# 1. Carga de archivo
# -------------------------------
uploaded_file = st.sidebar.file_uploader(
    "Carga tu archivo (Excel o CSV)",
    type=["xlsx", "csv"]
)

if uploaded_file is None:
    st.info("👈 Sube un archivo con los datos para comenzar")
    st.stop()

# Leer el archivo según su extensión
try:
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file, encoding='utf-8')
    else:
        df = pd.read_excel(uploaded_file, engine='openpyxl')
except Exception as e:
    st.error(f"Error al leer el archivo: {e}")
    st.stop()

# -------------------------------
# 2. Validación de columnas requeridas
# -------------------------------
columnas_requeridas = [
    "Documento", "Salida", "Numero", "Fecha", "Est.",
    "Articulo", "Descripcion", "Linea", "Cantidad",
    "Precio", "Importe", "Peso X Pza", "Peso Total"
]

columnas_faltantes = [col for col in columnas_requeridas if col not in df.columns]
if columnas_faltantes:
    st.error(f"El archivo no contiene las columnas requeridas: {', '.join(columnas_faltantes)}")
    st.write("Columnas encontradas:", list(df.columns))
    st.stop()

# Convertir columna Fecha a datetime
df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
# Eliminar filas con fecha inválida
df = df.dropna(subset=['Fecha'])

# -------------------------------
# 3. Filtros en la barra lateral
# -------------------------------
st.sidebar.header("⚙️ Filtros")

# -- Filtro de fechas --
fecha_min = df['Fecha'].min().date()
fecha_max = df['Fecha'].max().date()

opcion_fecha = st.sidebar.radio(
    "Período de tiempo",
    ["Rango personalizado", "Hoy", "Últimos 7 días", "Este mes", "Este trimestre", "Este año"]
)

if opcion_fecha == "Rango personalizado":
    fecha_inicio = st.sidebar.date_input("Fecha inicio", fecha_min, min_value=fecha_min, max_value=fecha_max)
    fecha_fin = st.sidebar.date_input("Fecha fin", fecha_max, min_value=fecha_min, max_value=fecha_max)
else:
    hoy = datetime.today().date()
    if opcion_fecha == "Hoy":
        fecha_inicio = hoy
        fecha_fin = hoy
    elif opcion_fecha == "Últimos 7 días":
        fecha_inicio = hoy - timedelta(days=7)
        fecha_fin = hoy
    elif opcion_fecha == "Este mes":
        fecha_inicio = hoy.replace(day=1)
        fecha_fin = hoy
    elif opcion_fecha == "Este trimestre":
        mes_actual = hoy.month
        trimestre = ((mes_actual - 1) // 3) * 3 + 1
        fecha_inicio = hoy.replace(month=trimestre, day=1)
        fecha_fin = hoy
    elif opcion_fecha == "Este año":
        fecha_inicio = hoy.replace(month=1, day=1)
        fecha_fin = hoy

# Aplicar filtro de fecha
df_filtrado = df[(df['Fecha'].dt.date >= fecha_inicio) & (df['Fecha'].dt.date <= fecha_fin)]

# -- Filtro de cliente/sucursal (columna 'Salida') --
clientes = sorted(df_filtrado['Salida'].unique())
clientes_seleccionados = st.sidebar.multiselect(
    "Selecciona Cliente/Sucursal",
    options=clientes,
    default=clientes
)

if clientes_seleccionados:
    df_filtrado = df_filtrado[df_filtrado['Salida'].isin(clientes_seleccionados)]

# -------------------------------
# 4. Métricas principales
# -------------------------------
total_piezas = df_filtrado['Cantidad'].sum()
total_importe = df_filtrado['Importe'].sum()
total_peso = df_filtrado['Peso Total'].sum()
num_documentos = df_filtrado['Documento'].nunique()

col1, col2, col3, col4 = st.columns(4)
col1.metric("📦 Piezas enviadas", f"{total_piezas:,.0f}")
col2.metric("💰 Importe total", f"${total_importe:,.2f}")
col3.metric("⚖️ Peso total (kg)", f"{total_peso:,.2f}")
col4.metric("📄 Documentos", f"{num_documentos}")

st.markdown("---")

# -------------------------------
# 5. Gráficos
# -------------------------------
# 5.1 Evolución temporal (agrupado por día, semana o mes)
st.subheader("📈 Evolución temporal")
agrupacion = st.radio(
    "Agrupar por",
    ["Día", "Semana", "Mes"],
    horizontal=True
)

if agrupacion == "Día":
    df_agrupado = df_filtrado.groupby(df_filtrado['Fecha'].dt.date).agg({
        'Cantidad': 'sum',
        'Importe': 'sum',
        'Peso Total': 'sum'
    }).reset_index()
    df_agrupado.rename(columns={'Fecha': 'Periodo'}, inplace=True)
    x_label = "Fecha"
elif agrupacion == "Semana":
    df_filtrado['Semana'] = df_filtrado['Fecha'].dt.to_period('W').apply(lambda r: r.start_time)
    df_agrupado = df_filtrado.groupby('Semana').agg({
        'Cantidad': 'sum',
        'Importe': 'sum',
        'Peso Total': 'sum'
    }).reset_index()
    df_agrupado.rename(columns={'Semana': 'Periodo'}, inplace=True)
    x_label = "Semana (inicio)"
else:  # Mes
    df_filtrado['Mes'] = df_filtrado['Fecha'].dt.to_period('M').apply(lambda r: r.start_time)
    df_agrupado = df_filtrado.groupby('Mes').agg({
        'Cantidad': 'sum',
        'Importe': 'sum',
        'Peso Total': 'sum'
    }).reset_index()
    df_agrupado.rename(columns={'Mes': 'Periodo'}, inplace=True)
    x_label = "Mes"

# Gráfico de barras apiladas o líneas para importe y cantidad
fig_evol = go.Figure()
fig_evol.add_trace(go.Bar(
    x=df_agrupado['Periodo'],
    y=df_agrupado['Cantidad'],
    name='Cantidad',
    yaxis='y1',
    marker_color='#1f77b4'
))
fig_evol.add_trace(go.Scatter(
    x=df_agrupado['Periodo'],
    y=df_agrupado['Importe'],
    name='Importe',
    yaxis='y2',
    marker_color='#ff7f0e',
    line=dict(width=3)
))
fig_evol.update_layout(
    xaxis_title=x_label,
    yaxis=dict(title="Cantidad", side='left'),
    yaxis2=dict(title="Importe", overlaying='y', side='right'),
    legend=dict(x=0.01, y=0.99),
    hovermode='x unified'
)
st.plotly_chart(fig_evol, use_container_width=True)

# 5.2 Distribución por cliente (Salida)
st.subheader("🏢 Distribución por Cliente/Sucursal")
col_graf1, col_graf2 = st.columns(2)

with col_graf1:
    # Importe por cliente
    df_cliente_importe = df_filtrado.groupby('Salida')['Importe'].sum().reset_index()
    df_cliente_importe = df_cliente_importe.sort_values('Importe', ascending=False).head(10)
    fig_cliente_importe = px.bar(
        df_cliente_importe,
        x='Salida',
        y='Importe',
        title='Top 10 por Importe',
        labels={'Salida': 'Cliente/Sucursal', 'Importe': 'Importe total'},
        color='Importe',
        color_continuous_scale='Blues'
    )
    st.plotly_chart(fig_cliente_importe, use_container_width=True)

with col_graf2:
    # Cantidad por cliente
    df_cliente_cant = df_filtrado.groupby('Salida')['Cantidad'].sum().reset_index()
    df_cliente_cant = df_cliente_cant.sort_values('Cantidad', ascending=False).head(10)
    fig_cliente_cant = px.bar(
        df_cliente_cant,
        x='Salida',
        y='Cantidad',
        title='Top 10 por Cantidad',
        labels={'Salida': 'Cliente/Sucursal', 'Cantidad': 'Piezas enviadas'},
        color='Cantidad',
        color_continuous_scale='Greens'
    )
    st.plotly_chart(fig_cliente_cant, use_container_width=True)

# 5.3 Top artículos
st.subheader("📦 Top Artículos")
col_art1, col_art2 = st.columns(2)

with col_art1:
    top_articulos_importe = df_filtrado.groupby('Articulo')['Importe'].sum().reset_index()
    top_articulos_importe = top_articulos_importe.sort_values('Importe', ascending=False).head(10)
    fig_art_importe = px.bar(
        top_articulos_importe,
        x='Articulo',
        y='Importe',
        title='Top 10 por Importe',
        labels={'Articulo': 'Artículo', 'Importe': 'Importe total'},
        color='Importe',
        color_continuous_scale='Oranges'
    )
    st.plotly_chart(fig_art_importe, use_container_width=True)

with col_art2:
    top_articulos_cant = df_filtrado.groupby('Articulo')['Cantidad'].sum().reset_index()
    top_articulos_cant = top_articulos_cant.sort_values('Cantidad', ascending=False).head(10)
    fig_art_cant = px.bar(
        top_articulos_cant,
        x='Articulo',
        y='Cantidad',
        title='Top 10 por Cantidad',
        labels={'Articulo': 'Artículo', 'Cantidad': 'Piezas enviadas'},
        color='Cantidad',
        color_continuous_scale='Purples'
    )
    st.plotly_chart(fig_art_cant, use_container_width=True)

# 5.4 Distribución por Línea
st.subheader("📊 Distribución por Línea")
df_linea = df_filtrado.groupby('Linea').agg({
    'Cantidad': 'sum',
    'Importe': 'sum'
}).reset_index()
fig_linea = px.pie(
    df_linea,
    values='Importe',
    names='Linea',
    title='Importe por Línea',
    hole=0.4,
    color_discrete_sequence=px.colors.qualitative.Set2
)
st.plotly_chart(fig_linea, use_container_width=True)

# -------------------------------
# 6. Tabla de datos filtrados
# -------------------------------
st.subheader("📋 Datos filtrados")
st.dataframe(
    df_filtrado,
    use_container_width=True,
    column_config={
        "Fecha": st.column_config.DatetimeColumn(format="DD/MM/YYYY"),
        "Importe": st.column_config.NumberColumn(format="$%.2f"),
        "Precio": st.column_config.NumberColumn(format="$%.2f"),
        "Peso X Pza": st.column_config.NumberColumn(format="%.3f"),
        "Peso Total": st.column_config.NumberColumn(format="%.3f"),
    }
)

# Botón para descargar datos filtrados
@st.cache_data
def convert_df_to_csv(dataframe):
    return dataframe.to_csv(index=False).encode('utf-8')

csv = convert_df_to_csv(df_filtrado)
st.download_button(
    label="⬇️ Descargar datos filtrados (CSV)",
    data=csv,
    file_name=f"envios_filtrados_{datetime.now().strftime('%Y%m%d')}.csv",
    mime="text/csv",
)

# -------------------------------
# 7. Nota final
# -------------------------------
st.sidebar.markdown("---")
st.sidebar.info(
    "📌 **Columnas esperadas:**\n"
    "Documento, Salida, Numero, Fecha, Est., Articulo, Descripcion, Linea, "
    "Cantidad, Precio, Importe, Peso X Pza, Peso Total"
)