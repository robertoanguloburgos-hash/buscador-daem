"""
Buscador y Validador Presupuestario DAEM
=========================================
Aplicación Streamlit para clasificación presupuestaria de compras públicas
bajo las reglas de Superintendencia de Educación (Superduc) y SEP.

Librerías: streamlit, pandas, difflib (estándar).
"""

import difflib
import io

import pandas as pd
import streamlit as st

# ------------------------------------------------------------------
# CONFIGURACIÓN DE PÁGINA
# ------------------------------------------------------------------
st.set_page_config(
    page_title="Buscador y Validador Presupuestario DAEM",
    page_icon="📊",
    layout="wide",
)

# ------------------------------------------------------------------
# DATOS DE EJEMPLO (se usan si el usuario no sube un CSV propio)
# ------------------------------------------------------------------
def cargar_datos_ejemplo() -> pd.DataFrame:
    data = [
        # codigo_cuenta, nombre_cuenta, superduc_categoria, programa_asociado
        ("215.22.04.001", "Materiales de Oficina", "Materiales de Oficina (Uso Administrativo)", "Fondo General"),
        ("215.22.04.002", "Equipos Menores", "Equipos Menores de Enseñanza", "SEP"),
        ("215.22.04.003", "Textos Escolares y Guías Didácticas", "Textos y Otros Materiales de Enseñanza", "SEP"),
        ("215.22.04.004", "Cuadernos y Papel Kraft", "Textos y Otros Materiales de Enseñanza", "SEP"),
        ("215.22.04.005", "Goma Eva y Silicona Escolar", "Textos y Otros Materiales de Enseñanza", "SEP"),
        ("215.22.04.006", "Notebook Educativo", "Tecnología Educativa", "SEP"),
        ("215.22.04.007", "Proyector Multimedia", "Tecnología Educativa", "SEP"),
        ("215.22.04.008", "Tablet para Aula de Recursos", "Tecnología Educativa", "PIE"),
        ("215.22.04.009", "Pantalla Interactiva", "Tecnología Educativa", "SEP"),
        ("215.29.04.010", "Archivador de Palanca", "Materiales de Oficina (Uso Administrativo)", "Fondo General"),
        ("215.29.04.011", "Perforadora de Escritorio", "Materiales de Oficina (Uso Administrativo)", "Fondo General"),
        ("215.29.04.012", "Goma de Borrar", "Materiales de Oficina (Uso Administrativo)", "Fondo General"),
        ("215.29.04.013", "Alargador Eléctrico 5 Metros", "No Elegible", "No Aplica"),
        ("215.29.04.014", "Zapatilla Eléctrica 6 Enchufes", "No Elegible", "No Aplica"),
        ("215.29.04.015", "Puntero Láser para Presentaciones", "No Elegible", "No Aplica"),
        ("215.22.05.016", "Materiales de Aseo", "Materiales de Aseo", "Fondo General"),
        ("215.22.05.017", "Paño Absorbente Multiuso", "Materiales de Aseo", "Fondo General"),
        ("215.22.04.018", "Equipos de Apoyo PIE - Sala de Recursos", "Materiales de Apoyo PIE", "PIE"),
        ("215.22.04.019", "Material Fungible Laboratorio de Ciencias", "Textos y Otros Materiales de Enseñanza", "SEP"),
        ("215.22.04.020", "Instrumentos Musicales Menores", "Textos y Otros Materiales de Enseñanza", "FAEP"),
    ]
    columnas = ["codigo_cuenta", "nombre_cuenta", "superduc_categoria", "programa_asociado"]
    return pd.DataFrame(data, columns=columnas)


# Mapeo de programa -> Cuenta Corriente DAEM recomendada
CUENTA_CORRIENTE_POR_PROGRAMA = {
    "SEP": "021 BC",
    "PIE": "025 BC",
    "Fondo General": "00100",
    "FAEP": "030 BC",
    "No Aplica": "N/A — Gasto no elegible, no se asigna cuenta corriente",
}


