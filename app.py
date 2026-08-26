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
    initial_sidebar_state="expanded"
)

# Estilos CSS personalizados para una UI limpia y moderna
st.markdown("""
<style>
    .metric-card {
        background-color: #1E222B;
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        text-align: center;
        border: 1px solid #2E3440;
    }
    .stButton>button {
        border-radius: 8px;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)

# --- BASE DE DATOS LOCAL ---
DB_NAME = "macros_history.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS comidas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            descripcion TEXT,
            calorias INTEGER,
            proteina REAL,
            carbs REAL,
            grasas REAL,
            consejo TEXT
        )
    """)
    conn.commit()
    conn.close()

def guardar_comida(desc, cal, prot, carb, gras, consejo):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    fecha_hoy = datetime.date.today().isoformat()
    c.execute("""
        INSERT INTO comidas (fecha, descripcion, calorias, proteina, carbs, grasas, consejo)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (fecha_hoy, desc, cal, prot, carb, gras, consejo))
    conn.commit()
    conn.close()

def eliminar_comida(comida_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("DELETE FROM comidas WHERE id = ?", (comida_id,))
    conn.commit()
    conn.close()

def obtener_totales_hoy():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    fecha_hoy = datetime.date.today().isoformat()
    c.execute("""
        SELECT SUM(calorias), SUM(proteina), SUM(carbs), SUM(grasas)
        FROM comidas WHERE fecha = ?
    """, (fecha_hoy,))
    row = c.fetchone()
    conn.close()
    return {
        "calorias": row[0] or 0,
        "proteina": row[1] or 0.0,
        "carbs": row[2] or 0.0,
        "grasas": row[3] or 0.0
    }

def obtener_comidas_hoy():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    fecha_hoy = datetime.date.today().isoformat()
    c.execute("""
        SELECT id, descripcion, calorias, proteina, carbs, grasas, consejo 
        FROM comidas WHERE fecha = ? ORDER BY id DESC
    """, (fecha_hoy,))
    rows = c.fetchall()
    conn.close()
    return rows

init_db()

# --- SCHEMA PYDANTIC ---
class MacroBreakdown(BaseModel):
    descripcion: str = Field(description="Nombre o resumen de los alimentos")
    calorias: int = Field(description="Calorías totales estimadas")
    proteina_g: float = Field(description="Gramos de proteína")
    carbohidratos_g: float = Field(description="Gramos de carbohidratos")
    grasas_g: float = Field(description="Gramos de grasa")
    consejo_coach: str = Field(description="Consejo breve enfocado en recomposición y déficit")

# --- BARRA LATERAL: PERFIL BIOMÉTRICO Y METAS DINÁMICAS ---
with st.sidebar:
    st.title("⚙️ Tu Perfil")
    
    with st.expander("👤 Parámetros Corporales", expanded=False):
        peso = st.number_input("Peso (kg)", min_value=40.0, max_value=200.0, value=85.6, step=0.2)
        altura = st.number_input("Altura (cm)", min_value=120, max_value=230, value=178, step=1)
        edad = st.number_input("Edad (años)", min_value=14, max_value=90, value=18, step=1)
        actividad = st.selectbox(
            "Nivel de Actividad",
            options=["Sedentario (poca actividad)", "Ligero (1-3 días gym)", "Moderado (3-5 días gym + caminata)", "Muy activo (6-7 días o doble sesión)"],
            index=2
        )
        tipo_meta = st.selectbox("Objetivo", ["Déficit Moderado (-500 kcal)", "Déficit Agresivo (-750 kcal)", "Mantenimiento"], index=0)

    # Cálculo TDEE Mifflin-St Jeor
    tmb = (10 * peso) + (6.25 * altura) - (5 * edad) + 5
    mult_act = {"Sedentario (poca actividad)": 1.2, "Ligero (1-3 días gym)": 1.375, "Moderado (3-5 días gym + caminata)": 1.55, "Muy activo (6-7 días o doble sesión)": 1.725}
    mantenimiento = tmb * mult_act[actividad]

    if tipo_meta == "Déficit Moderado (-500 kcal)":
        target_kcal = int(mantenimiento - 500)
    elif tipo_meta == "Déficit Agresivo (-750 kcal)":
        target_kcal = int(mantenimiento - 750)
    else:
        target_kcal = int(mantenimiento)

    target_prot = round(peso * 2.0, 1)        # 2.0g/kg de peso
    target_fats = round(peso * 0.7, 1)        # 0.7g/kg de peso
    calorias_restantes = target_kcal - (target_prot * 4) - (target_fats * 9)
    target_carbs = max(0, round(calorias_restantes / 4, 1))

    st.divider()
    st.subheader("🎯 Metas del Día")
    totales = obtener_totales_hoy()

    st.metric("🔥 Calorías", f"{totales['calorias']} / {target_kcal} kcal", delta=f"{totales['calorias'] - target_kcal} kcal", delta_color="inverse")
    st.progress(min(1.0, totales['calorias'] / target_kcal if target_kcal > 0 else 0.0))
    
    st.metric("🥩 Proteína", f"{totales['proteina']:.1f} / {target_prot} g")
    st.progress(min(1.0, totales['proteina'] / target_prot if target_prot > 0 else 0.0))

    st.metric("🍞 Carbs", f"{totales['carbs']:.1f} / {target_carbs} g")
    st.metric("🥑 Grasas", f"{totales['grasas']:.1f} / {target_fats} g")

    st.divider()
    api_key = os.environ.get("GEMINI_API_KEY") or st.text_input("Gemini API Key", type="password")

# --- CONTENIDO PRINCIPAL ---
st.title("🏋️‍♂️ AI Nutrition Coach")
st.caption("Registra tus comidas con foto o texto y mantén el déficit exacto.")

col_input, col_view = st.columns([1.1, 1], gap="large")

with col_input:
    st.subheader("📸 Registrar Alimento")
    uploaded_file = st.file_uploader("Sube una foto clara de tu plato", type=["jpg", "jpeg", "png"])
    detalles = st.text_area("Detalles de la comida:", placeholder="Ej. 180g de pechuga a la plancha, 1/2 taza de arroz y agua de limón sin azúcar...")

    if st.button("🚀 Analizar y Guardar", type="primary", use_container_width=True):
        if not api_key:
            st.error("Agrega tu Gemini API Key en la barra lateral o en el archivo .env.")
        elif not uploaded_file and not detalles.strip():
            st.warning("Sube una imagen o detalla tu comida.")
        else:
            client = genai.Client(api_key=api_key)
            prompt = f"""
            Eres un coach de nutrición deportiva. Estima las calorías y macros con precisión.
            Datos del usuario: {peso}kg, objetivo déficit calórico.
            Detalles adicionales del usuario: {detalles}
            """
            contents = [prompt]
            if uploaded_file:
                contents.append(types.Part.from_bytes(
                    data=uploaded_file.getvalue(),
                    mime_type=uploaded_file.type
                ))
            
            with st.spinner("Analizando plato con IA..."):
                try:
                    response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=contents,
                        config=types.GenerateContentConfig(
                            response_mime_type="application/json",
                            response_schema=MacroBreakdown,
                            temperature=0.2
                        )
                    )
                    data = MacroBreakdown.model_validate_json(response.text)
                    guardar_comida(data.descripcion, data.calorias, data.proteina_g, data.carbohidratos_g, data.grasas_g, data.consejo_coach)
                    st.success("¡Comida guardada!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error al analizar: {e}")

with col_view:
    st.subheader("📋 Historial de Hoy")
    historial = obtener_comidas_hoy()
    if not historial:
        st.info("Aún no has registrado alimentos hoy.")
    else:
        for c_id, desc, cal, prot, carb, gras, consejo in historial:
            with st.expander(f"🍽️ **{desc}** — {cal} kcal", expanded=True):
                m1, m2, m3 = st.columns(3)
                m1.markdown(f"🥩 **{prot}g** Prot")
                m2.markdown(f"🍞 **{carb}g** Carbs")
                m3.markdown(f"🥑 **{gras}g** Grasa")
                st.info(f"💡 {consejo}")
                if st.button("Eliminar comida", key=f"del_{c_id}"):
                    eliminar_comida(c_id)
                    st.rerun()