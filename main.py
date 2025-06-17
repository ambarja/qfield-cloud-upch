import os
from qfieldcloud_sdk.sdk import Client, FileTransferType
from pathlib import Path
import geopandas as gpd
import pandas as pd
import datetime
import hashlib
import sqlite3

# Configuración
username = os.environ["QFIELD_USER"]
password = os.environ["QFIELD_PASS"]
project_id = os.environ["QFIELD_PROJECT_ID"]

fecha_actual = datetime.date.today()
fecha_actual_str = fecha_actual.strftime("%Y-%m-%d")

# Rutas
remote_path = "georreferenciacion.gpkg"
local_path = Path("output/georreferenciacion.gpkg")
csv_diario = Path(f"output/georreferenciacion-update-{fecha_actual_str}.csv")
csv_maestro = Path("output/georreferenciacion-update.csv")
# Cliente QFieldCloud
client = Client(url="https://app.qfield.cloud/api/v1/")
client.login(username=username, password=password)

# Descargar archivo GPKG desde QFieldCloud
client.download_file(
    project_id=project_id,
    download_type=FileTransferType.PROJECT,
    local_filename=local_path,
    remote_filename=Path(remote_path),
    show_progress=True
)

# Leer datos y limpiar
gpkg_file = gpd.read_file(local_path, layer='georreferenciacion').dropna()
gpkg_file_nogeom = gpkg_file.drop(columns='geometry')
gpkg_file_nogeom['fecha_peru'] = pd.to_datetime(gpkg_file_nogeom['fecha'], utc=True).dt.tz_convert('America/Lima')
csv_nuevo = gpkg_file_nogeom.drop(columns='fecha')

# Si existe el CSV maestro, comparamos y hacemos append solo de nuevos
if csv_maestro.exists():
    df_antiguo = pd.read_csv(csv_maestro)
    df_total = pd.concat([df_antiguo, csv_nuevo], ignore_index=True).drop_duplicates()
    nuevos_registros = len(df_total) > len(df_antiguo)
else:
    df_total = csv_nuevo
    nuevos_registros = True

# Guardar el CSV diario y actualizar el maestro si hay cambios
csv_nuevo.to_csv(csv_diario, index=False)

if nuevos_registros:
    print("➡ Se detectaron nuevos datos. Actualizando CSV maestro y GPKG...")

    df_total.to_csv(csv_maestro, index=False)

    # Vaciar registros del GPKG sin borrar la tabla (conserva formularios)
    conn = sqlite3.connect(local_path)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM georreferenciacion;")
    conn.commit()
    conn.close()

    # Subir nuevo GPKG vacío
    client.upload_file(
        project_id=project_id,
        upload_type=FileTransferType.PROJECT,
        local_filename=local_path,
        remote_filename=Path(remote_path),
        show_progress=True
    )
else:
    print("✅ No hay nuevos registros. No se modifica GPKG ni CSV maestro.")
