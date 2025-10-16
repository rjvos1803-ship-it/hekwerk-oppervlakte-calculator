# Hekwerk-oppervlakte-calculator — Streamlit (v2, multipage + deployable)
# ---------------------------------------------------------------------
# Nieuwe features in v2:
# ✅ Meerdere PDF-pagina’s met pagina-selector (schaal per pagina)
# ✅ Per-lijn **diameter** aanpasbaar via een **editable tabel** (st.data_editor)
# ✅ Project-export (JSON) + CSV-export resultaten
# ✅ Klaar te draaien in **Docker** of als **Windows .exe** (PyInstaller)
#
# Benodigdheden (pip):
#   pip install streamlit streamlit-drawable-canvas pdf2image pillow pandas numpy
# Optioneel (voor JSON validatie):
#   pip install pydantic
#
# Voor PDF-rendering is Poppler vereist.
# Start lokaal:  streamlit run app.py
# Docker build:  docker build -t hekwerk-app .  |  docker run -p 8501:8501 hekwerk-app
# PyInstaller:   pyinstaller --onefile --add-data "assets;assets" app.py

import io
import json
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from PIL import Image
import streamlit as st
from streamlit_drawable_canvas import st_canvas

try:
    from pdf2image import convert_from_bytes
    PDF2IMAGE_OK = True
except Exception:
    PDF2IMAGE_OK = False

# -----------------------------
# Config
# -----------------------------
st.set_page_config(page_title="Hekwerk-oppervlakte-calculator", layout="wide")
st.title("🔧 Hekwerk-oppervlakte-calculator — v2")

st.markdown(
    """
    **Workflow**
    1. **Upload** de tekening (PDF of afbeelding). Bij PDF kun je de **pagina** kiezen.
    2. **Schaal** zetten per pagina: teken een **rechte schaal-lijn** over een bekende maat en vul de lengte (mm) in.
    3. **Annoteren**: *rechthoeken* = **panelen/plaat**, *lijnen* = **palen/buizen**.
    4. **Resultaten** verschijnen live. Je kunt **diameters per lijn** aanpassen in de tabel.
    5. **Exporteer** CSV of **project-JSON** (voor hergebruik / audit).
    """
)

# -----------------------------
# Helpers & State
# -----------------------------
@dataclass
class Scale:
    px_per_mm: Optional[float] = None


def ensure_state():
    if "pages" not in st.session_state:
        st.session_state.pages = []              # list[PIL.Image]
    if "page_scales" not in st.session_state:
        st.session_state.page_scales: Dict[int, float] = {}
    if "diameter_overrides" not in st.session_state:
        st.session_state.diameter_overrides: Dict[str, float] = {}
    if "results_df" not in st.session_state:
        st.session_state.results_df = pd.DataFrame()


def load_pages(file_bytes: bytes, filename: str) -> List[Image.Image]:
    suffix = filename.lower().split(".")[-1]
    if suffix in {"png", "jpg", "jpeg", "bmp", "tiff"}:
        img = Image.open(io.BytesIO(file_bytes)).convert("RGB")
        return [img]
    elif suffix == "pdf":
        if not PDF2IMAGE_OK:
            st.error("pdf2image niet beschikbaar. Installeer 'pdf2image' en 'poppler'.")
            st.stop()
        pages = convert_from_bytes(file_bytes, dpi=200)
        if not pages:
            st.error("Kon de PDF niet renderen.")
            st.stop()
        return [p.convert("RGB") for p in pages]
    else:
        st.error("Bestandstype niet ondersteund.")
        st.stop()


def canvas_objects(canvas_json):
    if not canvas_json or not canvas_json.get("objects"):
        return []
    return canvas_json["objects"]


ensure_state()

# -----------------------------
# Sidebar
# -----------------------------
with st.sidebar:
    st.header("Instellingen")
    coat_both_sides = st.checkbox("Panels dubbelzijdig coaten?", value=True)
    default_post_diameter_mm = st.number_input("Standaard paaldiameter (mm)", min_value=1.0, step=1.0, value=60.0)

    st.markdown("**Export**")
    export_csv = st.button("📥 Exporteer resultaten (CSV)")
    export_json = st.button("🧩 Exporteer project (JSON)")

    st.markdown("**Import project**")
    project_file = st.file_uploader("Laad project JSON", type=["json"], key="project_json")

