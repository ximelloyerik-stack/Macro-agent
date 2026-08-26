import streamlit as st
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
import sqlite3
import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="AI Macro Coach",
    page_icon="🔥",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- BASE DE DATOS LOCAL MULTIUSUARIO ---
DB_NAME = "macros_history.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS perfiles (
            nombre TEXT PRIMARY KEY,
            peso REAL,
            altura REAL,
            edad INTEGER,
            actividad TEXT,
            tipo_meta TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS comidas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT,
            fecha TEXT,
            descripcion TEXT,
            calorias INTEGER,
            proteina REAL,
            carbs REAL,
            grasas REAL,
            consejo TEXT
        )
    """)
    c.execute("PRAGMA table_info(comidas)")
    columnas = [col[1] for col in c.fetchall()]
    if "usuario" not in columnas:
        c.execute("ALTER TABLE comidas ADD COLUMN usuario TEXT DEFAULT 'Yerik'")
    conn.commit()
    conn.close()

def obtener_perfiles():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT nombre FROM perfiles ORDER BY nombre ASC")
    filas = c.fetchall()
    conn.close()
    return [f[0] for f in filas]

def obtener_datos_perfil(nombre):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT peso, altura, edad, actividad, tipo_meta FROM perfiles WHERE nombre = ?", (nombre,))
    fila = c.fetchone()
    conn.close()
    if fila:
        return {"peso": fila[0], "altura": fila[1], "edad": fila[2], "actividad": fila[3], "tipo_meta": fila[4]}
    return {"peso": 85.6, "altura": 178.0, "edad": 18, "actividad": "Moderado (3-5 días gym + caminata)", "tipo_meta": "Déficit Moderado (-500 kcal)"}

def guardar_perfil(nombre, peso, altura, edad, actividad, tipo_meta):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        INSERT INTO perfiles (nombre, peso, altura, edad, actividad, tipo_meta)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(nombre) DO UPDATE SET
            peso=excluded.peso,
            altura=excluded.altura,
            edad=excluded.edad,
            actividad=excluded.actividad,
            tipo_meta=excluded.tipo_meta
    """, (nombre, peso, altura, edad, actividad, tipo_meta))
    conn.commit()
    conn.close()

