import streamlit as pd
import pandas as pd
import pypdf
import os

st.set_page_config(page_title="Buscador Presupuestario DAEM", layout="wide")

st.title("🛡️ Buscador y Validador Presupuestario - DAEM Puerto Montt")
st.caption("Desplegado en la nube con enfoque metodológico de Control de Gestión")

# Barra lateral para cargar archivos reales si se requiere
st.sidebar.header("📁 Carga de Documentos Oficiales")
uploaded_excel = st.sidebar.file_uploader("Subir cuentas_daem.xlsx", type=["xlsx"])
uploaded_pdf = st.sidebar.file_uploader("Subir Manual Superduc 2026 (.pdf)", type=["pdf"])

# Cargar base maestra de cuentas (o usar la autogenerada por defecto)
if uploaded_excel:
    df_maestro = pd.read_excel(uploaded_excel)
elif os.path.exists("cuentas_daem.xlsx"):
    df_maestro = pd.read_excel("cuentas_daem.xlsx")
else:
    # Set de respaldo por si el repositorio está vacío en su primera corrida
    df_maestro = pd.DataFrame([
        {"codigo_erp": "215-29-06-001", "denominacion_erp": "EQUIPOS COMPUTACIONALES Y PERIFERICOS", "cuenta_superduc": "410703", "categoria_superduc": "Equipos Informáticos y Licencias", "palabras_clave": "computador, notebook, laptop, pc, pantalla, mouse, teclado"},
        {"codigo_erp": "215-22-04-002", "denominacion_erp": "Textos y Otros Materiales de Ensenanza", "cuenta_superduc": "410605", "categoria_superduc": "Material y Recursos Didácticos", "palabras_clave": "cuaderno, block, croquera, goma eva, silicona, tempera"},
        {"codigo_erp": "215-22-04-001", "denominacion_erp": "Materiales de Oficina", "cuenta_superduc": "410902", "categoria_superduc": "Materiales de Oficina", "palabras_clave": "archivador, perforadora, corchetera, resma, lapiz"}
    ])

# Campo de búsqueda
busqueda = st.text_input("🔍 Escribe el artículo, insumo o cuenta contable que deseas consultar:", "").strip().lower()

if busqueda:
    # 1. EJECUCIÓN DEL MOTOR DE REGLAS Y ALERTAS (HARDCODED)
    st.subheader("🚦 Alertas de Control Interno (SEP / DAEM)")
    
    if any(p in busqueda for p in ["alargador", "zapatilla", "alargadores"]):
        st.error("❌ RECHAZADO BAJO SEP. Los alargadores o extensiones de ningún tipo son elegibles por no constituir un recurso de carácter pedagógico.")
    elif any(p in busqueda for p in ["puntero", "laser"]):
        st.error("❌ RECHAZADO BAJO SEP. Prohibida la adquisición de punteros láser con fondos de esta subvención.")
    elif any(p in busqueda for p in ["necesidades especiales", "necesidades docente"]):
        st.error("❌ RIESGO CRÍTICO DE REPARO. Evitar estrictamente incorporar estas frases en las justificaciones o glosas del PME/SEP, ya que son blanco prioritario de reparos en las fiscalizaciones de la Superintendencia.")
    elif any(p in busqueda for p in ["goma", "borrador", "archivador", "perforadora", "oficina", "block", "cuaderno"]):
        st.warning("⚠️ ADVERTENCIA DE DESTINO. Los útiles de escritorio de uso puramente administrativo NO pasan por SEP. Si son materiales para uso directo de los estudiantes en aula (ej. pliegos de goma eva, papel kraft, silicona, cuadernos o blocks de dibujo), deben clasificarse y autorizarse bajo 'Textos y Otros Materiales de Enseñanza' con Código 1.")
    elif any(p in busqueda for p in ["computador", "notebook", "tablet", "proyector", "pantalla", "tecnología"]):
        st.info("ℹ️ ANÁLISIS DE TECNOLOGÍA. For su aprobación con fondos SEP, este artículo requiere obligatoriamente una Especificación Técnica detallada y una Justificación Pedagógica explícita asociada a la acción PME.")

    # 2. BÚSQUEDA ASOCIATIVA EN LA BASE MAESTRA
    st.subheader("📊 Coincidencias Sugeridas en el Balance Contable")
    
    # Filtrado inteligente (Contenido en nombre, categoría o tags)
    match_mask = (
        df_maestro['denominacion_erp'].str.lower().str.contains(busqueda, na=False) |
        df_maestro['categoria_superduc'].str.lower().str.contains(busqueda, na=False) |
        df_maestro['palabras_clave'].str.lower().str.contains(busqueda, na=False)
    )
    df_resultados = df_maestro[match_mask]

    if not df_resultados.empty:
        st.dataframe(df_resultados[['codigo_erp', 'denominacion_erp', 'cuenta_superduc', 'categoria_superduc', 'palabras_clave']], use_container_width=True)
        
        # Mostrar sugerencia de Cuenta Corriente del primer resultado
        top_row = df_resultados.iloc[0]
        st.success(f"💡 **Sugerencia Operativa DAEM:** Para la cuenta `{top_row['codigo_erp']}`, el código Superduc oficial es el `{top_row['cuenta_superduc']}`. Si el gasto se financia por SEP, recuerda utilizar la Cuenta Corriente **021 BC**; si es por PIE, corresponde la **025 BC**.")
    else:
        st.error("No se encontraron coincidencias directas en las cuentas contables ni en las palabras clave del balance.")

    # 3. LECTURA DINÁMICA DEL MANUAL PDF
    if uploaded_pdf:
        st.subheader("📖 Evidencia Encontrada en el Manual de la Superintendencia")
        with st.spinner("Escaneando el Manual PDF en tiempo real..."):
            pdf_reader = pypdf.PdfReader(uploaded_pdf)
            matches_pdf = 0
            for i, page in enumerate(pdf_reader.pages):
                text_page = page.extract_text()
                if busqueda in text_page.lower():
                    matches_pdf += 1
                    # Extraer un pequeño fragmento para contextualizar
                    idx_start = max(0, text_page.lower().find(busqueda) - 100)
                    idx_end = min(len(text_page), idx_start + 300)
                    snippet = text_page[idx_start:idx_end].replace("\n", " ")
                    st.markdown(f"**Encontrado en Página {i+1} del Manual:**")
                    st.code(f"...{snippet}...")
                    if matches_pdf >= 4: # Límite de seguridad visual para no saturar la pantalla
                        st.caption("Mostrando las primeras 4 coincidencias del PDF. Revisa el manual físico para más detalles.")
                        break
            if matches_pdf == 0:
                st.caption("No se localizaron menciones explícitas de este término en las páginas descriptivas del Manual PDF.")