# ------------------------------------------------------------------
# MOTOR DE REGLAS DE CONTROL INTERNO (SEP / SUPERDUC)
# ------------------------------------------------------------------
def analizar_alertas(texto: str):
    """
    Analiza el texto ingresado por el usuario y devuelve una lista de
    tuplas (nivel, mensaje) según las palabras clave detectadas.
    nivel puede ser: 'error', 'warning', 'info'
    """
    texto_lower = texto.lower()
    alertas = []

    reglas = [
        (
            "error",
            ["alargador", "zapatilla", "alargadores"],
            "❌ RECHAZADO BAJO SEP. Los alargadores o extensiones de ningún tipo son "
            "elegibles por no constituir un recurso de carácter pedagógico.",
        ),
        (
            "error",
            ["puntero", "laser", "láser"],
            "❌ RECHAZADO BAJO SEP. Prohibida la adquisición de punteros láser con "
            "fondos de esta subvención.",
        ),
        (
            "warning",
            ["goma", "borrador", "archivador", "perforadora", "oficina"],
            "⚠️ ADVERTENCIA. Los útiles de escritorio de uso puramente administrativo "
            "no pasan por SEP. Si son materiales para uso directo de los estudiantes "
            "en aula (ej. pliegos de goma eva, papel kraft, silicona, cuadernos), "
            "deben clasificarse y autorizarse bajo 'Textos y Otros Materiales de "
            "Enseñanza' con Código 1.",
        ),
        (
            "info",
            ["computador", "notebook", "tablet", "proyector", "pantalla", "tecnología", "tecnologia"],
            "ℹ️ ANÁLISIS DE TECNOLOGÍA. Para su aprobación con fondos SEP, este "
            "artículo requiere obligatoriamente una Especificación Técnica detallada "
            "y una Justificación Pedagógica explícita asociada a la acción PME.",
        ),
        (
            "error",
            ["necesidades especiales", "necesidades docente"],
            "⚠️ RIESGO DE REPARO. Evitar estrictamente incorporar estas frases en las "
            "justificaciones o glosas del PME/SEP, ya que son blanco prioritario de "
            "reparos en las fiscalizaciones de la Superintendencia.",
        ),
    ]

    for nivel, palabras_clave, mensaje in reglas:
        if any(palabra in texto_lower for palabra in palabras_clave):
            alertas.append((nivel, mensaje))

    return alertas


def mostrar_alertas(alertas):
    for nivel, mensaje in alertas:
        if nivel == "error":
            st.error(mensaje)
        elif nivel == "warning":
            st.warning(mensaje)
        elif nivel == "info":
            st.info(mensaje)


# ------------------------------------------------------------------
# BÚSQUEDA DIFUSA (FUZZY MATCHING) CON difflib
# ------------------------------------------------------------------
def buscar_coincidencias(df: pd.DataFrame, consulta: str, n: int = 5) -> pd.DataFrame:
    if not consulta.strip():
        return pd.DataFrame(columns=df.columns)

    consulta_lower = consulta.strip().lower()

    # Universo de texto a comparar: nombre_cuenta + superduc_categoria
    candidatos = {}
    for idx, row in df.iterrows():
        candidatos[str(row["nombre_cuenta"]).lower()] = idx
        candidatos[str(row["superduc_categoria"]).lower()] = idx

    # difflib.get_close_matches sobre las claves de texto
    mejores = difflib.get_close_matches(
        consulta_lower, list(candidatos.keys()), n=n, cutoff=0.3
    )

    # También agregamos coincidencias por substring (más permisivo, típico en
    # búsquedas de artículos con nombres cortos como "paño" o "goma")
    substring_idx = [
        idx
        for idx, row in df.iterrows()
        if consulta_lower in str(row["nombre_cuenta"]).lower()
        or consulta_lower in str(row["superduc_categoria"]).lower()
    ]

    indices_resultado = []
    for texto in mejores:
        idx = candidatos[texto]
        if idx not in indices_resultado:
            indices_resultado.append(idx)
    for idx in substring_idx:
        if idx not in indices_resultado:
            indices_resultado.append(idx)

    indices_resultado = indices_resultado[:n]

    if not indices_resultado:
        return pd.DataFrame(columns=df.columns)

    return df.loc[indices_resultado].reset_index(drop=True)


# ------------------------------------------------------------------
# BARRA LATERAL: CARGA DE ARCHIVO CSV
# ------------------------------------------------------------------
st.sidebar.header("⚙️ Configuración de Datos")
st.sidebar.markdown(
    "Sube tu propia base de cuentas (CSV) o utiliza el set de datos de "
    "ejemplo precargado."
)

archivo_subido = st.sidebar.file_uploader(
    "Sube tu archivo CSV de cuentas", type=["csv"]
)

columnas_requeridas = {
    "codigo_cuenta",
    "nombre_cuenta",
    "superduc_categoria",
    "programa_asociado",
}

