import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
from plotly.subplots import make_subplots


CITY_URLS = {
    "Madrid": "https://meteometrics.rlopez.org/historical-data/MAD",
    "Londres": "https://meteometrics.rlopez.org/historical-data/LON",
}
CITY_COLORS = {"Madrid": "#cf3f49", "Londres": "#2476a8"}
MONTHS = [
    "Ene", "Feb", "Mar", "Abr", "May", "Jun",
    "Jul", "Ago", "Sep", "Oct", "Nov", "Dic",
]
TEMPERATURE_AVG = "metrics.temperature.avg"
TEMPERATURE_MAX = "metrics.temperature.max"
TEMPERATURE_MIN = "metrics.temperature.min"
PRECIPITATION_AVG = "metrics.precipitation.avg"
TEMPERATURE_UNIT = "metrics.temperature.unit"
PRECIPITATION_UNIT = "metrics.precipitation.unit"
UNIT_COLUMNS = [TEMPERATURE_UNIT, PRECIPITATION_UNIT]

st.set_page_config(
    page_title="Clima | Madrid y Londres",
    page_icon="C",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700;800&display=swap');
    :root {
        --ink: #18292d;
        --muted: #637478;
        --line: #dce5e5;
        --paper: #f4f8f7;
        --surface: #ffffff;
        --red: #cf3f49;
        --blue: #2476a8;
        --mint: #d8efea;
    }
    html, body, [class*="stApp"] {
        font-family: 'Manrope', sans-serif;
        color: var(--ink);
    }
    .stApp { background: var(--paper); }
    [data-testid="stHeader"] { background: rgba(244, 248, 247, 0.88); }
    .block-container { max-width: 1320px; padding-top: 2.2rem; padding-bottom: 3rem; }
    h1, h2, h3 { color: var(--ink); }
    h1 { font-size: 2.35rem !important; font-weight: 800 !important; }
    h2 { font-size: 1.3rem !important; font-weight: 700 !important; }
    .eyebrow {
        color: #35645f; font-family: 'DM Mono', monospace; font-size: .75rem;
        text-transform: uppercase; letter-spacing: 0; margin-bottom: .35rem;
    }
    .subtitle { color: var(--muted); margin-top: -.55rem; margin-bottom: 1.6rem; }
    .section-label {
        border-top: 1px solid var(--line); padding-top: 1rem; margin-top: .5rem;
        color: #35645f; font-family: 'DM Mono', monospace; font-size: .72rem;
        text-transform: uppercase; letter-spacing: 0;
    }
    .city-name { font-size: 1.15rem; font-weight: 800; margin: .2rem 0 .15rem; }
    .city-date { color: var(--muted); font-family: 'DM Mono', monospace; font-size: .76rem; margin-bottom: .4rem; }
    [data-testid="stMetric"] {
        background: var(--surface); border: 1px solid var(--line); border-radius: 6px;
        padding: .9rem 1rem;
    }
    [data-testid="stMetricLabel"] { color: var(--muted); }
    [data-testid="stMetricValue"] { color: var(--ink); font-weight: 700; }
    [data-testid="stAlert"] { border-radius: 6px; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(ttl=3600, show_spinner="Cargando observaciones meteorológicas...")
def load_weather_data():
    madrid_response = requests.get(CITY_URLS["Madrid"], timeout=30)
    madrid_response.raise_for_status()
    london_response = requests.get(CITY_URLS["Londres"], timeout=30)
    london_response.raise_for_status()

    madrid = pd.json_normalize(madrid_response.json())
    madrid["city"] = "Madrid"
    london = pd.json_normalize(london_response.json())
    london["city"] = "Londres"
    data = pd.concat([madrid, london], ignore_index=True)

    # Normaliza decimales y convierte las métricas a valores numéricos.
    metric_columns = data.columns[
        data.columns.str.startswith("metrics.")
        & ~data.columns.isin(UNIT_COLUMNS)
    ]
    data[metric_columns] = data[metric_columns].replace(",", ".", regex=True)
    numeric_columns = data.columns[
        ~data.columns.isin(UNIT_COLUMNS + ["city"])
    ]
    data[numeric_columns] = data[numeric_columns].apply(
        pd.to_numeric, errors="coerce"
    )
    data[numeric_columns] = data[numeric_columns].replace(-999.0, float("nan"))

    # Deduplica cada mes, ordena y unifica las unidades meteorológicas.
    data = data.drop_duplicates(subset=["city", "year", "month"])
    data = data.sort_values(["city", "year", "month"], ignore_index=True)
    fahrenheit_rows = data[TEMPERATURE_UNIT].eq("F")
    temperature_columns = [TEMPERATURE_MAX, TEMPERATURE_AVG, TEMPERATURE_MIN]
    data.loc[fahrenheit_rows, temperature_columns] = (
        data.loc[fahrenheit_rows, temperature_columns] - 32
    ) * 5 / 9
    data.loc[fahrenheit_rows, TEMPERATURE_UNIT] = "C"

    inches_rows = data[PRECIPITATION_UNIT].eq("inches")
    data.loc[inches_rows, PRECIPITATION_AVG] *= 25.4
    data.loc[inches_rows, PRECIPITATION_UNIT] = "mm"
    data["date"] = pd.to_datetime(
        dict(year=data["year"], month=data["month"], day=1), errors="coerce"
    )
    return data


def render_city_snapshot(column, city, latest_row):
    color = CITY_COLORS[city]
    month_label = MONTHS[int(latest_row["month"]) - 1]
    column.markdown(
        f'<div class="city-name" style="color:{color}">{city}</div>'
        f'<div class="city-date">{month_label} {int(latest_row["year"])}</div>',
        unsafe_allow_html=True,
    )
    column.metric(
        "Temperatura media",
        f"{latest_row[TEMPERATURE_AVG]:.1f} °C"
        if pd.notna(latest_row[TEMPERATURE_AVG]) else "Sin datos",
    )
    column.metric(
        "Precipitación media",
        f"{latest_row[PRECIPITATION_AVG]:.1f} mm"
        if pd.notna(latest_row[PRECIPITATION_AVG]) else "Sin datos",
    )


def make_range_chart(data):
    figure = go.Figure()
    fill_colors = {"Madrid": "rgba(207, 63, 73, 0.15)", "Londres": "rgba(36, 118, 168, 0.15)"}

    for city, color in CITY_COLORS.items():
        city_data = data[data["city"].eq(city)].sort_values("date")
        if city_data.empty:
            continue

        # La banda se rellena entre la línea mínima y la máxima de cada ciudad.
        figure.add_trace(go.Scatter(
            x=city_data["date"], y=city_data[TEMPERATURE_MAX],
            mode="lines", line={"width": 0, "color": color},
            showlegend=False, hoverinfo="skip", legendgroup=city,
        ))
        figure.add_trace(go.Scatter(
            x=city_data["date"], y=city_data[TEMPERATURE_MIN],
            mode="lines", line={"width": 0, "color": color},
            fill="tonexty", fillcolor=fill_colors[city],
            name=f"{city} · rango", showlegend=False, legendgroup=city,
            hovertemplate="%{x|%b %Y}<br>Mínima: %{y:.1f} °C<extra>" + city + "</extra>",
        ))
        figure.add_trace(go.Scatter(
            x=city_data["date"], y=city_data[TEMPERATURE_AVG],
            mode="lines", name=city, legendgroup=city,
            line={"color": color, "width": 2.5},
            hovertemplate="%{x|%b %Y}<br>Media: %{y:.1f} °C<extra>" + city + "</extra>",
        ))

    figure.update_layout(
        height=440, margin={"l": 10, "r": 20, "t": 20, "b": 10},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Manrope, sans-serif", "color": "#18292d"},
        legend={"orientation": "h", "y": 1.08, "x": 0},
        hovermode="x unified",
    )
    figure.update_xaxes(showgrid=False, tickformat="%b\n%Y", title=None)
    figure.update_yaxes(title="Temperatura (°C)", gridcolor="#e2eaea", zeroline=False)
    return figure


def make_radar_chart(data):
    monthly = data.groupby(["city", "month"], as_index=False)[
        [TEMPERATURE_AVG, PRECIPITATION_AVG]
    ].mean()
    figure = make_subplots(
        rows=1, cols=2,
        specs=[[{"type": "polar"}, {"type": "polar"}]],
        subplot_titles=("Temperatura media · °C", "Precipitación media · mm"),
        horizontal_spacing=0.12,
    )
    theta = MONTHS + [MONTHS[0]]

    for city, color in CITY_COLORS.items():
        city_months = monthly[monthly["city"].eq(city)].set_index("month")
        if city_months.empty:
            continue
        for column_index, metric in enumerate(
            [TEMPERATURE_AVG, PRECIPITATION_AVG], start=1
        ):
            values = city_months[metric].reindex(range(1, 13)).tolist()
            figure.add_trace(go.Scatterpolar(
                r=values + [values[0]], theta=theta, name=city,
                mode="lines+markers", line={"color": color, "width": 2.5},
                marker={"size": 5}, fill="toself",
                fillcolor=("rgba(207, 63, 73, 0.08)" if city == "Madrid"
                           else "rgba(36, 118, 168, 0.08)"),
                showlegend=column_index == 1,
                hovertemplate="%{theta}<br>%{r:.1f}<extra>" + city + "</extra>",
            ), row=1, col=column_index)

    polar_style = {
        "bgcolor": "rgba(0,0,0,0)",
        "radialaxis": {"gridcolor": "#dce5e5", "linecolor": "#dce5e5"},
        "angularaxis": {"gridcolor": "#e8eeee", "linecolor": "#dce5e5"},
    }
    figure.update_layout(
        height=480, margin={"l": 25, "r": 25, "t": 65, "b": 20},
        paper_bgcolor="rgba(0,0,0,0)", font={"family": "Manrope, sans-serif", "color": "#18292d"},
        legend={"orientation": "h", "y": 1.12, "x": 0.35},
        polar=polar_style, polar2=polar_style,
    )
    figure.update_annotations(font={"size": 14, "color": "#18292d"})
    return figure, monthly


st.markdown('<div class="eyebrow">Observatorio urbano · datos históricos</div>', unsafe_allow_html=True)
st.title("Madrid y Londres, frente a frente")
st.markdown(
    '<p class="subtitle">Temperatura y lluvia en el ritmo de dos ciudades.</p>',
    unsafe_allow_html=True,
)

try:
    weather = load_weather_data()
except (requests.RequestException, KeyError, ValueError) as error:
    st.error(f"No se pudieron cargar los datos meteorológicos: {error}")
    st.stop()

available_years = sorted(weather["year"].dropna().astype(int).unique())
if not available_years:
    st.error("La API no devolvió observaciones con año válido.")
    st.stop()

with st.sidebar:
    st.markdown("### Periodo")
    selected_years = st.slider(
        "Años incluidos",
        min_value=int(available_years[0]),
        max_value=int(available_years[-1]),
        value=(int(available_years[0]), int(available_years[-1])),
        step=1,
    )

selected = weather[weather["year"].between(*selected_years)].copy()
latest_by_city = (
    selected.sort_values("date").groupby("city", as_index=False).tail(1).set_index("city")
)

st.markdown('<div class="section-label">01 / Resumen instantáneo</div>', unsafe_allow_html=True)
st.subheader("La última observación disponible")
summary_columns = st.columns(2, gap="large")
if "Madrid" in latest_by_city.index:
    render_city_snapshot(summary_columns[0], "Madrid", latest_by_city.loc["Madrid"])
if "Londres" in latest_by_city.index:
    render_city_snapshot(summary_columns[1], "Londres", latest_by_city.loc["Londres"])

st.markdown('<div class="section-label">02 / Evolución · banda de rango</div>', unsafe_allow_html=True)
st.subheader("Máximas y mínimas mensuales, con la media en el centro")
st.plotly_chart(make_range_chart(selected), use_container_width=True, theme=None)

shared_dates = selected.groupby("date")["city"].nunique()
shared_dates = shared_dates[shared_dates.eq(2)]
if not shared_dates.empty:
    latest_shared_date = shared_dates.index.max()
    latest_shared = selected[selected["date"].eq(latest_shared_date)].set_index("city")
    madrid_temp = latest_shared.loc["Madrid", TEMPERATURE_AVG]
    london_temp = latest_shared.loc["Londres", TEMPERATURE_AVG]
    delta = madrid_temp - london_temp
    warmer = "Madrid" if delta > 0 else "Londres"
    average_ranges = (
        selected.assign(thermal_range=selected[TEMPERATURE_MAX] - selected[TEMPERATURE_MIN])
        .groupby("city")["thermal_range"].mean()
    )
    broad_range_city = average_ranges.idxmax()
    st.info(
        f"En el último mes compartido ({MONTHS[latest_shared_date.month - 1]} "
        f"{latest_shared_date.year}), {warmer} registró una media {abs(delta):.1f} °C "
        f"más alta. La banda muestra máximas y mínimas mensuales; "
        f"{broad_range_city} presenta el mayor rango térmico medio "
        f"({average_ranges[broad_range_city]:.1f} °C)."
    )

st.markdown('<div class="section-label">03 / Perfil climático · 12 meses</div>', unsafe_allow_html=True)
st.subheader("El ciclo anual de temperatura y precipitación")
radar_figure, monthly_profiles = make_radar_chart(selected)
st.plotly_chart(radar_figure, use_container_width=True, theme=None)

temperature_profile = monthly_profiles.pivot(
    index="month", columns="city", values=TEMPERATURE_AVG
).reindex(range(1, 13))
precipitation_profile = monthly_profiles.groupby("city")[PRECIPITATION_AVG].mean()
if {"Madrid", "Londres"}.issubset(temperature_profile.columns) and {
    "Madrid", "Londres"
}.issubset(precipitation_profile.index):
    warmer_month_count = int(
        (temperature_profile["Madrid"] > temperature_profile["Londres"]).sum()
    )
    wetter_city = "Madrid" if (
        precipitation_profile["Madrid"] > precipitation_profile["Londres"]
    ) else "Londres"
    precipitation_difference = abs(
        precipitation_profile["Madrid"] - precipitation_profile["Londres"]
    )
    st.info(
        f"En el perfil mensual medio, Madrid es más cálida en {warmer_month_count} de "
        f"los 12 meses. {wetter_city} registra una precipitación mensual media mayor, "
        f"por {precipitation_difference:.1f} mm. Los radares separan las escalas "
        f"para que temperatura y lluvia se puedan comparar con sus unidades reales."
    )