def guardar_comida(usuario, desc, cal, prot, carb, gras, consejo):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    fecha_hoy = datetime.date.today().isoformat()
    c.execute("""
        INSERT INTO comidas (usuario, fecha, descripcion, calorias, proteina, carbs, grasas, consejo)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (usuario, fecha_hoy, desc, cal, prot, carb, gras, consejo))
    conn.commit()
    conn.close()

def eliminar_comida(comida_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM comidas WHERE id = ?", (comida_id,))
    conn.commit()
    conn.close()

def obtener_totales_hoy(usuario):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    fecha_hoy = datetime.date.today().isoformat()
    c.execute("SELECT SUM(calorias), SUM(proteina), SUM(carbs), SUM(grasas) FROM comidas WHERE usuario = ? AND fecha = ?", (usuario, fecha_hoy))
    row = c.fetchone()
    conn.close()
    return {"calorias": row[0] or 0, "proteina": row[1] or 0.0, "carbs": row[2] or 0.0, "grasas": row[3] or 0.0}

def obtener_comidas_hoy(usuario):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    fecha_hoy = datetime.date.today().isoformat()
    c.execute("SELECT id, descripcion, calorias, proteina, carbs, grasas, consejo FROM comidas WHERE usuario = ? AND fecha = ? ORDER BY id DESC", (usuario, fecha_hoy))
    rows = c.fetchall()
    conn.close()
    return rows

init_db()
# Crear perfil inicial por defecto si la base de datos está vacía
lista_perfiles = obtener_perfiles()
if not lista_perfiles:
    guardar_perfil("Yerik", 85.6, 178.0, 18, "Moderado (3-5 días gym + caminata)", "Déficit Moderado (-500 kcal)")
    lista_perfiles = obtener_perfiles()

# Control de sesión
if "usuario_actual" not in st.session_state or st.session_state["usuario_actual"] not in lista_perfiles:
    st.session_state["usuario_actual"] = lista_perfiles[0]

def cambiar_usuario():
    st.session_state["usuario_actual"] = st.session_state["sb_elegido"]

# --- SCHEMA PYDANTIC PARA GEMINI ---
class MacroBreakdown(BaseModel):
    descripcion: str = Field(description="Nombre o resumen del alimento")
    calorias: int = Field(description="Calorías totales estimadas")
    proteina_g: float = Field(description="Gramos de proteína")
    carbohidratos_g: float = Field(description="Gramos de carbohidratos")
    grasas_g: float = Field(description="Gramos de grasa")
    consejo_coach: str = Field(description="Consejo breve enfocado en recomposición y déficit")

# --- SELECTOR DE USUARIO DIRECTO EN PANTALLA ---
st.title("🔥 AI Nutrition Coach")

c_user, c_nuevo = st.columns([2, 1])

with c_user:
    idx_actual = lista_perfiles.index(st.session_state["usuario_actual"])
    st.selectbox(
        "👤 Perfil activo:",
        options=lista_perfiles,
        index=idx_actual,
        key="sb_elegido",
        on_change=cambiar_usuario
    )

with c_nuevo:
    with st.popover("➕ Nuevo Perfil"):
        nombre_nuevo = st.text_input("Nombre:").strip()
        if st.button("Crear", type="primary", use_container_width=True):
            if nombre_nuevo and nombre_nuevo not in lista_perfiles:
                guardar_perfil(nombre_nuevo, 70.0, 170.0, 20, "Moderado (3-5 días gym + caminata)", "Déficit Moderado (-500 kcal)")
                st.session_state["usuario_actual"] = nombre_nuevo
                st.rerun()
            elif nombre_nuevo in lista_perfiles:
                st.warning("Ya existe.")
            else:
                st.warning("Escribe un nombre.")

usuario_activo = st.session_state["usuario_actual"]
datos_perfil = obtener_datos_perfil(usuario_activo)

# --- EXPANDER CON KEYS DINÁMICAS POR USUARIO ---
with st.expander(f"⚙️ Configurar Medidas de **{usuario_activo}**", expanded=False):
    actividades_opts = [
        "Sedentario (poca actividad)", 
        "Ligero (1-3 días gym)", 
        "Moderado (3-5 días gym + caminata)", 
        "Muy activo (6-7 días o doble sesión)"
    ]
    metas_opts = [
        "Déficit Moderado (-500 kcal)", 
        "Déficit Agresivo (-750 kcal)", 
        "Mantenimiento"
    ]

    c1, c2, c3 = st.columns(3)
    p_val = float(datos_perfil["peso"]) if datos_perfil else 85.6
    a_val = float(datos_perfil["altura"]) if datos_perfil else 178.0
    e_val = int(datos_perfil["edad"]) if datos_perfil else 18
    
    with c1:
        peso_input = st.number_input("Peso (kg)", min_value=30.0, max_value=250.0, value=p_val, step=0.2, key=f"peso_{usuario_activo}")
    with c2:
        altura_input = st.number_input("Altura (cm)", min_value=100.0, max_value=240.0, value=a_val, step=1.0, key=f"alt_{usuario_activo}")
    with c3:
        edad_input = st.number_input("Edad", min_value=10, max_value=100, value=e_val, step=1, key=f"edad_{usuario_activo}")

    c4, c5 = st.columns(2)
    act_idx = actividades_opts.index(datos_perfil["actividad"]) if datos_perfil and datos_perfil["actividad"] in actividades_opts else 2
    meta_idx = metas_opts.index(datos_perfil["tipo_meta"]) if datos_perfil and datos_perfil["tipo_meta"] in metas_opts else 0
    
    with c4:
        actividad_input = st.selectbox("Nivel de Actividad", options=actividades_opts, index=act_idx, key=f"act_{usuario_activo}")
    with c5:
        meta_input = st.selectbox("Objetivo", options=metas_opts, index=meta_idx, key=f"meta_{usuario_activo}")

    if st.button("💾 Guardar mis medidas", use_container_width=True):
        guardar_perfil(usuario_activo, peso_input, altura_input, edad_input, actividad_input, meta_input)
        st.success("¡Datos actualizados!")
        st.rerun()

# --- CÁLCULO DE METAS METABÓLICAS (Mifflin-St Jeor) ---
tmb = (10 * peso_input) + (6.25 * altura_input) - (5 * edad_input) + 5
mult_act = {
    "Sedentario (poca actividad)": 1.2, 
    "Ligero (1-3 días gym)": 1.375, 
    "Moderado (3-5 días gym + caminata)": 1.55, 
    "Muy activo (6-7 días o doble sesión)": 1.725
}
mantenimiento = tmb * mult_act[actividad_input]

if meta_input == "Déficit Moderado (-500 kcal)":
    target_kcal = int(mantenimiento - 500)
elif meta_input == "Déficit Agresivo (-750 kcal)":
    target_kcal = int(mantenimiento - 750)
else:
    target_kcal = int(mantenimiento)

target_prot = round(peso_input * 2.0, 1)
target_fats = round(peso_input * 0.7, 1)
calorias_restantes = target_kcal - (target_prot * 4) - (target_fats * 9)
target_carbs = max(0, round(calorias_restantes / 4, 1))

totales = obtener_totales_hoy(usuario_activo)

# --- PANEL DE PROGRESO DE MACROS ---
st.divider()
st.subheader(f"🎯 Metas Diarias de {usuario_activo}")
m_col1, m_col2, m_col3, m_col4 = st.columns(4)
with m_col1:
    st.metric("🔥 Calorías", f"{totales['calorias']} / {target_kcal} kcal", delta=f"{totales['calorias'] - target_kcal} kcal", delta_color="inverse")
    st.progress(min(1.0, totales['calorias'] / target_kcal if target_kcal > 0 else 0.0))
with m_col2:
    st.metric("🥩 Proteína", f"{totales['proteina']:.1f} / {target_prot} g")
    st.progress(min(1.0, totales['proteina'] / target_prot if target_prot > 0 else 0.0))
with m_col3:
    st.metric("🍞 Carbos", f"{totales['carbs']:.1f} / {target_carbs} g")
with m_col4:
    st.metric("🥑 Grasas", f"{totales['grasas']:.1f} / {target_fats} g")

# Detección de API Key
api_key = st.secrets.get("GEMINI_API_KEY", os.environ.get("GEMINI_API_KEY", ""))

st.divider()

# --- REGISTRO Y HISTORIAL ---
col_input, col_view = st.columns([1.1, 1], gap="large")

with col_input:
    st.subheader(f"📸 Registrar Comida para {usuario_activo}")
    uploaded_file = st.file_uploader("Foto del plato:", type=["jpg", "jpeg", "png"])
    detalles = st.text_area("Detalles de la comida:", placeholder="Ej. 180g de pechuga a la plancha con media taza de arroz...")

    if st.button("🚀 Analizar y Guardar", type="primary", use_container_width=True):
        if not api_key:
            st.error("No se encontró la GEMINI_API_KEY en Secrets.")
        elif not uploaded_file and not detalles.strip():
            st.warning("Sube una foto o describe tu alimento.")
        else:
            client = genai.Client(api_key=api_key)
            prompt = f"""
            Eres un coach de nutrición deportiva de precisión.
            Datos del usuario ({usuario_activo}): {peso_input}kg, altura {altura_input}cm, objetivo: {meta_input}.
            Comida / detalles: {detalles}
            """
            contents = [prompt]
            if uploaded_file:
                contents.append(types.Part.from_bytes(
                    data=uploaded_file.getvalue(),
                    mime_type=uploaded_file.type
                ))
            
            with st.spinner(f"Analizando comida para {usuario_activo}..."):
                try:
                    response = client.models.generate_content(
                        model='gemini-2.0-flash',
                        contents=contents,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=MacroBreakdown,
                            temperature=0.2
                        )
                    )
                    data = MacroBreakdown.model_validate_json(response.text)
                    guardar_comida(usuario_activo, data.descripcion, data.calorias, data.proteina_g, data.carbohidratos_g, data.grasas_g, data.consejo_coach)
                    st.success(f"¡Comida guardada para {usuario_activo}!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al analizar: {e}")

with col_view:
    st.subheader(f"📋 Historial de Hoy ({usuario_activo})")
    historial = obtener_comidas_hoy(usuario_activo)
    if not historial:
        st.info(f"No hay registros de comidas para {usuario_activo} hoy.")
    else:
        for c_id, desc, cal, prot, carb, gras, consejo in historial:
            with st.expander(f"🍽️ **{desc}** — {cal} kcal", expanded=True):
                c_prot, c_carb, c_gras = st.columns(3)
                c_prot.markdown(f"🥩 **{prot}g** Prot")
                c_carb.markdown(f"🍞 **{carb}g** Carbs")
                c_gras.markdown(f"🥑 **{gras}g** Grasa")
                st.info(f"💡 {consejo}")
                if st.button("Eliminar", key=f"del_{c_id}"):
                    eliminar_comida(c_id)
                    st.rerun()