# -----------------------------
# Upload bestand
# -----------------------------
upload = st.file_uploader("Upload PDF of afbeelding van de tekening", type=["pdf", "png", "jpg", "jpeg", "bmp", "tiff"], key="drawing")
if not upload and not st.session_state.pages:
    st.info("Upload een tekening om te beginnen.")
    st.stop()

if upload:
    st.session_state.pages = load_pages(upload.read(), upload.name)

pages = st.session_state.pages
num_pages = len(pages)
page_idx = 0
if num_pages > 1:
    page_idx = st.number_input("Pagina", min_value=1, max_value=num_pages, value=1, step=1) - 1
base_img = pages[page_idx]
W, H = base_img.size

col_scale, col_draw = st.columns([1, 2])

# -----------------------------
# 1) SCHAAL ZETTEN (per pagina)
# -----------------------------
with col_scale:
    st.subheader("1) Schaal zetten")
    st.caption("Teken een **rechte lijn** over een bekende maat op **deze pagina** en vul de **werkelijke lengte (mm)** in.")

    scale_len_mm = st.number_input("Werkelijke lengte van de schaal-lijn (mm)", min_value=0.0, step=1.0, value=1000.0, key=f"scale_len_mm_{page_idx}")

    scale_canvas = st_canvas(
        fill_color="rgba(255, 165, 0, 0.2)",
        stroke_width=3,
        stroke_color="#ff0000",
        background_image=base_img,
        background_color="#eee",
        update_streamlit=True,
        height=min(600, int(H * 0.75)),
        width=min(600, int(W * 0.75)),
        drawing_mode="line",
        key=f"scale_canvas_{page_idx}",
    )

    px_per_mm = None
    objs = canvas_objects(scale_canvas.json_data)
    max_len = 0.0
    for o in objs:
        if o.get("type") == "line":
            x1, y1, x2, y2 = o.get("x1", 0), o.get("y1", 0), o.get("x2", 0), o.get("y2", 0)
            L = math.hypot(x2 - x1, y2 - y1)
            if L > max_len:
                max_len = L
    if max_len > 0 and scale_len_mm > 0:
        px_per_mm = max_len / scale_len_mm
        st.session_state.page_scales[page_idx] = px_per_mm
        st.success(f"Schaal (pagina {page_idx+1}): **{px_per_mm:.4f} px/mm**")
    else:
        px_per_mm = st.session_state.page_scales.get(page_idx)
        if px_per_mm:
            st.info(f"Schaal al gezet voor pagina {page_idx+1}: **{px_per_mm:.4f} px/mm**")
        else:
            st.warning("Teken een lijn en vul de werkelijke lengte in mm.")

# -----------------------------
# 2) OBJECTEN TEKENEN
# -----------------------------
with col_draw:
    st.subheader("2) Objecten tekenen en automatisch berekenen")

    tabs = st.tabs(["Panelen (rechthoeken)", "Palen/Buizen (lijnen)"])

    with tabs[0]:
        st.caption("Teken **rechthoeken** over panelen/plaatdelen op **deze pagina**.")
        panel_canvas = st_canvas(
            fill_color="rgba(0, 200, 0, 0.2)",
            stroke_width=2,
            stroke_color="#00aa00",
            background_image=base_img,
            background_color="#eee",
            update_streamlit=True,
            height=min(800, H),
            width=min(1000, W),
            drawing_mode="rect",
            key=f"panel_canvas_{page_idx}",
        )
        panel_objs = canvas_objects(panel_canvas.json_data)

    with tabs[1]:
        st.caption("Teken **lijnen** voor palen/buizen. Pas daarna de **diameter per lijn** aan in de tabel.")
        post_canvas = st_canvas(
            fill_color="rgba(0,0,0,0)",
            stroke_width=3,
            stroke_color="#0066ff",
            background_image=base_img,
            background_color="#eee",
            update_streamlit=True,
            height=min(800, H),
            width=min(1000, W),
            drawing_mode="line",
            key=f"post_canvas_{page_idx}",
        )
        post_objs = canvas_objects(post_canvas.json_data)