if archivo_subido is not None:
    try:
        df_cuentas = pd.read_csv(archivo_subido)
        if not columnas_requeridas.issubset(set(df_cuentas.columns)):
            st.sidebar.error(
                "El CSV no contiene todas las columnas requeridas: "
                + ", ".join(sorted(columnas_requeridas))
            )
            st.sidebar.info("Se cargará el set de datos de ejemplo en su lugar.")
            df_cuentas = cargar_datos_ejemplo()
        else:
            st.sidebar.success(f"Archivo cargado correctamente ({len(df_cuentas)} filas).")
    except Exception as exc:
        st.sidebar.error(f"Error al leer el CSV: {exc}")
        st.sidebar.info("Se cargará el set de datos de ejemplo en su lugar.")
        df_cuentas = cargar_datos_ejemplo()
else:
    df_cuentas = cargar_datos_ejemplo()
    st.sidebar.info("Usando set de datos de ejemplo (20 cuentas precargadas).")

with st.sidebar.expander("📄 Ver formato de CSV esperado"):
    st.code(
        "codigo_cuenta,nombre_cuenta,superduc_categoria,programa_asociado\n"
        "215.22.04.001,Materiales de Oficina,Textos y Otros Materiales de Enseñanza,SEP",
        language="csv",
    )

st.sidebar.markdown("---")
st.sidebar.caption(
    "Motor de reglas SEP / Superduc integrado. Esta herramienta es un apoyo "
    "de control de gestión y no reemplaza el criterio del validador ni la "
    "normativa vigente de la Superintendencia de Educación."
)

# ------------------------------------------------------------------
# ENCABEZADO PRINCIPAL
# ------------------------------------------------------------------
st.title("📊 Buscador y Validador Presupuestario DAEM")
st.markdown(
    """
Herramienta de apoyo al **control de gestión** para la clasificación y
validación presupuestaria de solicitudes de compra bajo las reglas de la
**Subvención Escolar Preferencial (SEP)** y los criterios de fiscalización
de la **Superintendencia de Educación (Superduc)**.

Ingresa el nombre del artículo a adquirir para obtener: (1) alertas de
control interno automáticas, y (2) las cuentas presupuestarias más
cercanas según coincidencia difusa (*fuzzy matching*).
"""
)

st.divider()

# ------------------------------------------------------------------
# BUSCADOR PRINCIPAL
# ------------------------------------------------------------------
consulta = st.text_input(
    "🔍 Escribe el artículo a buscar...",
    placeholder="Ej: computador, paño, goma, archivador, notebook...",
)

if consulta.strip():
    alertas = analizar_alertas(consulta)
    if alertas:
        st.subheader("Alertas de Control Interno")
        mostrar_alertas(alertas)
        st.divider()

    resultados = buscar_coincidencias(df_cuentas, consulta, n=5)

    if resultados.empty:
        st.warning(
            "No se encontraron coincidencias cercanas en la base de cuentas cargada. "
            "Intenta con otro término o revisa el CSV cargado."
        )
    else:
        st.subheader("Cuentas Sugeridas (mejores coincidencias)")
        st.dataframe(resultados, use_container_width=True, hide_index=True)

        st.subheader("📋 Detalle de la Selección")
        opciones = resultados.apply(
            lambda r: f"{r['codigo_cuenta']} — {r['nombre_cuenta']}", axis=1
        ).tolist()
        seleccion = st.selectbox("Selecciona una cuenta para ver su detalle:", opciones)

        if seleccion:
            fila = resultados.iloc[opciones.index(seleccion)]
            programa = str(fila["programa_asociado"])
            cuenta_corriente = CUENTA_CORRIENTE_POR_PROGRAMA.get(
                programa, "No definida — verificar manualmente con Tesorería DAEM"
            )

            st.success(
                f"""
**Código de cuenta (ERP):** `{fila['codigo_cuenta']}`

**Categoría Superduc:** {fila['superduc_categoria']}

**Programa sugerido:** {programa}

**Cuenta Corriente DAEM recomendada:** {cuenta_corriente}
"""
            )
else:
    st.info("Ingresa un término de búsqueda para comenzar la validación.")

# ------------------------------------------------------------------
# VISTA COMPLETA DE LA BASE (OPCIONAL)
# ------------------------------------------------------------------
with st.expander("📚 Ver base de cuentas completa cargada"):
    st.dataframe(df_cuentas, use_container_width=True, hide_index=True)

st.divider()
st.caption(
    "Buscador y Validador Presupuestario DAEM · Herramienta de apoyo interno · "
    "No constituye resolución oficial de clasificación presupuestaria."
)
