# Hekwerk-oppervlakte-calculator — Streamlit (Cloud, full version)
# - PDF rendering via pypdfium2 (no Poppler required)
# - Multipage PDF support, scale per page
# - Panels (rectangles) and Posts/Pipes (lines) with editable diameters
# - CSV & JSON export + JSON import (settings & results)
# - Version-pinned and with compatibility shim for streamlit-drawable-canvas

import io
import json
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import pandas as pd
from PIL import Image
import streamlit as st
from streamlit_drawable_canvas import st_canvas

# --- Compat patch for streamlit-drawable-canvas across Streamlit versions ---
try:
    from streamlit.elements.image import ImageMixin as _ImageMixin
    if not hasattr(_ImageMixin, "image_to_url") and hasattr(_ImageMixin, "_image_to_url"):
        _ImageMixin.image_to_url = _ImageMixin._image_to_url  # type: ignore[attr-defined]
except Exception:
    pass
# ---------------------------------------------------------------------------

# --- PDF rendering (Streamlit Cloud friendly) ---
try:
    import pypdfium2 as pdfium
    PDF_RENDERER = "pdfium"
except Exception:
    PDF_RENDERER = None

st.set_page_config(page_title="Hekwerk-oppervlakte-calculator", layout="wide")
st.title("🔧 Hekwerk-oppervlakte-calculator — Cloud (volledige versie)")

st.markdown(
    """
    **Workflow**
    1. **Upload** tekening (PDF of afbeelding). Bij PDF kun je de **pagina** kiezen.
    2. Zet de **schaal** op de huidige pagina: teken een **rechte lijn** over een bekende maat en vul de lengte (mm) in.
    3. Teken *rechthoeken* (panelen/plaat) en *lijnen* (palen/buizen).
    4. Pas **diameters per lijn** aan in de tabel en **exporteer** CSV/JSON.
    """
)

@dataclass
class Scale:
    px_per_mm: Optional[float] = None

def ensure_state():
    if "pages" not in st.session_state:
        st.session_state.pages = []
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
        if PDF_RENDERER != "pdfium":
            st.error("PDF-rendering niet beschikbaar. Installeer 'pypdfium2'.")
            st.stop()
        pdf = pdfium.PdfDocument(io.BytesIO(file_bytes))
        dpi = 200
        scale = dpi / 72.0
        pages = []
        for i in range(len(pdf)):
            page = pdf[i]
            pages.append(page.render(scale=scale).to_pil().convert("RGB"))
        if not pages:
            st.error("Kon de PDF niet renderen.")
            st.stop()
        return pages
    else:
        st.error("Bestandstype niet ondersteund.")
        st.stop()

def canvas_objects(canvas_json):
    if not canvas_json or not canvas_json.get("objects"):
        return []
    return canvas_json["objects"]

ensure_state()

with st.sidebar:
    st.header("Instellingen")
    coat_both_sides = st.checkbox("Panels dubbelzijdig coaten?", value=True)
    default_post_diameter_mm = st.number_input("Standaard paaldiameter (mm)", min_value=1.0, step=1.0, value=60.0)

    st.markdown("**Export**")
    export_csv = st.button("📥 Exporteer resultaten (CSV)")
    export_json = st.button("🧩 Exporteer project (JSON)")

    st.markdown("**Import project**")
    project_file = st.file_uploader("Laad project JSON", type=["json"], key="project_json")

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

with col_scale:
    st.subheader("1) Schaal zetten (per pagina)")
    st.caption("Teken een **rechte lijn** over een bekende maat en vul **lengte (mm)** in.")

    scale_len_mm = st.number_input("Werkelijke lengte (mm)", min_value=0.0, step=1.0, value=1000.0, key=f"scale_len_mm_{page_idx}")

    scale_canvas = st_canvas(
        fill_color="rgba(255, 165, 0, 0.2)",
        stroke_width=3,
        stroke_color="#ff0000",
        background_image=base_img,  # PIL.Image
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

with col_draw:
    st.subheader("2) Objecten tekenen en berekenen")
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
        st.caption("Teken **lijnen** voor palen/buizen. Diameter kun je zo aanpassen in de tabel.")
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

rows: List[dict] = []
page_label = f"p{page_idx+1}"

if px_per_mm:
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

df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["Pagina","Type","ID","Breedte (mm)","Hoogte (mm)","Dubbelzijdig","Diameter (mm)","Lengte (m)","Oppervlakte (m²)"])