# -----------------------------
# 3) BEREKENEN + EDITABLE DIAMETERS
# -----------------------------
rows: List[dict] = []
page_label = f"p{page_idx+1}"

if px_per_mm:
    # Panels
    if panel_objs:
        for i, o in enumerate(panel_objs, start=1):
            if o.get("type") == "rect":
                w_px = abs(o.get("width", 0)) * o.get("scaleX", 1.0)
                h_px = abs(o.get("height", 0)) * o.get("scaleY", 1.0)
                w_mm = w_px / px_per_mm
                h_mm = h_px / px_per_mm
                area_m2 = (w_mm * h_mm) / 1_000_000.0
                if coat_both_sides:
                    area_m2 *= 2.0
                rows.append({
                    "Pagina": page_label,
                    "Type": "Paneel",
                    "ID": f"{page_label}-panel-{i}",
                    "Breedte (mm)": round(w_mm, 1),
                    "Hoogte (mm)": round(h_mm, 1),
                    "Dubbelzijdig": coat_both_sides,
                    "Diameter (mm)": None,
                    "Lengte (m)": None,
                    "Oppervlakte (m²)": round(area_m2, 4),
                })
    # Posts
    if post_objs:
        for i, o in enumerate(post_objs, start=1):
            if o.get("type") == "line":
                x1, y1, x2, y2 = o.get("x1", 0), o.get("y1", 0), o.get("x2", 0), o.get("y2", 0)
                L_px = math.hypot(x2 - x1, y2 - y1)
                L_mm = L_px / px_per_mm
                L_m = L_mm / 1000.0
                obj_id = f"{page_label}-post-{i}"
                dia_override = st.session_state.diameter_overrides.get(obj_id, default_post_diameter_mm)
                circumference_mm = math.pi * dia_override
                mantle_m2 = (circumference_mm * L_mm) / 1_000_000.0
                rows.append({
                    "Pagina": page_label,
                    "Type": "Paal/Buis",
                    "ID": obj_id,
                    "Breedte (mm)": None,
                    "Hoogte (mm)": None,
                    "Dubbelzijdig": None,
                    "Diameter (mm)": round(dia_override, 1),
                    "Lengte (m)": round(L_m, 3),
                    "Oppervlakte (m²)": round(mantle_m2, 4),
                })

# Combineer met vorige pagina resultaten (niet persistent tussen rerenders behalve in session)
if rows:
    df = pd.DataFrame(rows)
else:
    df = pd.DataFrame(columns=["Pagina","Type","ID","Breedte (mm)","Hoogte (mm)","Dubbelzijdig","Diameter (mm)","Lengte (m)","Oppervlakte (m²)"])

st.subheader("3) Resultaten (diameter per lijn aanpasbaar)")
if df.empty:
    st.warning("Nog geen objecten of schaal niet gezet voor deze pagina.")

# Maak diameter kolom editable voor Paal/Buis
if not df.empty:
    edited = st.data_editor(
        df,
        use_container_width=True,
        column_config={
            "Diameter (mm)": st.column_config.NumberColumn("Diameter (mm)", min_value=1.0, step=1.0),
        },
        disabled=[c for c in df.columns if c != "Diameter (mm)"],
        key=f"editor_{page_idx}",
    )

    # Recompute surfaces using edited diameters
    def recompute_surfaces(df_edit: pd.DataFrame):
        panel_area = 0.0
        post_area = 0.0
        post_len_total = 0.0
        out_rows = []
        for _, r in df_edit.iterrows():
            if r["Type"] == "Paneel":
                panel_area += float(r["Oppervlakte (m²)"] or 0)
                out_rows.append(r)
            else:
                L_m = float(r["Lengte (m)"] or 0)
                dia = float(r["Diameter (mm)"] or default_post_diameter_mm)
                # Herbereken op basis van L_m en dia (we kennen px_per_mm niet meer hier, dus gebruiken direct L_m)
                mantle_m2 = (math.pi * dia * (L_m * 1000.0)) / 1_000_000.0
                r["Oppervlakte (m²)"] = round(mantle_m2, 4)
                post_area += mantle_m2
                post_len_total += L_m
                out_rows.append(r)
                # Bewaar override
                st.session_state.diameter_overrides[str(r["ID"])] = dia
        total = panel_area + post_area
        return pd.DataFrame(out_rows), panel_area, post_area, total, post_len_total

    edited, panel_area, post_area, total_area, post_len_total = recompute_surfaces(edited)
    st.session_state.results_df = edited

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        st.metric("Totaal paneel-oppervlak", f"{panel_area:.3f} m²")
    with col_b:
        st.metric("Totaal paal/buis-oppervlak", f"{post_area:.3f} m²")
    with col_c:
        st.metric("Totaal (m²)", f"{total_area:.3f} m²")
    if post_len_total > 0:
        st.caption(f"Totale paal-/buislengte: **{post_len_total:.2f} m**")

