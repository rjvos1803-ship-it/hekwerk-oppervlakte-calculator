# Hekwerk-oppervlakte-calculator (v2)

## Snel starten (Windows / macOS / Linux met Python 3.10+)
1. Installeer Poppler (nodig voor PDF → image).
2. In deze map:
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```
3. Open de link (http://localhost:8501) en sleep je PDF erin.

## Docker
```bash
docker build -t hekwerk-app .
docker run -d --name hekwerk -p 8501:8501 hekwerk-app
```

## .exe bouwen (optioneel)
```bash
pip install pyinstaller
pyinstaller --onefile app.py
dist/app.exe
```