st.subheader("3) Resultaten (diameter per lijn aanpasbaar)")
if df.empty:
    st.warning("Nog geen objecten of schaal niet gezet voor deze pagina.")
else:
    edited = st.data_editor(
        df,
        use_container_width=True,
        column_config={
            "Diameter (mm)": st.column_config.NumberColumn("Diameter (mm)", min_value=1.0, step=1.0),
        },
        disabled=[c for c in df.columns if c != "Diameter (mm)"],
        key=f"editor_{page_idx}",
    )

    def recompute_surfaces(df_edit: pd.DataFrame) -> Tuple[pd.DataFrame, float, float, float, float]:
        panel_area = float(df_edit.loc[df_edit["Type"] == "Paneel", "Oppervlakte (m²)"].sum())
        post_rows = df_edit[df_edit["Type"] == "Paal/Buis"].copy()
        # herbereken paal-oppervlak met aangepaste diameter
        post_rows["Oppervlakte (m²)"] = (math.pi * post_rows["Diameter (mm)"] * (post_rows["Lengte (m)"] * 1000.0)) / 1_000_000.0
        post_area = float(post_rows["Oppervlakte (m²)"].sum())
        total_area = panel_area + post_area
        post_len_total = float(post_rows["Lengte (m)"].sum())
        # store overrides
        for _, r in post_rows.iterrows():
            st.session_state.diameter_overrides[str(r["ID"])] = float(r["Diameter (mm)"] or default_post_diameter_mm)
        # return merged view
        merged = pd.concat([df_edit[df_edit["Type"] == "Paneel"], post_rows], ignore_index=True)
        return merged, panel_area, post_area, total_area, post_len_total

    edited, panel_area, post_area, total_area, post_len_total = recompute_surfaces(edited)
    st.session_state.results_df = edited

    c1, c2, c3 = st.columns(3)
    c1.metric("Totaal paneel-oppervlak", f"{panel_area:.3f} m²")
    c2.metric("Totaal paal/buis-oppervlak", f"{post_area:.3f} m²")
    c3.metric("Totaal (m²)", f"{total_area:.3f} m²")
    if post_len_total > 0:
        st.caption(f"Totale paal-/buislengte: **{post_len_total:.2f} m**")

# Export / Import
if export_csv and not st.session_state.results_df.empty:
    csv = st.session_state.results_df.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", csv, file_name="hekwerk_oppervlakte_resultaten.csv", mime="text/csv")
elif export_csv:
    st.warning("Geen data om te exporteren.")

if export_json and not st.session_state.results_df.empty:
    payload = {
        "page_scales": st.session_state.page_scales,
        "diameter_overrides": st.session_state.diameter_overrides,
        "results": st.session_state.results_df.to_dict(orient="records"),
        "settings": {
            "coat_both_sides": coat_both_sides,
            "default_post_diameter_mm": default_post_diameter_mm,
        },
    }
    st.download_button("Download project JSON", json.dumps(payload, indent=2).encode("utf-8"), file_name="hekwerk_project.json", mime="application/json")

if project_file is not None:
    try:
        payload = json.load(project_file)
        st.session_state.page_scales = {int(k) if isinstance(k,str) and k.isdigit() else int(k): float(v) for k,v in payload.get("page_scales", {}).items()}
        st.session_state.diameter_overrides = {str(k): float(v) for k,v in payload.get("diameter_overrides", {}).items()}
        results = payload.get("results", [])
        if results:
            st.session_state.results_df = pd.DataFrame(results)
        st.success("Project geladen. (Canvas-vormen opnieuw tekenen is in deze versie nog niet mogelijk.)")
    except Exception as e:
        st.error(f"Kon project niet laden: {e}")
