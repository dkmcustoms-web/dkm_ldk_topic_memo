"""
Talking-points spiekapp
-----------------------
Streamlit + Neon (PostgreSQL)

Tabs per onderwerp (AI, Prijs, Garantie, ...). Per tab korte bullets
die je in de app toevoegt/bewerkt/verwijdert. Tijdens een gesprek
sla je gewoon de juiste tab open en zie je je punten.

Env: DATABASE_URL  (Railway env var of .streamlit/secrets.toml)
"""

import os

import streamlit as st
from sqlalchemy import create_engine, text

# ---------------------------------------------------------------------------
# Branding
# ---------------------------------------------------------------------------
PRIMARY = "#3cceff"
ACCENT = "#f35e40"

st.set_page_config(page_title="Talking points", page_icon="💬", layout="wide")
st.markdown(
    f"""
    <style>
      .stApp h1 {{ color: {PRIMARY}; }}
      div.stButton > button[kind="primary"] {{ background-color: {ACCENT}; border: none; }}
      .bullet {{ font-size: 1.15rem; line-height: 1.9; }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
def _database_url():
    url = os.environ.get("DATABASE_URL") or st.secrets.get("DATABASE_URL")
    if not url:
        st.error("DATABASE_URL ontbreekt (env var of .streamlit/secrets.toml).")
        st.stop()
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


@st.cache_resource
def get_engine():
    return create_engine(_database_url(), pool_pre_ping=True)


def init_db():
    with get_engine().begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS topics (
                id     SERIAL PRIMARY KEY,
                naam   TEXT NOT NULL UNIQUE,
                positie INT NOT NULL DEFAULT 0
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS bullets (
                id       SERIAL PRIMARY KEY,
                topic_id INT NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
                tekst    TEXT NOT NULL,
                positie  INT NOT NULL DEFAULT 0
            )
        """))


def lijst_topics():
    with get_engine().connect() as conn:
        return conn.execute(text(
            "SELECT id, naam FROM topics ORDER BY positie, naam"
        )).fetchall()


def voeg_topic_toe(naam):
    with get_engine().begin() as conn:
        conn.execute(text(
            "INSERT INTO topics (naam) VALUES (:n) ON CONFLICT (naam) DO NOTHING"
        ), {"n": naam.strip()})


def hernoem_topic(tid, naam):
    with get_engine().begin() as conn:
        conn.execute(text("UPDATE topics SET naam = :n WHERE id = :id"),
                     {"n": naam.strip(), "id": tid})


def verwijder_topic(tid):
    with get_engine().begin() as conn:
        conn.execute(text("DELETE FROM topics WHERE id = :id"), {"id": tid})


def lijst_bullets(tid):
    with get_engine().connect() as conn:
        return conn.execute(text(
            "SELECT id, tekst FROM bullets WHERE topic_id = :t ORDER BY positie, id"
        ), {"t": tid}).fetchall()


def voeg_bullet_toe(tid, tekst):
    with get_engine().begin() as conn:
        conn.execute(text(
            "INSERT INTO bullets (topic_id, tekst) VALUES (:t, :x)"
        ), {"t": tid, "x": tekst.strip()})


def update_bullet(bid, tekst):
    with get_engine().begin() as conn:
        conn.execute(text("UPDATE bullets SET tekst = :x WHERE id = :id"),
                     {"x": tekst.strip(), "id": bid})


def verwijder_bullet(bid):
    with get_engine().begin() as conn:
        conn.execute(text("DELETE FROM bullets WHERE id = :id"), {"id": bid})


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
init_db()
st.title("💬 Talking points")

if "edit" not in st.session_state:
    st.session_state.edit = False

# ----- Sidebar: onderwerpen beheren -----
with st.sidebar:
    st.header("Onderwerpen")
    nieuw = st.text_input("Nieuw onderwerp", placeholder="bv. AI")
    if st.button("➕ Toevoegen", use_container_width=True) and nieuw.strip():
        voeg_topic_toe(nieuw)
        st.rerun()
    st.divider()
    st.session_state.edit = st.toggle("✏️ Bewerkmodus", value=st.session_state.edit)

topics = lijst_topics()

if not topics:
    st.info("Nog geen onderwerpen. Voeg er links eentje toe (bv. *AI*).")
    st.stop()

tabs = st.tabs([naam for _, naam in topics])
for tab, (tid, naam) in zip(tabs, topics):
    with tab:
        bullets = lijst_bullets(tid)

        if not st.session_state.edit:
            # --- Gespreksmodus: gewoon lezen ---
            if bullets:
                md = "\n".join(f"- {tekst}" for _, tekst in bullets)
                st.markdown(f"<div class='bullet'>\n\n{md}\n\n</div>",
                            unsafe_allow_html=True)
            else:
                st.caption("Nog geen punten. Zet bewerkmodus aan om toe te voegen.")
        else:
            # --- Bewerkmodus ---
            for bid, tekst in bullets:
                c1, c2 = st.columns([8, 1])
                with c1:
                    nieuwe = st.text_input(
                        "bullet", value=tekst, key=f"b_{bid}",
                        label_visibility="collapsed",
                    )
                    if nieuwe.strip() != tekst:
                        update_bullet(bid, nieuwe)
                with c2:
                    if st.button("🗑️", key=f"del_{bid}"):
                        verwijder_bullet(bid)
                        st.rerun()

            st.markdown("**Nieuw punt**")
            c1, c2 = st.columns([8, 1])
            with c1:
                nb = st.text_input("nieuwe bullet", key=f"new_{tid}",
                                   label_visibility="collapsed",
                                   placeholder="korte talking point...")
            with c2:
                if st.button("➕", key=f"add_{tid}") and nb.strip():
                    voeg_bullet_toe(tid, nb)
                    st.rerun()

            st.divider()
            with st.expander("Onderwerp beheren"):
                rn = st.text_input("Naam wijzigen", value=naam, key=f"rn_{tid}")
                cc1, cc2 = st.columns(2)
                with cc1:
                    if st.button("Opslaan naam", key=f"save_{tid}") and rn.strip():
                        hernoem_topic(tid, rn)
                        st.rerun()
                with cc2:
                    if st.button("🗑️ Onderwerp verwijderen", key=f"deltopic_{tid}"):
                        verwijder_topic(tid)
                        st.rerun()

st.caption("DKM-Customs — Developed by Luc De Kerf")
