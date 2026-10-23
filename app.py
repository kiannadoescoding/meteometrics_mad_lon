import pandas as pd
import requests

url_mad = "https://meteometrics.rlopez.org/historical-data/MAD"
url_lon = "https://meteometrics.rlopez.org/historical-data/LON"

try:
    # Realiza la petición para Madrid
    response = requests.get(url_mad)
    response.raise_for_status()
    raw_data_madrid = response.json()

    # Realiza la petición para Londres
    response = requests.get(url_lon)
    response.raise_for_status()
    raw_data_londres = response.json()

    data_madrid = pd.json_normalize(raw_data_madrid)
    data_madrid["city"] = "Madrid"
    data_londres = pd.json_normalize(raw_data_londres)
    data_londres["city"] = "Londres"
    combined_data = pd.concat([data_madrid, data_londres], ignore_index=True)

    # Guarda el total original para resumir cuantas filas elimina el deduplicado.
    initial_records = len(combined_data)

    unit_columns = [
        "metrics.temperature.unit",
        "metrics.precipitation.unit",
    ]
    metric_columns = combined_data.columns[
        combined_data.columns.str.startswith("metrics.")
        & ~combined_data.columns.isin(unit_columns)
    ]

    # Corrige primero los decimales escritos con coma en las metricas.
    combined_data[metric_columns] = combined_data[metric_columns].replace(",", ".", regex=True)

    # Convierte todas las columnas de datos a numeros, excepto ciudad y unidades.
    numeric_columns = combined_data.columns[
        ~combined_data.columns.isin(unit_columns + ["city"])
    ]
    combined_data[numeric_columns] = combined_data[numeric_columns].apply(
        pd.to_numeric, errors="coerce"
    )

    # Trata el valor sentinela como un dato ausente.
    combined_data[numeric_columns] = combined_data[numeric_columns].replace(
        -999.0, float("nan")
    )

    # Conserva una sola fila por ciudad, año y mes, y cuenta las eliminadas.
    combined_data = combined_data.drop_duplicates(
        subset=["city", "year", "month"]
    )
    deleted_records = initial_records - len(combined_data)

    # Ordena los registros antes de aplicar las conversiones de unidades.
    combined_data = combined_data.sort_values(
        ["city", "year", "month"], ignore_index=True
    )

    # Convierte temperaturas Fahrenheit a Celsius solo donde la unidad lo indica.
    fahrenheit_rows = combined_data["metrics.temperature.unit"].eq("F")
    temperature_columns = [
        "metrics.temperature.max",
        "metrics.temperature.avg",
        "metrics.temperature.min",
    ]
    combined_data.loc[fahrenheit_rows, temperature_columns] = (
        combined_data.loc[fahrenheit_rows, temperature_columns] - 32
    ) * 5 / 9
    combined_data.loc[fahrenheit_rows, "metrics.temperature.unit"] = "C"

    # Convierte pulgadas a milimetros solo para las filas expresadas en inches.
    inches_rows = combined_data["metrics.precipitation.unit"].eq("inches")
    combined_data.loc[inches_rows, "metrics.precipitation.avg"] *= 25.4
    combined_data.loc[inches_rows, "metrics.precipitation.unit"] = "mm"

    # Escribe un resumen de los registros antes y despues de la limpieza.
    with open("informe_limpieza.txt", "w", encoding="utf-8") as report:
        report.write(f"Registros iniciales: {initial_records}\n")
        report.write(f"Registros borrados: {deleted_records}\n")
        report.write(f"Registros finales: {len(combined_data)}\n")

    print(combined_data)

except requests.exceptions.RequestException as error:
    print(f"Error al obtener los datos meteorológicos: {error}")