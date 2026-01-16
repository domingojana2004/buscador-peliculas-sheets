import random
import pandas as pd
import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from gspread.utils import rowcol_to_a1

st.set_page_config(page_title="Buscador de Películas Chinguis", layout="wide")

REQUIRED_COLS = ["Nombre","Género","Año","Saga","Numero saga","Duración","Plataforma","Rating","¿Mugui?","¿Punti?"]
EDIT_COLS = ["¿Mugui?","¿Punti?"]

def _gc():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    return gspread.authorize(creds)

def read_sheet():
    gc = _gc()
    sh = gc.open_by_key(st.secrets["SHEET_ID"])
    ws = sh.worksheet(st.secrets["WORKSHEET_NAME"])
    values = ws.get_all_values()
    if not values:
        return ws, pd.DataFrame(columns=REQUIRED_COLS)

    header = values[0]
    rows = values[1:]
    df = pd.DataFrame(rows, columns=header)

    for c in REQUIRED_COLS:
        if c not in df.columns:
            df[c] = ""

    df = df[REQUIRED_COLS].copy()
    df["Año"] = pd.to_numeric(df["Año"], errors="coerce").astype("Int64")
    df["Duración"] = pd.to_numeric(df["Duración"], errors="coerce").astype("Int64")
    df["Rating"] = pd.to_numeric(df["Rating"], errors="coerce")

    def to_bool(x):
        s = str(x).strip().lower()
        return s in ["true","1","yes","y","si","sí","x"]

    for c in EDIT_COLS:
        df[c] = df[c].apply(to_bool)

    df["_row"] = range(2, len(df) + 2)
    return ws, df

def update_cells(ws, updates):
    if updates:
        ws.batch_update(updates)

def platform_tokens(s):
    if s is None:
        return []
    return [t.strip() for t in str(s).split(";") if t.strip()]

st.markdown("## 🎬 Buscador de Películas Chinguis")

ws, base_df = read_sheet()

with st.sidebar:
    st.markdown("## 🎥 Filtros")

    genres = sorted([g for g in base_df["Género"].dropna().unique().tolist() if str(g).strip() != ""])
    all_platforms = set()
    for v in base_df["Plataforma"].fillna(""):
        for t in platform_tokens(v):
            all_platforms.add(t)
    platforms = sorted(all_platforms)

    sel_gen = st.multiselect("Género", options=genres, default=[])
    sel_plat = st.multiselect("Plataforma", options=platforms, default=[])

    if base_df["Año"].dropna().empty:
        y_min, y_max = 1900, 2025
    else:
        y_min = int(base_df["Año"].dropna().min())
        y_max = int(base_df["Año"].dropna().max())

    year_range = st.slider("Año", min_value=y_min, max_value=y_max, value=(y_min, y_max))

    excl_mugui = st.checkbox("❌ Excluir vistas por Mugui", value=False)
    excl_punti = st.checkbox("❌ Excluir vistas por Punti", value=False)

    order_col = st.selectbox("Ordenar por", ["Nombre","Año","Duración","Rating","Género","Plataforma","Saga","Numero saga"], index=0)
    order_dir = st.radio("Dirección", ["Ascendente","Descendente"], index=0, horizontal=False)

df = base_df.copy()

if sel_gen:
    df = df[df["Género"].isin(sel_gen)]

if sel_plat:
    def has_any_platform(cell):
        toks = set(platform_tokens(cell))
        return any(p in toks for p in sel_plat)
    df = df[df["Plataforma"].apply(has_any_platform)]

df = df[(df["Año"].fillna(-10_000) >= year_range[0]) & (df["Año"].fillna(10_000) <= year_range[1])]

if excl_mugui:
    df = df[~df["¿Mugui?"].astype(bool)]
if excl_punti:
    df = df[~df["¿Punti?"].astype(bool)]

ascending = (order_dir == "Ascendente")
df = df.sort_values(by=order_col, ascending=ascending, na_position="last")

st.markdown(f"### 🔎 Se encontraron **{len(df)}** películas")

col_order = ["Nombre","Género","Año","Saga","Numero saga","Duración","Plataforma","Rating","¿Mugui?","¿Punti?","_row"]
df_view = df[col_order].copy()

edited = st.data_editor(
    df_view,
    hide_index=True,
    use_container_width=True,
    column_config={
        "_row": st.column_config.NumberColumn("_row", disabled=True),
        "¿Mugui?": st.column_config.CheckboxColumn("¿Mugui?"),
        "¿Punti?": st.column_config.CheckboxColumn("¿Punti?"),
    },
    disabled=["Nombre","Género","Año","Saga","Numero saga","Duración","Plataforma","Rating","_row"],
    key="table_editor",
)

edited_df = pd.DataFrame(edited)
updates = []

if not edited_df.empty:
    base_map = base_df.set_index("_row")[EDIT_COLS]
    edited_map = edited_df.set_index("_row")[EDIT_COLS]

    changed_rows = base_map.index.intersection(edited_map.index)
    for r in changed_rows:
        for col_name in EDIT_COLS:
            old = bool(base_map.loc[r, col_name])
            new = bool(edited_map.loc[r, col_name])
            if old != new:
                col_idx = REQUIRED_COLS.index(col_name) + 1
                a1 = rowcol_to_a1(int(r), int(col_idx))
                updates.append({"range": a1, "values": [[str(new).upper()]]})

update_cells(ws, updates)

st.markdown("")
if st.button("🍿 Mostrar una película al azar"):
    if len(df) == 0:
        st.info("No hay resultados con estos filtros.")
    else:
        pick = df.sample(1).iloc[0].to_dict()
        st.markdown(
            f"""
**{pick.get("Nombre","")}**

- **Género:** {pick.get("Género","")}
- **Año:** {pick.get("Año","")}
- **Saga:** {pick.get("Saga","")}
- **Número saga:** {pick.get("Numero saga","")}
- **Duración:** {pick.get("Duración","")} min
- **Plataforma:** {pick.get("Plataforma","")}
- **Rating:** {pick.get("Rating","")}
- **¿Mugui?:** {"✅" if pick.get("¿Mugui?", False) else "⬜"}
- **¿Punti?:** {"✅" if pick.get("¿Punti?", False) else "⬜"}
            """.strip()
        )