# -----------------------------
# Export / Import
# -----------------------------
if export_csv and not st.session_state.results_df.empty:
    csv = st.session_state.results_df.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", csv, file_name="hekwerk_oppervlakte_resultaten.csv", mime="text/csv")
elif export_csv:
    st.warning("Geen data om te exporteren.")

if export_json:
    payload = {
        "page_scales": st.session_state.page_scales,
        "diameter_overrides": st.session_state.diameter_overrides,
        "results": st.session_state.results_df.to_dict(orient="records") if not st.session_state.results_df.empty else [],
        "settings": {
            "coat_both_sides": coat_both_sides,
            "default_post_diameter_mm": default_post_diameter_mm,
        },
    }
    data = json.dumps(payload, indent=2).encode("utf-8")
    st.download_button("Download project JSON", data, file_name="hekwerk_project.json", mime="application/json")

if project_file is not None:
    try:
        payload = json.load(project_file)
        st.session_state.page_scales = {int(k) if isinstance(k,str) and k.isdigit() else int(k): float(v) for k,v in payload.get("page_scales", {}).items()}
        st.session_state.diameter_overrides = {str(k): float(v) for k,v in payload.get("diameter_overrides", {}).items()}
        results = payload.get("results", [])
        if results:
            st.session_state.results_df = pd.DataFrame(results)
        st.success("Project geladen. Let op: bestaande tekeningen op het canvas kunnen niet automatisch worden teruggezet in deze MVP.")
    except Exception as e:
        st.error(f"Kon project niet laden: {e}")

st.markdown("""
---
### 📦 Deploy-opties (Netlife klaarzetten)
**Docker (aanbevolen intern):**

**Dockerfile**
```
FROM python:3.11-slim
RUN apt-get update && apt-get install -y poppler-utils && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
EXPOSE 8501
CMD ["streamlit", "run", "app.py", "--server.enableCORS=false", "--server.enableXsrfProtection=false"]
```

**requirements.txt**
```
streamlit
streamlit-drawable-canvas
pdf2image
pillow
pandas
numpy
```

**Run**
```
docker build -t hekwerk-app .
docker run -d --name hekwerk -p 8501:8501 hekwerk-app
```

**Windows .exe (zonder Docker):**
1) `pip install -r requirements.txt` + Poppler installeren (zodat `pdf2image` werkt).
2) `pip install pyinstaller`
3) `pyinstaller --onefile app.py`
4) Start `dist/app.exe` → drag & drop PDF en werken.

> Indien Netlife een interne container registry of orkestratie (bv. Kubernetes) gebruikt, push de image en publiceer via de standaard ingress/proxy. De app is volledig self-contained.

**Beveiliging (optioneel):** voeg simpele wachtwoordprotectie toe met `streamlit-authenticator` of zet 'm achter jullie reverse proxy met SSO.

**Bekende beperking MVP:** herladen van getekende vormen in het canvas is (nog) niet mogelijk; wel worden schaal/diameters/resultaten opgeslagen. Dat kunnen we in v3 oplossen door objecten te serialiseren en terug te injecteren.
""")
