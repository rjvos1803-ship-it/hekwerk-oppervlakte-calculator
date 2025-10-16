# App content minimized for brevity; same as previous cell
import io, json, math
from dataclasses import dataclass
from typing import Dict, List, Optional
import pandas as pd
from PIL import Image
import streamlit as st
from streamlit_drawable_canvas import st_canvas
try:
    import pypdfium2 as pdfium
    PDF_RENDERER = "pdfium"
except Exception:
    PDF_RENDERER = None
st.set_page_config(page_title="Hekwerk-oppervlakte-calculator", layout="wide")
st.title("🔧 Hekwerk-oppervlakte-calculator")
@dataclass
class Scale: px_per_mm: Optional[float] = None
def ensure_state():
    for k,v in {"pages":[],"page_scales":{},"diameter_overrides":{},"results_df":pd.DataFrame()}.items():
        if k not in st.session_state: st.session_state[k]=v
def load_pages(file_bytes: bytes, filename: str) -> List[Image.Image]:
    suffix = filename.lower().split(".")[-1]
    if suffix in {"png","jpg","jpeg","bmp","tiff"}:
        return [Image.open(io.BytesIO(file_bytes)).convert("RGB")]
    elif suffix=="pdf":
        if PDF_RENDERER!="pdfium": st.error("PDF-rendering niet beschikbaar."); st.stop()
        pdf = pdfium.PdfDocument(io.BytesIO(file_bytes)); scale=200/72; out=[]
        for i in range(len(pdf)): out.append(pdf[i].render(scale=scale).to_pil().convert("RGB"))
        return out
    else: st.error("Bestandstype niet ondersteund."); st.stop()
def canvas_objects(js): return js.get("objects",[]) if js else []
ensure_state()
with st.sidebar:
    coat_both_sides = st.checkbox("Panels dubbelzijdig coaten?", True)
    default_post_diameter_mm = st.number_input("Standaard paaldiameter (mm)", 1.0, step=1.0, value=60.0)
    export_csv = st.button("📥 Exporteer resultaten (CSV)")
upload = st.file_uploader("Upload PDF/afbeelding", type=["pdf","png","jpg","jpeg","bmp","tiff"]) 
if not upload and not st.session_state.pages: st.info("Upload een tekening om te beginnen."); st.stop()
if upload: st.session_state.pages = load_pages(upload.read(), upload.name)
pages = st.session_state.pages; page_idx = 0
if len(pages)>1: page_idx = st.number_input("Pagina", 1, len(pages), 1)-1
base_img = pages[page_idx]; W,H = base_img.size
c1,c2 = st.columns([1,2])
with c1:
    scale_len_mm = st.number_input("Werkelijke lengte (mm)", 0.0, step=1.0, value=1000.0, key=f"scale_{page_idx}")
    scale_canvas = st_canvas(fill_color="rgba(255,165,0,0.2)", stroke_width=3, stroke_color="#f00", background_image=base_img, background_color="#eee", update_streamlit=True, height=min(600,int(H*0.75)), width=min(600,int(W*0.75)), drawing_mode="line", key=f"scale_canvas_{page_idx}")
    px_per_mm=None; max_len=0.0
    for o in canvas_objects(scale_canvas.json_data):
        if o.get("type")=="line":
            x1,y1,x2,y2 = o.get("x1",0),o.get("y1",0),o.get("x2",0),o.get("y2",0)
            L=( (x2-x1)**2 + (y2-y1)**2 )**0.5
            if L>max_len: max_len=L
    if max_len>0 and scale_len_mm>0: px_per_mm=max_len/scale_len_mm; st.session_state.page_scales[page_idx]=px_per_mm
    else: px_per_mm=st.session_state.page_scales.get(page_idx)
with c2:
    tabs = st.tabs(["Panelen","Palen/Buizen"])
    with tabs[0]:
        panel_canvas = st_canvas(fill_color="rgba(0,200,0,0.2)", stroke_width=2, stroke_color="#0a0", background_image=base_img, background_color="#eee", update_streamlit=True, height=min(800,H), width=min(1000,W), drawing_mode="rect", key=f"panel_{page_idx}")
        panels = canvas_objects(panel_canvas.json_data)
    with tabs[1]:
        post_canvas = st_canvas(fill_color="rgba(0,0,0,0)", stroke_width=3, stroke_color="#06f", background_image=base_img, background_color="#eee", update_streamlit=True, height=min(800,H), width=min(1000,W), drawing_mode="line", key=f"post_{page_idx}")
        posts = canvas_objects(post_canvas.json_data)
rows=[]; label=f"p{page_idx+1}"
if px_per_mm:
    for i,o in enumerate(panels or [],1):
        if o.get("type")=="rect":
            w_px=abs(o.get("width",0))*o.get("scaleX",1.0); h_px=abs(o.get("height",0))*o.get("scaleY",1.0)
            w_mm=w_px/px_per_mm; h_mm=h_px/px_per_mm; area=(w_mm*h_mm)/1_000_000.0; 
            if coat_both_sides: area*=2.0
            rows.append({"Pagina":label,"Type":"Paneel","ID":f"{label}-panel-{i}","Breedte (mm)":round(w_mm,1),"Hoogte (mm)":round(h_mm,1),"Dubbelzijdig":coat_both_sides,"Diameter (mm)":None,"Lengte (m)":None,"Oppervlakte (m²)":round(area,4)})
    for i,o in enumerate(posts or [],1):
        if o.get("type")=="line":
            x1,y1,x2,y2=o.get("x1",0),o.get("y1",0),o.get("x2",0),o.get("y2",0)
            L_m = (((x2-x1)**2+(y2-y1)**2)**0.5)/px_per_mm/1000.0
            dia=60.0; area=(3.1415926535*dia*(L_m*1000.0))/1_000_000.0
            rows.append({"Pagina":label,"Type":"Paal/Buis","ID":f"{label}-post-{i}","Breedte (mm)":None,"Hoogte (mm)":None,"Dubbelzijdig":None,"Diameter (mm)":dia,"Lengte (m)":round(L_m,3),"Oppervlakte (m²)":round(area,4)})
import pandas as pd
df = pd.DataFrame(rows) if rows else pd.DataFrame(columns=["Pagina","Type","ID","Breedte (mm)","Hoogte (mm)","Dubbelzijdig","Diameter (mm)","Lengte (m)","Oppervlakte (m²)"])
st.dataframe(df, use_container_width=True)
if export_csv and not df.empty: st.download_button("Download CSV", df.to_csv(index=False).encode("utf-8"), file_name="hekwerk_oppervlakte_resultaten.csv", mime="text/csv")
