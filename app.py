import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import holidays

# Configuración de la página
st.set_page_config(
    page_title="Dashboard de Envíos",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("📊 Dashboard de Envíos a Clientes y Sucursales")
st.markdown("---")

# ---------------------------------------
# Barra lateral - Carga y filtros
# ---------------------------------------
uploaded_file = st.sidebar.file_uploader(
    "Carga tu archivo (Excel o CSV)",
    type=["xlsx", "csv"]
)

if uploaded_file is None:
    st.info("👈 Sube un archivo con los datos para comenzar")
    st.stop()

# Leer archivo
try:
    if uploaded_file.name.endswith('.csv'):
        df = pd.read_csv(uploaded_file, encoding='utf-8')
    else:
        df = pd.read_excel(uploaded_file, engine='openpyxl')
except Exception as e:
    st.error(f"Error al leer el archivo: {e}")
    st.stop()

# Conversión robusta de columnas numéricas
columnas_numericas = ['Cantidad', 'Precio', 'Importe', 'Peso X Pza', 'Peso Total']
for col in columnas_numericas:
    if col in df.columns:
        df[col] = df[col].astype(str).str.replace(r'[\$,]', '', regex=True).str.strip()
        df[col] = pd.to_numeric(df[col], errors='coerce')

# Validar columnas requeridas
columnas_requeridas = [
    "Documento", "Salida", "Doc.", "Numero", "Fecha", "Est.",
    "Articulo", "Descripcion", "Linea", "Cantidad",
    "Precio", "Importe", "Peso X Pza", "Peso Total"
]
faltantes = [c for c in columnas_requeridas if c not in df.columns]
if faltantes:
    st.error(f"Columnas faltantes: {', '.join(faltantes)}")
    st.write("Columnas encontradas:", list(df.columns))
    st.stop()

# Convertir Fecha
df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
df = df.dropna(subset=['Fecha'])

# ---------------------------------------
# Filtros en barra lateral
# ---------------------------------------
st.sidebar.header("⚙️ Filtros")

# Filtro de fechas
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

df_filtrado = df[(df['Fecha'].dt.date >= fecha_inicio) & (df['Fecha'].dt.date <= fecha_fin)]

# Filtro de cliente/sucursal (incluir)
clientes = sorted(df_filtrado['Salida'].unique())
clientes_seleccionados = st.sidebar.multiselect(
    "Selecciona Cliente/Sucursal",
    options=clientes,
    default=clientes
)
if clientes_seleccionados:
    df_filtrado = df_filtrado[df_filtrado['Salida'].isin(clientes_seleccionados)]

# Filtro de exclusión de clientes/sucursales
clientes_excluir = st.sidebar.multiselect(
    "Excluir Cliente/Sucursal",
    options=sorted(df_filtrado['Salida'].unique()),
    default=[]
)
if clientes_excluir:
    df_filtrado = df_filtrado[~df_filtrado['Salida'].isin(clientes_excluir)]

# ---------------------------------------
# Métricas principales
# ---------------------------------------
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

# ---------------------------------------
# REPORTE SEMANAL (excluyendo domingos)
# ---------------------------------------
st.subheader("📈 Reporte Semanal (Lunes a Sábado) - Toneladas e Importe")

# Filtrar domingos (dayofweek=6)
df_semanal = df_filtrado[df_filtrado['Fecha'].dt.dayofweek != 6].copy()

if df_semanal.empty:
    st.warning("No hay datos para fechas de lunes a sábado en el período seleccionado.")
else:
    # Agrupar por semana (inicio lunes)
    df_semanal['Semana'] = df_semanal['Fecha'].dt.to_period('W-MON').apply(lambda r: r.start_time)
    df_agrupado_sem = df_semanal.groupby('Semana').agg({
        'Cantidad': 'sum',
        'Importe': 'sum',
        'Peso Total': 'sum'
    }).reset_index()
    df_agrupado_sem['Toneladas'] = df_agrupado_sem['Peso Total'] / 1000.0

    # Detectar festivos en México (por semana)
    mx_holidays = holidays.MX()
    # Función para saber si una semana tiene festivo
    def tiene_festivo(semana_inicio):
        # semana_inicio es datetime
        fin_semana = semana_inicio + timedelta(days=5)  # sábado
        for d in (semana_inicio + timedelta(days=i) for i in range(6)):
            if d in mx_holidays:
                return True
        return False

    df_agrupado_sem['Festivo'] = df_agrupado_sem['Semana'].apply(tiene_festivo)

    # Gráfico: barras toneladas + línea importe
    fig_sem = go.Figure()
    fig_sem.add_trace(go.Bar(
        x=df_agrupado_sem['Semana'],
        y=df_agrupado_sem['Toneladas'],
        name='Toneladas',
        yaxis='y1',
        marker_color='#1f77b4'
    ))
    fig_sem.add_trace(go.Scatter(
        x=df_agrupado_sem['Semana'],
        y=df_agrupado_sem['Importe'],
        name='Importe',
        yaxis='y2',
        marker_color='#ff7f0e',
        line=dict(width=3)
    ))

    # Añadir anotaciones para semanas con festivo
    for idx, row in df_agrupado_sem.iterrows():
        if row['Festivo']:
            fig_sem.add_annotation(
                x=row['Semana'],
                y=row['Toneladas'] * 0.9,  # ajustar altura
                text="🎉 Festivo",
                showarrow=True,
                arrowhead=2,
                arrowsize=1,
                arrowwidth=2,
                arrowcolor="red"
            )

    fig_sem.update_layout(
        xaxis_title="Semana (inicio lunes)",
        yaxis=dict(title="Toneladas", side='left'),
        yaxis2=dict(title="Importe", overlaying='y', side='right'),
        legend=dict(x=0.01, y=0.99),
        hovermode='x unified'
    )
    st.plotly_chart(fig_sem, use_container_width=True)

    # Promedios y metas
    promedio_ton = df_agrupado_sem['Toneladas'].mean()
    promedio_imp = df_agrupado_sem['Importe'].mean()

    col_meta1, col_meta2 = st.columns(2)
    meta_ton = col_meta1.number_input("Meta semanal (toneladas)", min_value=0.0, value=round(promedio_ton, 2), step=0.1)
    meta_imp = col_meta2.number_input("Meta semanal (importe $)", min_value=0.0, value=round(promedio_imp, 2), step=100.0)

    # Mostrar promedio y comparación
    st.write(f"**Promedio real semanal:** {promedio_ton:.2f} toneladas | ${promedio_imp:,.2f} de importe")
    if meta_ton > 0:
        diff_ton = promedio_ton - meta_ton
        pct_ton = (diff_ton / meta_ton) * 100 if meta_ton != 0 else 0
        st.write(f"📊 **Meta vs Real (toneladas):** {meta_ton:.2f} vs {promedio_ton:.2f} → {diff_ton:+.2f} ({pct_ton:+.1f}%)")
    if meta_imp > 0:
        diff_imp = promedio_imp - meta_imp
        pct_imp = (diff_imp / meta_imp) * 100 if meta_imp != 0 else 0
        st.write(f"📊 **Meta vs Real (importe):** ${meta_imp:,.2f} vs ${promedio_imp:,.2f} → {diff_imp:+,.2f} ({pct_imp:+.1f}%)")

    # Agregar línea de meta en el gráfico (opcional)
    if meta_ton > 0:
        fig_sem.add_hline(y=meta_ton, line_dash="dash", line_color="green", yref="y1",
                          annotation_text=f"Meta ton {meta_ton}", annotation_position="top right")
    if meta_imp > 0:
        fig_sem.add_hline(y=meta_imp, line_dash="dash", line_color="red", yref="y2",
                          annotation_text=f"Meta importe ${meta_imp:,.0f}", annotation_position="bottom right")
    st.plotly_chart(fig_sem, use_container_width=True)

    # Tabla resumen semanal
    st.subheader("📋 Resumen semanal")
    st.dataframe(
        df_agrupado_sem[['Semana', 'Cantidad', 'Importe', 'Toneladas', 'Festivo']],
        use_container_width=True,
        column_config={
            "Semana": "Inicio de semana",
            "Cantidad": "Piezas",
            "Importe": st.column_config.NumberColumn(format="$%.2f"),
            "Toneladas": st.column_config.NumberColumn(format="%.3f"),
            "Festivo": "¿Contiene festivo?"
        }
    )

st.markdown("---")

# ---------------------------------------
# Gráficos adicionales (usando Descripcion)
# ---------------------------------------
st.subheader("🏢 Distribución por Cliente/Sucursal")
col_graf1, col_graf2 = st.columns(2)

with col_graf1:
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

# Top artículos (usando Descripcion)
st.subheader("📦 Top Artículos (por Descripción)")
col_art1, col_art2 = st.columns(2)

with col_art1:
    top_articulos_importe = df_filtrado.groupby('Descripcion')['Importe'].sum().reset_index()
    top_articulos_importe = top_articulos_importe.sort_values('Importe', ascending=False).head(10)
    fig_art_importe = px.bar(
        top_articulos_importe,
        x='Descripcion',
        y='Importe',
        title='Top 10 por Importe',
        labels={'Descripcion': 'Artículo', 'Importe': 'Importe total'},
        color='Importe',
        color_continuous_scale='Oranges'
    )
    st.plotly_chart(fig_art_importe, use_container_width=True)

with col_art2:
    top_articulos_cant = df_filtrado.groupby('Descripcion')['Cantidad'].sum().reset_index()
    top_articulos_cant = top_articulos_cant.sort_values('Cantidad', ascending=False).head(10)
    fig_art_cant = px.bar(
        top_articulos_cant,
        x='Descripcion',
        y='Cantidad',
        title='Top 10 por Cantidad',
        labels={'Descripcion': 'Artículo', 'Cantidad': 'Piezas enviadas'},
        color='Cantidad',
        color_continuous_scale='Purples'
    )
    st.plotly_chart(fig_art_cant, use_container_width=True)

# Distribución por Línea
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

# ---------------------------------------
# Tabla de datos con selector de columnas
# ---------------------------------------
st.subheader("📋 Datos filtrados")

# Selector de columnas visibles
columnas_disponibles = list(df_filtrado.columns)
columnas_por_defecto = ['Fecha', 'Salida', 'Descripcion', 'Cantidad', 'Importe', 'Peso Total']
columnas_seleccionadas = st.multiselect(
    "Selecciona las columnas a mostrar",
    options=columnas_disponibles,
    default=[col for col in columnas_por_defecto if col in columnas_disponibles]
)

if columnas_seleccionadas:
    df_mostrar = df_filtrado[columnas_seleccionadas]
else:
    df_mostrar = df_filtrado

st.dataframe(
    df_mostrar,
    use_container_width=True,
    column_config={
        "Fecha": st.column_config.DatetimeColumn(format="DD/MM/YYYY"),
        "Importe": st.column_config.NumberColumn(format="$%.2f"),
        "Precio": st.column_config.NumberColumn(format="$%.2f"),
        "Peso X Pza": st.column_config.NumberColumn(format="%.3f"),
        "Peso Total": st.column_config.NumberColumn(format="%.3f"),
    }
)

# Descargar solo columnas seleccionadas
@st.cache_data
def convert_df_to_csv(dataframe):
    return dataframe.to_csv(index=False).encode('utf-8')

csv = convert_df_to_csv(df_mostrar)
st.download_button(
    label="⬇️ Descargar datos filtrados (CSV)",
    data=csv,
    file_name=f"envios_filtrados_{datetime.now().strftime('%Y%m%d')}.csv",
    mime="text/csv",
)

# Nota de festivos en la barra lateral
st.sidebar.markdown("---")
st.sidebar.info(
    "📌 **Columnas esperadas:**\n"
    "Documento, Salida, Numero, Fecha, Est., Articulo, Descripcion, Linea, "
    "Cantidad, Precio, Importe, Peso X Pza, Peso Total\n\n"
    "🔔 **Festivos México** detectados automáticamente."
)
