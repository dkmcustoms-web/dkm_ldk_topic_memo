"""
Talking-points spiekapp + gespreksnotities
-------------------------------------------
Streamlit + Neon (PostgreSQL)

Zijbalk-navigatie:
  - Talking points : vaste onderwerpen (AI, Prijs, ...) met korte bullets
  - Gesprekken     : per koper een gesprek met vrije notities, opgeslagen in DB

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
      .block-container {{ padding-top: 2rem; }}
      .app-title {{ color: {PRIMARY}; font-size: 1.6rem; font-weight: 700;
                    margin: 0 0 1rem 0; }}
      div.stButton > button[kind="primary"] {{ background-color: {ACCENT}; border: none; }}
      .bullet {{ font-size: 1.1rem; line-height: 1.8; }}
      section[data-testid="stSidebar"] .stButton > button {{ text-align: left; }}
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


@st.cache_resource
def init_db():
    with get_engine().begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS topics (
                id      SERIAL PRIMARY KEY,
                naam    TEXT NOT NULL UNIQUE,
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
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS gesprekken (
                id         SERIAL PRIMARY KEY,
                koper      TEXT NOT NULL,
                aangemaakt TIMESTAMPTZ NOT NULL DEFAULT now(),
                bijgewerkt TIMESTAMPTZ NOT NULL DEFAULT now(),
                notities   TEXT NOT NULL DEFAULT ''
            )
        """))


# ----- Topics / bullets -----
@st.cache_data(ttl=300)
def lijst_topics():
    with get_engine().connect() as conn:
        return conn.execute(text(
            "SELECT id, naam FROM topics ORDER BY positie, naam")).fetchall()


def voeg_topic_toe(naam):
    with get_engine().begin() as conn:
        conn.execute(text(
            "INSERT INTO topics (naam) VALUES (:n) ON CONFLICT (naam) DO NOTHING"),
            {"n": naam.strip()})
    lijst_topics.clear()


def hernoem_topic(tid, naam):
    with get_engine().begin() as conn:
        conn.execute(text("UPDATE topics SET naam = :n WHERE id = :id"),
                     {"n": naam.strip(), "id": tid})
    lijst_topics.clear()


def verwijder_topic(tid):
    with get_engine().begin() as conn:
        conn.execute(text("DELETE FROM topics WHERE id = :id"), {"id": tid})
    lijst_topics.clear()
    lijst_bullets.clear()


@st.cache_data(ttl=300)
def lijst_bullets(tid):
    with get_engine().connect() as conn:
        return conn.execute(text(
            "SELECT id, tekst FROM bullets WHERE topic_id = :t ORDER BY positie, id"),
            {"t": tid}).fetchall()


def voeg_bullet_toe(tid, tekst):
    with get_engine().begin() as conn:
        conn.execute(text(
            "INSERT INTO bullets (topic_id, tekst) VALUES (:t, :x)"),
            {"t": tid, "x": tekst.strip()})
    lijst_bullets.clear()


def update_bullet(bid, tekst):
    with get_engine().begin() as conn:
        conn.execute(text("UPDATE bullets SET tekst = :x WHERE id = :id"),
                     {"x": tekst.strip(), "id": bid})
    lijst_bullets.clear()


def verwijder_bullet(bid):
    with get_engine().begin() as conn:
        conn.execute(text("DELETE FROM bullets WHERE id = :id"), {"id": bid})
    lijst_bullets.clear()


# ----- Gesprekken -----
@st.cache_data(ttl=300)
def lijst_gesprekken():
    with get_engine().connect() as conn:
        return conn.execute(text(
            "SELECT id, koper, bijgewerkt FROM gesprekken ORDER BY bijgewerkt DESC"
        )).fetchall()


@st.cache_data(ttl=300)
def laad_gesprek(gid):
    with get_engine().connect() as conn:
        return conn.execute(text(
            "SELECT koper, notities FROM gesprekken WHERE id = :id"),
            {"id": gid}).fetchone()


def nieuw_gesprek(koper):
    with get_engine().begin() as conn:
        gid = conn.execute(text(
            "INSERT INTO gesprekken (koper) VALUES (:k) RETURNING id"),
            {"k": koper.strip()}).scalar_one()
    lijst_gesprekken.clear()
    return gid


def bewaar_gesprek(gid, koper, notities):
    with get_engine().begin() as conn:
        conn.execute(text("""
            UPDATE gesprekken SET koper = :k, notities = :n, bijgewerkt = now()
             WHERE id = :id
        """), {"id": gid, "k": koper.strip(), "n": notities})
    lijst_gesprekken.clear()
    laad_gesprek.clear()


