# -*- coding: utf-8 -*-
"""
DAEM Puerto Montt - Validador de Contrataciones y Control de Gestión
Herramienta de apoyo para revisión de balances contables (.xls/.xlsx),
cruce con el Manual de la Superintendencia (PDF) y motor de alertas
de control interno (SEP / DAEM).

Autor: Consultor de Control de Gestión (Python)
"""

import io
import difflib
import unicodedata

import pandas as pd
import streamlit as st

try:
    from pypdf import PdfReader
    PYPDF_OK = True
except Exception:
    PYPDF_OK = False


# =============================================================================
# CONFIGURACIÓN GENERAL DE LA PÁGINA
# =============================================================================
st.set_page_config(
    page_title="DAEM Puerto Montt | Validador de Contrataciones y Balance",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Estilo sobrio institucional -------------------------------------------------
st.markdown(
    """
    <style>
        .main {background-color: #FAFAFA;}
        .block-container {padding-top: 2rem;}
        h1, h2, h3 {color: #1B2A4A;}
        .stAlert {border-radius: 8px;}
        .daem-header {
            background-color: #1B2A4A;
            padding: 1.2rem 1.5rem;
            border-radius: 10px;
            color: white;
            margin-bottom: 1.5rem;
        }
        .daem-header h1 {color: white; margin-bottom: 0.2rem; font-size: 1.6rem;}
        .daem-header p {color: #D6DCE5; margin: 0; font-size: 0.95rem;}
        .footer-note {
            color: #8A8A8A;
            font-size: 0.8rem;
            text-align: center;
            margin-top: 3rem;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# =============================================================================
# UTILIDADES DE TEXTO
# =============================================================================
def normalizar_texto(texto: str) -> str:
    """Quita tildes, pasa a minúsculas y limpia espacios para comparar términos."""
    if not isinstance(texto, str):
        texto = str(texto)
    texto = texto.strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto


# =============================================================================
# CARGA Y NORMALIZACIÓN DEL BALANCE CONTABLE (.xls / .xlsx)
# =============================================================================

# Mapa de nombres de columnas "parecidos" -> nombre estándar interno
MAPA_COLUMNAS = {
    "codigo": ["codigo", "cod_cuenta", "cod cuenta", "cuenta", "codigo_cuenta", "cod"],
    "nombre_cuenta": ["nombre_cuenta", "nombre cuenta", "denominacion", "glosa_cuenta",
                       "nombre", "descripcion", "detalle_cuenta"],
    "superduc": ["superduc", "super duc", "sup_duc", "codigo_superintendencia",
                 "cod_superduc", "superintendencia"],
    "programa": ["programa", "programa_presupuestario", "prog", "fuente_financiamiento",
                 "fuente"],
}


def _generar_datos_prueba() -> pd.DataFrame:
    """Genera un set de datos de prueba con cuentas típicas del clasificador DAEM."""
    data = [
        ["215.22.04.001", "Materiales de Oficina", "215.22.04", "SEP"],
        ["215.22.08.001", "Equipos Menores", "215.22.08", "PIE"],
        ["215.22.04.007", "Materiales Didácticos y Textos de Enseñanza", "215.22.04", "SEP"],
        ["215.22.07.001", "Publicidad y Difusión", "215.22.07", "FAEP"],
        ["215.29.04.001", "Mobiliario y Otros", "215.29.04", "SEP"],
        ["215.22.11.001", "Servicios Técnicos y Profesionales", "215.22.11", "PIE"],
        ["215.22.06.001", "Mantenimiento y Reparaciones", "215.22.06", "Municipal"],
        ["215.29.06.001", "Equipos Informáticos", "215.29.06", "SEP"],
    ]
    df = pd.DataFrame(data, columns=["codigo", "nombre_cuenta", "superduc", "programa"])
    return df


def _detectar_y_renombrar_columnas(df: pd.DataFrame) -> pd.DataFrame:
    """Busca columnas similares (por nombre normalizado) y las renombra al estándar."""
    columnas_originales = list(df.columns)
    columnas_normalizadas = {col: normalizar_texto(col).replace(" ", "_") for col in columnas_originales}

    renombre_final = {}
    for estandar, variantes in MAPA_COLUMNAS.items():
        variantes_norm = [normalizar_texto(v).replace(" ", "_") for v in variantes]
        for col_original, col_norm in columnas_normalizadas.items():
            if col_norm in variantes_norm or any(v in col_norm for v in variantes_norm):
                renombre_final[col_original] = estandar
                break

    df = df.rename(columns=renombre_final)
    return df


def cargar_balance(archivo_subido) -> tuple[pd.DataFrame, str]:
    """
    Carga el archivo de balance (.xls o .xlsx). Si no hay archivo, o si falla
    la lectura, retorna un set de datos de prueba junto con un mensaje de estado.
    """
    if archivo_subido is None:
        return _generar_datos_prueba(), "demo"

    try:
        nombre = archivo_subido.name.lower()
        if nombre.endswith(".xls"):
            # Motor clásico para .xls (requiere xlrd)
            df = pd.read_excel(archivo_subido, engine="xlrd")
        else:
            # .xlsx / .xlsm -> openpyxl
            df = pd.read_excel(archivo_subido, engine="openpyxl")

        if df.empty:
            raise ValueError("El archivo se leyó correctamente pero no contiene filas de datos.")

        df = _detectar_y_renombrar_columnas(df)

        # Asegurar que existan al menos las columnas clave; si faltan, se crean vacías
        for col_estandar in ["codigo", "nombre_cuenta", "superduc", "programa"]:
            if col_estandar not in df.columns:
                df[col_estandar] = ""

        # Limpieza básica de tipos
        for col in ["codigo", "nombre_cuenta", "superduc", "programa"]:
            df[col] = df[col].astype(str).str.strip()

        return df, "ok"

    except ImportError as e:
        st.error(
            "⚠️ No fue posible leer el archivo .xls porque falta la librería 'xlrd'. "
            "Revisa que esté incluida en requirements.txt. Se usarán datos de prueba mientras tanto."
        )
        return _generar_datos_prueba(), "error"
    except Exception as e:
        st.error(
            f"⚠️ No fue posible leer el archivo de Balance subido. Detalle técnico: {e}. "
            "Se están mostrando datos de prueba (demo) para que puedas seguir trabajando."
        )
        return _generar_datos_prueba(), "error"


# =============================================================================
# LECTURA Y BÚSQUEDA EN EL MANUAL DE LA SUPERINTENDENCIA (PDF)
# =============================================================================
@st.cache_data(show_spinner=False)
def extraer_texto_pdf(archivo_bytes: bytes) -> list[dict]:
    """
    Extrae el texto del PDF página por página.
    Retorna una lista de diccionarios: [{"pagina": int, "texto": str}, ...]
    """
    reader = PdfReader(io.BytesIO(archivo_bytes))
    paginas = []
    for i, page in enumerate(reader.pages, start=1):
        try:
            texto = page.extract_text() or ""
        except Exception:
            texto = ""
        paginas.append({"pagina": i, "texto": texto})
    return paginas


def buscar_termino_en_pdf(paginas: list[dict], termino: str, contexto: int = 120) -> list[dict]:
    """Busca el término (sin distinguir mayúsculas/tildes) en el texto de cada página del PDF."""
    termino_norm = normalizar_texto(termino)
    if not termino_norm:
        return []

    resultados = []
    for pagina in paginas:
        texto_original = pagina["texto"]
        texto_norm = normalizar_texto(texto_original)
        idx = texto_norm.find(termino_norm)
        if idx != -1:
            inicio = max(0, idx - contexto)
            fin = min(len(texto_original), idx + len(termino_norm) + contexto)
            fragmento = texto_original[inicio:fin].replace("\n", " ").strip()
            resultados.append({
                "pagina": pagina["pagina"],
                "fragmento": f"...{fragmento}..." if fragmento else "(texto no legible en esta página)",
            })
    return resultados


# =============================================================================
# MOTOR DE REGLAS DE CONTROL INTERNO (SEP / DAEM) - HARDCODED
# =============================================================================
REGLAS_CONTROL = [
    {
        "tipo": "roja",
        "palabras": ["alargador", "zapatilla"],
        "mensaje": "❌ RECHAZADO BAJO SEP. Los alargadores no son elegibles bajo ningún motivo por no ser de carácter pedagógico.",
    },
    {
        "tipo": "roja",
        "palabras": ["puntero", "laser"],
        "mensaje": "❌ RECHAZADO BAJO SEP. Prohibida la adquisición de punteros láser.",
    },
    {
        "tipo": "roja",
        "palabras": ["necesidades especiales", "necesidades docente"],
        "mensaje": "⚠️ RIESGO DE REPARO. No incorpores estas frases en las glosas o justificaciones de compras o contratos.",
    },
    {
        "tipo": "amarilla",
        "palabras": ["goma", "borrador", "archivador", "perforadora", "oficina"],
        "mensaje": "⚠️ ADVERTENCIA. Los útiles de escritorio administrativos no pasan por SEP. Si son didácticos para el aula (goma eva, papel kraft, cuadernos), imputar en 'Textos y Otros Materiales de Enseñanza'.",
    },
    {
        "tipo": "azul",
        "palabras": ["computador", "notebook", "tablet", "proyector", "tecnologia"],
        "mensaje": "ℹ️ REQUIERE ACCIÓN. Exige especificación técnica detallada y justificación pedagógica en la Acción PME.",
    },
]


def evaluar_reglas_control(termino: str) -> list[dict]:
    """Evalúa el término buscado contra el motor de reglas hardcoded."""
    termino_norm = normalizar_texto(termino)
    alertas_activadas = []
    for regla in REGLAS_CONTROL:
        for palabra_clave in regla["palabras"]:
            if normalizar_texto(palabra_clave) in termino_norm:
                alertas_activadas.append(regla)
                break
    return alertas_activadas


def mostrar_alerta(regla: dict):
    if regla["tipo"] == "roja":
        st.error(regla["mensaje"])
    elif regla["tipo"] == "amarilla":
        st.warning(regla["mensaje"])
    elif regla["tipo"] == "azul":
        st.info(regla["mensaje"])


# =============================================================================
# BÚSQUEDA DIFUSA EN EL BALANCE
# =============================================================================
def busqueda_difusa_balance(df: pd.DataFrame, termino: str, umbral: float = 0.55, top_n: int = 25) -> pd.DataFrame:
    """
    Busca coincidencias difusas del término dentro de codigo + nombre_cuenta,
    usando difflib. También incluye coincidencias directas de substring.
    """
    if df.empty or not termino.strip():
        return df.iloc[0:0]

    termino_norm = normalizar_texto(termino)

    filas_resultado = []
    for _, fila in df.iterrows():
        texto_comparar = normalizar_texto(f"{fila.get('codigo', '')} {fila.get('nombre_cuenta', '')}")

        # 1) Coincidencia directa (substring) -> score máximo
        if termino_norm in texto_comparar:
            score = 1.0
        else:
            # 2) Coincidencia difusa palabra por palabra
            palabras_texto = texto_comparar.split()
            mejores_scores = [
                difflib.SequenceMatcher(None, termino_norm, palabra).ratio()
                for palabra in palabras_texto
            ] or [0.0]
            score = max(mejores_scores)

        if score >= umbral:
            filas_resultado.append((score, fila))

    if not filas_resultado:
        return df.iloc[0:0]

    filas_resultado.sort(key=lambda x: x[0], reverse=True)
    filas_resultado = filas_resultado[:top_n]

    df_resultado = pd.DataFrame([f[1] for f in filas_resultado])
    df_resultado.insert(0, "coincidencia_%", [round(f[0] * 100, 1) for f in filas_resultado])
    return df_resultado.reset_index(drop=True)


# =============================================================================
# ENCABEZADO
# =============================================================================
st.markdown(
    """
    <div class="daem-header">
        <h1>🏛️ Validador de Contrataciones y Balance Contable — DAEM Puerto Montt</h1>
        <p>Cruce entre Balance Contable (.xls/.xlsx), Manual de la Superintendencia (PDF)
        y motor de control interno SEP / DAEM.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if not PYPDF_OK:
    st.error(
        "⚠️ La librería 'pypdf' no está disponible en este entorno. "
        "Revisa que 'pypdf' esté incluido en requirements.txt para poder leer el Manual PDF."
    )


# =============================================================================
# SIDEBAR - CARGA DE ARCHIVOS
# =============================================================================
with st.sidebar:
    st.header("📂 Carga de Archivos")

    st.subheader("1. Balance Contable")
    archivo_balance = st.file_uploader(
        "Sube el Balance (.xls o .xlsx)",
        type=["xls", "xlsx"],
        help="Si no subes un archivo, la app usará un set de datos de prueba con cuentas típicas del clasificador presupuestario.",
    )

    st.subheader("2. Manual de la Superintendencia")
    archivo_pdf = st.file_uploader(
        "Sube el Manual (.pdf)",
        type=["pdf"],
        help="El texto se extraerá internamente para buscar coincidencias con el término consultado.",
    )

    st.markdown("---")
    st.subheader("⚙️ Parámetros de búsqueda")
    umbral_similitud = st.slider(
        "Sensibilidad de búsqueda difusa en el Balance",
        min_value=0.3, max_value=0.9, value=0.55, step=0.05,
        help="Valores más bajos muestran más resultados (menos exigentes); valores más altos son más estrictos.",
    )

    st.markdown("---")
    st.caption("DAEM Puerto Montt · Control de Gestión · Uso interno")


# =============================================================================
# CARGA DE DATOS
# =============================================================================
df_balance, estado_balance = cargar_balance(archivo_balance)

if estado_balance == "demo":
    st.info(
        "ℹ️ No se ha subido un archivo de Balance. Se está usando un **set de datos de prueba** "
        "con cuentas típicas (ej: 215.22.04.001 - Materiales de Oficina, 215.22.08.001 - Equipos Menores). "
        "Sube tu archivo real en el panel lateral para trabajar con tus datos."
    )
elif estado_balance == "ok":
    st.success(f"✅ Balance cargado correctamente. {len(df_balance)} cuentas detectadas.")

paginas_pdf = None
if archivo_pdf is not None and PYPDF_OK:
    try:
        paginas_pdf = extraer_texto_pdf(archivo_pdf.getvalue())
        st.success(f"✅ Manual PDF cargado correctamente. {len(paginas_pdf)} páginas procesadas.")
    except Exception as e:
        st.error(
            f"⚠️ No fue posible leer el PDF del Manual de la Superintendencia. Detalle técnico: {e}. "
            "Verifica que el archivo no esté dañado, protegido con contraseña, o corresponda a un PDF escaneado sin texto."
        )
        paginas_pdf = None
elif archivo_pdf is None:
    st.info("ℹ️ No se ha subido el Manual de la Superintendencia (PDF). La búsqueda en el manual quedará deshabilitada hasta que subas el archivo.")


# =============================================================================
# BÚSQUEDA PRINCIPAL
# =============================================================================
st.markdown("---")
st.header("🔍 Búsqueda y Validación")

termino_busqueda = st.text_input(
    "Ingresa el término, ítem o palabra clave a validar (ej: computador, alargador, goma, notebook)",
    placeholder="Escribe aquí el ítem que deseas validar...",
)

if termino_busqueda.strip():

    # -------------------------------------------------------------------
    # 1. Motor de reglas de control interno (SEP / DAEM)
    # -------------------------------------------------------------------
    st.subheader("🚦 Alertas de Control Interno (SEP / DAEM)")
    alertas = evaluar_reglas_control(termino_busqueda)
    if alertas:
        for regla in alertas:
            mostrar_alerta(regla)
    else:
        st.success("✅ No se activaron alertas críticas hardcoded para este término. Igualmente, valida contra el Manual de la Superintendencia más abajo.")

    # -------------------------------------------------------------------
    # 2. Resultados en el Balance (búsqueda difusa)
    # -------------------------------------------------------------------
    st.subheader("📊 Coincidencias en el Balance Contable")
    resultados_balance = busqueda_difusa_balance(df_balance, termino_busqueda, umbral=umbral_similitud)

    if resultados_balance.empty:
        st.warning("No se encontraron coincidencias en el Balance cargado para este término. Prueba bajar la sensibilidad en el panel lateral.")
    else:
        st.dataframe(
            resultados_balance,
            width='stretch',
            hide_index=True,
        )

    # -------------------------------------------------------------------
    # 3. Resultados en el Manual PDF de la Superintendencia
    # -------------------------------------------------------------------
    st.subheader("📖 Coincidencias en el Manual de la Superintendencia")
    if paginas_pdf is None:
        st.warning("Sube el Manual en formato PDF en el panel lateral para poder contrastar la regla oficial de la Superintendencia.")
    else:
        resultados_pdf = buscar_termino_en_pdf(paginas_pdf, termino_busqueda)
        if not resultados_pdf:
            st.warning(f"No se encontraron coincidencias de '{termino_busqueda}' en el texto del Manual PDF cargado.")
        else:
            for r in resultados_pdf:
                st.markdown(f"**Encontrado en Página {r['pagina']} del Manual:**")
                st.markdown(f"> {r['fragmento']}")
                st.markdown("")

else:
    st.info("👆 Ingresa un término en el cuadro de búsqueda para comenzar la validación.")


# =============================================================================
# VISTA COMPLETA DEL BALANCE (opcional, expandible)
# =============================================================================
with st.expander("📋 Ver Balance Contable completo cargado"):
    st.dataframe(df_balance, width='stretch', hide_index=True)


# =============================================================================
# PIE DE PÁGINA
# =============================================================================
st.markdown(
    """
    <p class="footer-note">
        Herramienta de apoyo interno para revisión de contrataciones y balance — DAEM Puerto Montt.
        No reemplaza el criterio profesional ni la revisión formal de Control de Gestión.
    </p>
    """,
    unsafe_allow_html=True,
)
