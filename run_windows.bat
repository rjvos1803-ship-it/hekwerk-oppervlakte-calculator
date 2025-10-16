@echo off
SETLOCAL
IF NOT EXIST .venv (
  py -m venv .venv
)
CALL .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
streamlit run app.py