def verwijder_gesprek(gid):
    with get_engine().begin() as conn:
        conn.execute(text("DELETE FROM gesprekken WHERE id = :id"), {"id": gid})
    lijst_gesprekken.clear()
    laad_gesprek.clear()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
init_db()

ss = st.session_state
ss.setdefault("view", "topics")          # "topics" | "gesprekken"
ss.setdefault("edit", False)
ss.setdefault("active_topic", None)
ss.setdefault("active_gid", None)

# ----- Sidebar -----
with st.sidebar:
    st.markdown("### 💬 Menu")
    if st.button("📌 Talking points", use_container_width=True):
        ss.view = "topics"
        st.rerun()
    if st.button("🗂️ Gesprekken", use_container_width=True):
        ss.view = "gesprekken"
        st.rerun()
    st.divider()

    if ss.view == "topics":
        st.markdown("**Onderwerpen**")
        topics = lijst_topics()
        for tid, naam in topics:
            if st.button(naam, key=f"topic_{tid}", use_container_width=True):
                ss.active_topic = tid
                st.rerun()
        st.divider()
        nieuw = st.text_input("Nieuw onderwerp", placeholder="bv. AI")
        if st.button("➕ Toevoegen", use_container_width=True) and nieuw.strip():
            voeg_topic_toe(nieuw)
            st.rerun()
        st.divider()
        ss.edit = st.toggle("✏️ Bewerkmodus", value=ss.edit)

    else:  # gesprekken
        st.markdown("**Gesprekken**")
        if st.button("➕ Nieuw gesprek", use_container_width=True):
            ss.active_gid = "new"
            st.rerun()
        st.divider()
        for gid, koper, bij in lijst_gesprekken():
            label = f"{koper or '(naamloos)'} · {bij:%d/%m %H:%M}"
            if st.button(label, key=f"gespr_{gid}", use_container_width=True):
                ss.active_gid = gid
                st.rerun()


# ===========================================================================
# VIEW: Talking points
# ===========================================================================
if ss.view == "topics":
    st.markdown("<div class='app-title'>📌 Talking points</div>",
                unsafe_allow_html=True)

    topics = lijst_topics()
    if not topics:
        st.info("Nog geen onderwerpen. Voeg er links eentje toe (bv. *AI*).")
        st.stop()

    ids = [t[0] for t in topics]
    if ss.active_topic not in ids:
        ss.active_topic = ids[0]
    tid = ss.active_topic
    naam = dict(topics)[tid]

    st.subheader(naam)
    bullets = lijst_bullets(tid)

    if not ss.edit:
        if bullets:
            md = "\n".join(f"- {tekst}" for _, tekst in bullets)
            st.markdown(f"<div class='bullet'>\n\n{md}\n\n</div>",
                        unsafe_allow_html=True)
        else:
            st.caption("Nog geen punten. Zet bewerkmodus aan om toe te voegen.")
    else:
        for bid, tekst in bullets:
            c1, c2 = st.columns([8, 1])
            with c1:
                nieuwe = st.text_input("bullet", value=tekst, key=f"b_{bid}",
                                       label_visibility="collapsed")
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
                    ss.active_topic = None
                    st.rerun()


# ===========================================================================
# VIEW: Gesprekken
# ===========================================================================
else:
    st.markdown("<div class='app-title'>🗂️ Gesprekken</div>",
                unsafe_allow_html=True)

    if ss.active_gid is None:
        st.caption("Kies links een gesprek of maak een nieuw gesprek aan.")
        st.stop()

    if ss.active_gid == "new":
        koper, notities = "", ""
    else:
        rec = laad_gesprek(ss.active_gid)
        if rec is None:
            ss.active_gid = None
            st.rerun()
        koper, notities = rec.koper, rec.notities

    koper_in = st.text_input("Koper / bedrijf", value=koper,
                             placeholder="bv. Acme NV")
    notities_in = st.text_area("Notities", value=notities, height=360,
                               placeholder="Vrije notities tijdens het gesprek...")

    c1, c2, _ = st.columns([1, 1, 4])
    with c1:
        if st.button("💾 Opslaan", type="primary", use_container_width=True):
            if not koper_in.strip():
                st.warning("Vul eerst een kopernaam in.")
            else:
                if ss.active_gid == "new":
                    ss.active_gid = nieuw_gesprek(koper_in)
                bewaar_gesprek(ss.active_gid, koper_in, notities_in)
                st.success("Opgeslagen.")
                st.rerun()
    with c2:
        if ss.active_gid != "new":
            if st.button("🗑️ Verwijderen", use_container_width=True):
                verwijder_gesprek(ss.active_gid)
                ss.active_gid = None
                st.rerun()

st.caption("DKM-Customs — Developed by Luc De Kerf")
