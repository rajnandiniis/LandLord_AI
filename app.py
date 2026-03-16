"""
LandlordAI v2 — app.py
=======================
UI ONLY. All logic lives in agents/ and utils/.

Run: streamlit run app.py
"""

import os, io, json, zipfile
from datetime import datetime, timedelta

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

# ── Internal imports ──────────────────────────────────────────────────────────
from config.settings  import VIOLATION_CLASSES, NYC_AGENCIES, FINE_REDUCTION_TIPS, SUMMONS_TYPES, APP_NAME, APP_VERSION
from utils.extractor  import extract_text, fetch_violations_from_api, format_violation_text
from utils.validator  import check_api_key, check_file, check_text, sanitize_filename
from utils.excel_processor import build_excel
from utils.pdf_generator   import build_pdf
from agents.reader_agent   import analyze_violation
from agents.research_agent import build_action_plan
from agents.writer_agent   import write_letters
from agents.document_agent import scrape_document, generate_summons_text

load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title=f"{APP_NAME} — NYC Property Assistant",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────────────────────
# SESSION STATE DEFAULTS
# ─────────────────────────────────────────────────────────────────────────────
DEFAULTS = {
    "theme":         "dark",
    "font_size":     "medium",
    "accent":        "gold",
    "compact":       False,
    "openai_key":    os.getenv("OPENAI_API_KEY", ""),
    "owner_name":    "",
    "property_addr": "",
    "chat":          [],
    "pending_q":     None,
    "history":       [],
    "scraped_db":    [],
    "last_scraped":  None,
    "vdata": None, "rdata": None, "ldata": None,
    "auto_run_text": None,
}
for k, v in DEFAULTS.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ─────────────────────────────────────────────────────────────────────────────
# THEME ENGINE
# ─────────────────────────────────────────────────────────────────────────────
def get_theme_vars():
    dark = st.session_state["theme"] == "dark"
    accent = st.session_state["accent"]

    accents = {
        "gold":  ("#C9A84C", "#E8C96D"),
        "blue":  ("#3B82F6", "#60A5FA"),
        "green": ("#10B981", "#34D399"),
        "rose":  ("#F43F5E", "#FB7185"),
    }
    a1, a2 = accents.get(accent, accents["gold"])

    font_sizes = {"small": "13px", "medium": "15px", "large": "17px"}
    fs = font_sizes.get(st.session_state["font_size"], "15px")

    if dark:
        return {
            "--bg":       "#0A1628",
            "--bg2":      "#0F2044",
            "--bg3":      "#162A52",
            "--surface":  "#1E3A5F",
            "--border":   "#2A4A7F",
            "--text":     "#F1F5F9",
            "--text2":    "#94A3B8",
            "--text3":    "#64748B",
            "--accent":   a1,
            "--accent2":  a2,
            "--red":      "#EF4444",
            "--orange":   "#F97316",
            "--amber":    "#F59E0B",
            "--green":    "#10B981",
            "--fs":       fs,
            "--sidebar-bg": "#050E1A",
        }
    else:
        return {
            "--bg":       "#F8FAFC",
            "--bg2":      "#FFFFFF",
            "--bg3":      "#F1F5F9",
            "--surface":  "#FFFFFF",
            "--border":   "#E2E8F0",
            "--text":     "#0F172A",
            "--text2":    "#475569",
            "--text3":    "#94A3B8",
            "--accent":   a1,
            "--accent2":  a2,
            "--red":      "#DC2626",
            "--orange":   "#EA580C",
            "--amber":    "#D97706",
            "--green":    "#059669",
            "--fs":       fs,
            "--sidebar-bg": "#0A1628",
        }


def inject_css():
    t = get_theme_vars()
    compact_pad = "12px 14px" if st.session_state["compact"] else "20px 24px"

    st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@600;700;800&family=Outfit:wght@300;400;500;600;700&display=swap');

:root {{
{"".join(f"  {k}: {v};" for k, v in t.items())}
}}

* {{ box-sizing: border-box; }}

html, body, .stApp {{
  background: var(--bg) !important;
  font-family: 'Outfit', sans-serif !important;
  font-size: var(--fs) !important;
  color: var(--text) !important;
}}

/* ── Hide chrome ── */
#MainMenu, footer, header {{ visibility: hidden; }}
.block-container {{ padding: 0 1.5rem 2rem 1.5rem !important; max-width: 1440px; }}

/* ── Sidebar ── */
div[data-testid="stSidebar"] {{
  background: var(--sidebar-bg) !important;
  border-right: 1px solid rgba(201,168,76,0.15) !important;
}}
div[data-testid="stSidebar"] * {{ color: #94A3B8 !important; }}
div[data-testid="stSidebar"] h1,
div[data-testid="stSidebar"] h2,
div[data-testid="stSidebar"] h3,
div[data-testid="stSidebar"] h4 {{
  color: var(--accent) !important;
  font-family: 'Cormorant Garamond', serif !important;
}}
div[data-testid="stSidebar"] .stTextInput input,
div[data-testid="stSidebar"] .stSelectbox > div > div {{
  background: rgba(255,255,255,0.05) !important;
  border: 1px solid rgba(255,255,255,0.12) !important;
  color: #e2e8f0 !important;
  border-radius: 8px !important;
}}
div[data-testid="stSidebar"] .stRadio label span,
div[data-testid="stSidebar"] .stCheckbox label span {{
  color: #94A3B8 !important;
}}

/* ── Typography ── */
h1, h2, h3 {{ font-family: 'Cormorant Garamond', serif !important; color: var(--text) !important; }}

/* ── Hero ── */
.hero {{
  background: linear-gradient(135deg, var(--bg2) 0%, var(--bg3) 100%);
  border: 1px solid rgba(201,168,76,0.18);
  border-radius: 24px;
  padding: 52px 48px;
  margin: 20px 0 28px 0;
  position: relative;
  overflow: hidden;
}}
.hero::before {{
  content:''; position:absolute; top:-80px; right:-80px;
  width:360px; height:360px;
  background: radial-gradient(circle, rgba(201,168,76,0.10) 0%, transparent 70%);
  border-radius:50%;
}}
.hero-title {{
  font-family: 'Cormorant Garamond', serif;
  font-size: 3.4rem; font-weight: 800;
  color: var(--text); line-height: 1.12; margin: 0 0 14px 0;
}}
.hero-title span {{ color: var(--accent); }}
.hero-sub {{
  color: var(--text2); font-size: 1.05rem; font-weight: 300;
  max-width: 580px; line-height: 1.7; margin: 0 0 26px 0;
}}
.hero-badge {{
  display:inline-flex; align-items:center; gap:5px;
  padding:5px 14px; border-radius:100px;
  font-size:0.78rem; font-weight:600;
  background: rgba(201,168,76,0.10);
  border: 1px solid rgba(201,168,76,0.25);
  color: var(--accent); margin:3px;
}}

/* ── Stat cards ── */
.stat-grid {{ display:grid; grid-template-columns:repeat(4,1fr); gap:14px; margin:0 0 28px 0; }}
.stat-card {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 22px 18px;
  text-align: center;
  transition: transform 0.2s, box-shadow 0.2s;
  cursor: default;
}}
.stat-card:hover {{ transform:translateY(-3px); box-shadow:0 8px 32px rgba(0,0,0,0.15); }}
.stat-num {{ font-family:'Cormorant Garamond',serif; font-size:2.6rem; font-weight:700; color:var(--text); line-height:1; }}
.stat-num.a {{ color:var(--accent); }}
.stat-lbl {{ color:var(--text3); font-size:0.72rem; font-weight:600; letter-spacing:0.07em; text-transform:uppercase; margin-top:6px; }}

/* ── Card ── */
.card {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 18px;
  padding: {compact_pad};
  margin: 10px 0;
  transition: box-shadow 0.2s;
}}
.card:hover {{ box-shadow: 0 4px 20px rgba(0,0,0,0.10); }}
.card-critical {{ border-left:4px solid var(--red); }}
.card-high     {{ border-left:4px solid var(--orange); }}
.card-medium   {{ border-left:4px solid var(--amber); }}
.card-low      {{ border-left:4px solid var(--green); }}

/* ── Severity badges ── */
.badge {{
  display:inline-flex; align-items:center; gap:5px;
  padding:4px 12px; border-radius:100px;
  font-size:0.73rem; font-weight:700;
  letter-spacing:0.05em; text-transform:uppercase;
}}
.badge-critical {{ background:rgba(239,68,68,0.12); color:var(--red); border:1px solid rgba(239,68,68,0.3); }}
.badge-high     {{ background:rgba(249,115,22,0.12); color:var(--orange); border:1px solid rgba(249,115,22,0.3); }}
.badge-medium   {{ background:rgba(245,158,11,0.12); color:var(--amber); border:1px solid rgba(245,158,11,0.3); }}
.badge-low      {{ background:rgba(16,185,129,0.12); color:var(--green); border:1px solid rgba(16,185,129,0.3); }}
.badge-info     {{ background:rgba(59,130,246,0.12); color:#60A5FA; border:1px solid rgba(59,130,246,0.3); }}

/* ── Section header ── */
.sec-hdr {{ display:flex; align-items:center; gap:12px; margin:24px 0 14px 0; }}
.sec-icon {{
  width:38px; height:38px; border-radius:10px;
  background: linear-gradient(135deg, var(--bg3), var(--surface));
  border:1px solid var(--border);
  display:flex; align-items:center; justify-content:center; font-size:1rem;
}}
.sec-title {{ font-family:'Cormorant Garamond',serif; font-size:1.3rem; font-weight:700; color:var(--text); margin:0; }}
.sec-sub {{ color:var(--text3); font-size:0.78rem; margin:2px 0 0 0; }}

/* ── Step items ── */
.step {{
  display:flex; align-items:flex-start; gap:14px;
  padding:14px 18px; background:var(--bg3);
  border:1px solid var(--border); border-radius:12px; margin:6px 0;
  transition: background 0.2s;
}}
.step:hover {{ background:var(--surface); }}
.step-num {{
  min-width:34px; height:34px; border-radius:50%;
  background:var(--text); color:var(--bg);
  display:flex; align-items:center; justify-content:center;
  font-weight:700; font-size:0.85rem;
}}
.step-num.urgent {{ background:var(--red); color:white; }}
.step-num.high   {{ background:var(--orange); color:white; }}
.step-t  {{ font-weight:600; color:var(--text); font-size:0.92rem; }}
.step-d  {{ color:var(--text2); font-size:0.8rem; margin-top:3px; line-height:1.5; }}

/* ── Tip items ── */
.tip {{
  display:flex; align-items:flex-start; gap:10px;
  padding:10px 14px; background:var(--bg3);
  border-left:3px solid var(--accent);
  border-radius:0 10px 10px 0; margin:5px 0;
}}
.tip-t {{ color:var(--text2); font-size:0.86rem; line-height:1.5; }}

/* ── Deadline ring ── */
.deadline-card {{
  background:var(--surface); border:1px solid var(--border);
  border-radius:16px; padding:20px; text-align:center;
}}
.deadline-num {{
  font-family:'Cormorant Garamond',serif;
  font-size:3.6rem; font-weight:800; line-height:1;
}}
.deadline-lbl {{ color:var(--text3); font-size:0.75rem; font-weight:600; letter-spacing:0.05em; text-transform:uppercase; margin-top:4px; }}

/* ── Letter paper ── */
.letter {{
  background:var(--surface); border:1px solid var(--border);
  border-radius:14px; padding:36px 40px;
  font-family:'Times New Roman',Georgia,serif;
  font-size:0.94rem; line-height:1.9;
  color:var(--text); white-space:pre-wrap;
  position:relative;
}}
.letter::before {{
  content:''; position:absolute; top:0; left:0; right:0;
  height:4px; border-radius:14px 14px 0 0;
  background:linear-gradient(90deg,var(--accent),transparent);
}}

/* ── Recommendation box ── */
.rec-box {{ border-radius:14px; padding:20px 24px; margin:12px 0; border-width:2px; border-style:solid; }}
.rec-pay   {{ background:rgba(16,185,129,0.06); border-color:rgba(16,185,129,0.3); }}
.rec-fight {{ background:rgba(239,68,68,0.06); border-color:rgba(239,68,68,0.3); }}
.rec-neg   {{ background:rgba(245,158,11,0.06); border-color:rgba(245,158,11,0.3); }}
.rec-title {{ font-family:'Cormorant Garamond',serif; font-size:1.4rem; font-weight:700; }}

/* ── Chat ── */
.chat-user {{
  background:var(--accent); color:#0A1628;
  border-radius:18px 18px 4px 18px;
  padding:12px 16px; margin:6px 0 6px 15%;
  font-size:0.9rem; line-height:1.5; font-weight:500;
}}
.chat-ai {{
  background:var(--surface); border:1px solid var(--border);
  border-radius:18px 18px 18px 4px;
  padding:12px 16px; margin:6px 15% 6px 0;
  font-size:0.9rem; line-height:1.5; color:var(--text);
}}
.chat-lbl {{ font-size:0.68rem; font-weight:700; letter-spacing:0.06em; text-transform:uppercase; margin-bottom:5px; }}

/* ── Progress bar ── */
.prog-track {{ background:var(--border); border-radius:100px; height:7px; overflow:hidden; margin:5px 0; }}
.prog-fill  {{ height:100%; border-radius:100px; background:linear-gradient(90deg,var(--accent),var(--accent2)); transition:width 0.5s; }}

/* ── Divider ── */
.gold-div {{ height:1px; background:linear-gradient(90deg,transparent,var(--accent),transparent); margin:24px 0; opacity:0.35; }}

/* ── Status pill ── */
.pill {{ display:inline-flex; align-items:center; gap:5px; padding:3px 11px; border-radius:100px; font-size:0.73rem; font-weight:600; }}
.pill-on  {{ background:rgba(16,185,129,0.15); color:var(--green); border:1px solid rgba(16,185,129,0.3); }}
.pill-off {{ background:rgba(245,158,11,0.15); color:var(--amber); border:1px solid rgba(245,158,11,0.3); }}

/* ── Flow banner (tab 5) ── */
.flow-banner {{
  background:linear-gradient(135deg,var(--bg2),var(--bg3));
  border:1px solid rgba(201,168,76,0.18);
  border-radius:16px; padding:22px 28px; margin-bottom:22px;
  display:flex; gap:0; align-items:center;
  flex-wrap:wrap; justify-content:space-between;
}}
.flow-step {{ text-align:center; flex:1; min-width:100px; }}
.flow-icon {{ font-size:1.7rem; }}
.flow-lbl  {{ color:var(--accent); font-weight:700; font-size:0.8rem; margin-top:5px; letter-spacing:0.04em; }}
.flow-sub  {{ color:var(--text3); font-size:0.72rem; margin-top:2px; }}
.flow-arrow {{ color:var(--accent); font-size:1.3rem; flex:0; padding:0 6px; }}

/* ── Buttons ── */
.stButton > button {{
  font-family: 'Outfit', sans-serif !important;
  font-weight: 600 !important;
  border-radius: 10px !important;
  transition: all 0.2s !important;
  border: none !important;
}}
.stButton > button[kind="primary"] {{
  background: linear-gradient(135deg, var(--accent), var(--accent2)) !important;
  color: #0A1628 !important;
}}
.stButton > button[kind="primary"]:hover {{
  transform: translateY(-1px) !important;
  box-shadow: 0 6px 20px rgba(201,168,76,0.35) !important;
}}
.stButton > button[kind="secondary"] {{
  background: var(--bg3) !important;
  color: var(--text2) !important;
  border: 1px solid var(--border) !important;
}}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {{
  background: var(--bg3) !important;
  border-radius: 12px !important;
  padding: 4px !important;
  border: 1px solid var(--border) !important;
  gap: 3px !important;
}}
.stTabs [data-baseweb="tab"] {{
  border-radius: 8px !important;
  font-family: 'Outfit', sans-serif !important;
  font-weight: 500 !important;
  color: var(--text2) !important;
  font-size: 0.88rem !important;
}}
.stTabs [aria-selected="true"] {{
  background: linear-gradient(135deg, var(--accent), var(--accent2)) !important;
  color: #0A1628 !important;
  font-weight: 700 !important;
}}

/* ── Metrics ── */
[data-testid="metric-container"] {{
  background: var(--surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: 14px !important;
  padding: 14px !important;
}}
[data-testid="metric-container"] label {{ color: var(--text3) !important; }}
[data-testid="metric-container"] [data-testid="stMetricValue"] {{ color: var(--text) !important; }}

/* ── Inputs ── */
.stTextInput input, .stTextArea textarea, .stSelectbox > div > div {{
  background: var(--bg3) !important;
  border: 1px solid var(--border) !important;
  color: var(--text) !important;
  border-radius: 10px !important;
}}
.stTextInput input:focus, .stTextArea textarea:focus {{
  border-color: var(--accent) !important;
  box-shadow: 0 0 0 3px rgba(201,168,76,0.15) !important;
}}

/* ── File uploader ── */
[data-testid="stFileUploadDropzone"] {{
  background: var(--bg3) !important;
  border: 2px dashed var(--border) !important;
  border-radius: 14px !important;
  transition: border-color 0.2s !important;
}}
[data-testid="stFileUploadDropzone"]:hover {{
  border-color: var(--accent) !important;
}}

/* ── Expander ── */
.streamlit-expanderHeader {{
  background: var(--bg3) !important;
  border-radius: 10px !important;
  color: var(--text) !important;
  font-weight: 600 !important;
  font-family: 'Outfit', sans-serif !important;
}}
.streamlit-expanderContent {{
  background: var(--surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: 0 0 10px 10px !important;
}}

/* ── Status widget ── */
[data-testid="stStatusWidget"] {{
  background: var(--surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: 12px !important;
}}

/* ── Scrollbar ── */
::-webkit-scrollbar {{ width:6px; height:6px; }}
::-webkit-scrollbar-track {{ background:var(--bg3); }}
::-webkit-scrollbar-thumb {{ background:var(--border); border-radius:10px; }}
::-webkit-scrollbar-thumb:hover {{ background:var(--accent); }}
</style>
""", unsafe_allow_html=True)


inject_css()

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────
def get_client():
    key = st.session_state.get("openai_key", "")
    return OpenAI(api_key=key) if key else None


def sev_badge(sev: str) -> str:
    css = {"CRITICAL":"critical","HIGH":"high","MEDIUM":"medium","LOW":"low"}.get(sev,"medium")
    icon= {"CRITICAL":"🔴","HIGH":"🟠","MEDIUM":"🟡","LOW":"🟢"}.get(sev,"🟡")
    return f'<span class="badge badge-{css}">{icon} {sev}</span>'


def gold_div():
    st.markdown('<div class="gold-div"></div>', unsafe_allow_html=True)


def sec_header(icon, title, sub=""):
    st.markdown(f"""
    <div class="sec-hdr">
      <div class="sec-icon">{icon}</div>
      <div><div class="sec-title">{title}</div>{"<div class='sec-sub'>" + sub + "</div>" if sub else ""}</div>
    </div>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(f"""
    <div style="padding:6px 0 18px 0">
      <div style="font-family:'Cormorant Garamond',serif;font-size:1.6rem;font-weight:700;color:var(--accent)">🏛️ {APP_NAME}</div>
      <div style="font-size:0.72rem;letter-spacing:0.08em;color:#64748b;margin-top:2px">NYC PROPERTY ASSISTANT  v{APP_VERSION}</div>
    </div>""", unsafe_allow_html=True)

    # ── API Key ──────────────────────────────────────────────────────────────
    st.markdown("#### 🔑 API Key")
    api_key = st.text_input("OpenAI API Key", value=st.session_state["openai_key"],
                             type="password", placeholder="sk-proj-...", label_visibility="collapsed")
    if api_key:
        ok, err = check_api_key(api_key)
        if ok:
            st.session_state["openai_key"] = api_key
            st.markdown('<span class="pill pill-on">● System Ready</span>', unsafe_allow_html=True)
        else:
            st.markdown(f'<span class="pill pill-off">⚠ {err}</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="pill pill-off">● Enter API Key</span>', unsafe_allow_html=True)

    st.divider()

    # ── Property Info ────────────────────────────────────────────────────────
    st.markdown("#### 🏢 Your Property")
    st.session_state["owner_name"]    = st.text_input("Owner / LLC Name", value=st.session_state["owner_name"],
                                                       placeholder="e.g. Smith Properties LLC", label_visibility="collapsed")
    st.session_state["property_addr"] = st.text_input("Property Address",  value=st.session_state["property_addr"],
                                                       placeholder="e.g. 123 Main St, Brooklyn", label_visibility="collapsed")

    st.divider()

    # ══════════════════════════════════════════════════════════════════════════
    # ⚙️  APPEARANCE SETTINGS
    # ══════════════════════════════════════════════════════════════════════════
    st.markdown("#### ⚙️ Appearance")

    # Theme
    theme_icons = {"dark": "🌙 Dark", "light": "☀️ Light"}
    chosen_theme = st.radio("Theme", list(theme_icons.keys()),
                             format_func=lambda x: theme_icons[x],
                             index=list(theme_icons.keys()).index(st.session_state["theme"]),
                             horizontal=True, label_visibility="collapsed")
    if chosen_theme != st.session_state["theme"]:
        st.session_state["theme"] = chosen_theme
        st.rerun()

    # Accent color
    accent_icons = {"gold":"🟡 Gold","blue":"🔵 Blue","green":"🟢 Green","rose":"🔴 Rose"}
    chosen_accent = st.selectbox("Accent Color", list(accent_icons.keys()),
                                  format_func=lambda x: accent_icons[x],
                                  index=list(accent_icons.keys()).index(st.session_state["accent"]),
                                  label_visibility="collapsed")
    if chosen_accent != st.session_state["accent"]:
        st.session_state["accent"] = chosen_accent
        st.rerun()

    # Font size
    fs_opts = {"small":"🔡 Small","medium":"🔤 Medium","large":"🔠 Large"}
    chosen_fs = st.select_slider("Font Size", options=list(fs_opts.keys()),
                                  value=st.session_state["font_size"],
                                  format_func=lambda x: fs_opts[x],
                                  label_visibility="collapsed")
    if chosen_fs != st.session_state["font_size"]:
        st.session_state["font_size"] = chosen_fs
        st.rerun()

    # Compact mode
    compact = st.toggle("Compact Mode", value=st.session_state["compact"])
    if compact != st.session_state["compact"]:
        st.session_state["compact"] = compact
        st.rerun()

    st.divider()

    # ── Quick reference ──────────────────────────────────────────────────────
    st.markdown("#### 📖 Violation Classes")
    for cls, info in VIOLATION_CLASSES.items():
        st.markdown(f"**{cls.split('(')[0].strip()}**")
        st.caption(f"⏰ {info['deadline_days']}d  |  💰 {info['fine_range']}")

    st.divider()
    st.markdown("#### 📞 NYC Help Lines")
    st.markdown("""
    <div style="font-size:0.82rem;line-height:2.1">
    🏛️ <b style="color:#c9a84c">HPD:</b> 212-863-5620<br>
    🏗️ <b style="color:#c9a84c">DOB:</b> 212-393-2550<br>
    ⚖️ <b style="color:#c9a84c">OATH:</b> 212-933-3000<br>
    📞 <b style="color:#c9a84c">311:</b> General help<br>
    🆘 <b style="color:#c9a84c">Legal Aid:</b> 212-577-3300
    </div>""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# HERO
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <div class="hero-title">NYC Property Violations,<br><span>Resolved in 60 Seconds.</span></div>
  <div class="hero-sub">Upload any HPD or DOB violation notice. Three AI agents instantly analyze it, build your action plan, generate response letters, and create legal summons — no lawyer required.</div>
  <div>
    <span class="hero-badge">🏛️ HPD Violations</span>
    <span class="hero-badge">🏗️ DOB Violations</span>
    <span class="hero-badge">⚖️ OATH Hearings</span>
    <span class="hero-badge">📝 Response Letters</span>
    <span class="hero-badge">📊 Scrape to Excel</span>
    <span class="hero-badge">⚡ Legal Summons</span>
  </div>
</div>""", unsafe_allow_html=True)

st.markdown("""
<div class="stat-grid">
  <div class="stat-card"><div class="stat-num a">60s</div><div class="stat-lbl">Full Analysis</div></div>
  <div class="stat-card"><div class="stat-num">$0</div><div class="stat-lbl">Lawyer Cost</div></div>
  <div class="stat-card"><div class="stat-num a">3</div><div class="stat-lbl">AI Agents</div></div>
  <div class="stat-card"><div class="stat-num">24/7</div><div class="stat-lbl">Available</div></div>
</div>""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# TABS
# ─────────────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "  📋  Analyze Violation  ",
    "  💬  Legal Assistant  ",
    "  📂  Case History  ",
    "  📚  NYC Law Guide  ",
    "  📊  Scrape & Summons  ",
    "  🔍  Auto Monitor  ",
])


# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 — ANALYZE VIOLATION
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    left, right = st.columns([5, 6], gap="large")

    HPD_SAMPLE = """NYC DEPARTMENT OF HOUSING PRESERVATION & DEVELOPMENT
NOTICE OF VIOLATION — CLASS C (IMMEDIATELY HAZARDOUS)
Date Issued: March 10, 2026 | Violation: HPD-2026-BK-047291
Property: 456 Bedford Avenue, Apt 4C, Brooklyn, NY 11226
Owner: Smith Properties LLC
Code: §27-2029 | LACK OF HEAT — Temp recorded 54°F at 8:45AM (required 68°F)
CLASS C — IMMEDIATELY HAZARDOUS | Deadline: 24 HOURS | Fine: $250/day
Projected 30-day fine: $7,500
Hearing: April 5, 2026 at 9:30AM — OATH, 66 John Street 10th Floor, NY 10038
Inspector: Rodriguez, Carmen  Badge: HPD-7742"""

    DOB_SAMPLE = """NYC DEPARTMENT OF BUILDINGS — STOP WORK ORDER
ECB Violation: 35-2026-MN-DOB-88291 | Date: Feb 28, 2026
Property: 347 West 45th Street Floors 3&4, New York, NY 10036
Owner: Midtown Holdings LLC
Work without permits — framing, electrical rough-in, plumbing stub-outs, structural beam removal.
ALL WORK MUST CEASE IMMEDIATELY.
Class I — Immediately Dangerous | Base Penalty: $5,000 + $1,000/day after 10 days
Hearing: March 30, 2026 | OATH/ECB 66 John Street 10th Floor
Inspector: Williams, James T. Badge #DOB-3381"""

    with left:
        sec_header("📤", "Upload Your Violation", "Photo, PDF, Word doc, or paste text")

        uploaded = st.file_uploader("Drop file here", type=["pdf","docx","txt","jpg","jpeg","png"],
                                     label_visibility="collapsed")
        if uploaded:
            fok, ferr = check_file(uploaded)
            if fok:
                st.success(f"✅ **{uploaded.name}** ready")
                if uploaded.name.lower().endswith((".jpg",".jpeg",".png")):
                    st.image(uploaded, use_column_width=True)
            else:
                st.error(f"❌ {ferr}")

        st.markdown(f'<div style="text-align:center;color:var(--text3);padding:6px 0;font-size:0.8rem">— or paste text below —</div>', unsafe_allow_html=True)
        manual = st.text_area("Paste text", placeholder="Paste violation notice text here...",
                               height=120, label_visibility="collapsed")

        run_btn = st.button("🚀  Analyze My Violation", type="primary", use_container_width=True,
                             disabled=not (uploaded or manual or st.session_state.get("auto_run_text")))

        gold_div()
        st.markdown("**📂 Load sample to test:**")
        c1, c2 = st.columns(2)
        if c1.button("🔥 HPD Class C — No Heat", use_container_width=True):
            st.session_state["auto_run_text"] = HPD_SAMPLE
            st.rerun()
        if c2.button("🏗️ DOB Stop Work Order", use_container_width=True):
            st.session_state["auto_run_text"] = DOB_SAMPLE
            st.rerun()

    with right:
        sec_header("📊", "Analysis Results", "Instant AI-powered violation breakdown")

        # ── Handle pending auto-run ─────────────────────────────────────────
        should_run = run_btn or bool(st.session_state.get("auto_run_text"))

        if should_run:
            if not st.session_state.get("openai_key"):
                st.error("❌ Enter your OpenAI API key in the sidebar first.")
                st.session_state["auto_run_text"] = None
            else:
                client = get_client()
                owner  = st.session_state.get("owner_name","Property Owner") or "Property Owner"

                with st.status("🤖 AI Agents Analyzing...", expanded=True) as status:
                    st.write("📄 Extracting text...")
                    try:
                        if st.session_state.get("auto_run_text"):
                            text = st.session_state.pop("auto_run_text")
                        elif uploaded:
                            fok, ferr = check_file(uploaded)
                            if not fok:
                                st.error(ferr); st.stop()
                            text = extract_text(uploaded, client)
                        else:
                            text = manual

                        tok, terr = check_text(text)
                        if not tok:
                            st.error(terr); st.stop()
                    except Exception as e:
                        st.error(f"❌ File error: {e}"); st.stop()

                    st.write("🔍 Agent 1 — Reading violation...")
                    try:
                        vdata = analyze_violation(text, client)
                    except Exception as e:
                        st.error(f"❌ Agent 1 error: {e}. Check your API key has credits."); st.stop()

                    sev = vdata.get("severity","HIGH")
                    st.write(f"✅ Agent 1 done — **{sev}** | {vdata.get('violation_type','Unknown')}")

                    st.write("📚 Agent 2 — Researching strategy...")
                    try:
                        rdata = build_action_plan(vdata, client)
                    except Exception as e:
                        st.error(f"❌ Agent 2 error: {e}"); st.stop()

                    rec = rdata.get("recommendation","?")
                    st.write(f"✅ Agent 2 done — Strategy: **{rec}**")

                    st.write("✍️ Agent 3 — Drafting letters...")
                    try:
                        ldata = write_letters(vdata, rdata, owner, client)
                    except Exception as e:
                        st.error(f"❌ Agent 3 error: {e}"); st.stop()

                    st.write("✅ Agent 3 done — Letters ready")
                    status.update(label="✅ Analysis Complete!", state="complete")

                st.session_state.update({"vdata": vdata, "rdata": rdata, "ldata": ldata})

                if "history" not in st.session_state:
                    st.session_state["history"] = []
                st.session_state["history"].append({
                    "date":     datetime.now().strftime("%b %d, %Y %H:%M"),
                    "type":     vdata.get("violation_type","Unknown"),
                    "agency":   vdata.get("agency","Unknown"),
                    "severity": sev,
                    "fine":     vdata.get("fine_per_day","N/A"),
                    "rec":      rec,
                    "days":     vdata.get("response_deadline_days",30),
                    "case":     vdata.get("case_number","N/A"),
                })

        # ── Show results ────────────────────────────────────────────────────
        if st.session_state.get("vdata"):
            vdata = st.session_state["vdata"]
            rdata = st.session_state["rdata"]
            ldata = st.session_state["ldata"]
            sev   = vdata.get("severity","HIGH")
            sev_css = {"CRITICAL":"critical","HIGH":"high","MEDIUM":"medium","LOW":"low"}.get(sev,"medium")

            st.markdown(f"""
            <div class="card card-{sev_css}">
              <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:12px">
                {sev_badge(sev)}
                <span class="badge badge-info">🏛️ {vdata.get('agency','?')}</span>
                <span class="badge badge-info">📋 {vdata.get('violation_class','?')}</span>
              </div>
              <div style="font-family:'Cormorant Garamond',serif;font-size:1.2rem;font-weight:700;color:var(--text);margin-bottom:10px">{vdata.get('violation_type','Violation Detected')}</div>
              <div style="background:var(--bg3);border-radius:10px;padding:12px 14px;margin-bottom:10px">
                <div style="font-size:0.72rem;font-weight:700;color:var(--text3);text-transform:uppercase;letter-spacing:0.05em;margin-bottom:5px">⚠️ What Happened</div>
                <div style="color:var(--text2);font-size:0.88rem;line-height:1.6">{vdata.get('what_happened','See analysis below.')}</div>
              </div>
              <div style="background:rgba(249,115,22,0.08);border-radius:10px;padding:12px 14px">
                <div style="font-size:0.72rem;font-weight:700;color:var(--orange);text-transform:uppercase;letter-spacing:0.05em;margin-bottom:5px">⚡ Immediate Risk</div>
                <div style="color:var(--text2);font-size:0.88rem;line-height:1.6">{vdata.get('immediate_risk','Act promptly.')}</div>
              </div>
            </div>""", unsafe_allow_html=True)

            m1, m2, m3 = st.columns(3)
            m1.metric("💰 Fine/Day", vdata.get("fine_per_day","N/A"))
            m2.metric("⏰ Days to Act", vdata.get("response_deadline_days","?"))
            m3.metric("🎯 Strategy", rdata.get("recommendation","?"))
        else:
            st.markdown("""
            <div class="card" style="text-align:center;padding:52px 28px">
              <div style="font-size:3rem;margin-bottom:14px">🏛️</div>
              <div style="font-family:'Cormorant Garamond',serif;font-size:1.2rem;color:var(--text);margin-bottom:8px">No Violation Analyzed Yet</div>
              <div style="color:var(--text3);font-size:0.88rem">Upload a notice or click a sample →</div>
            </div>""", unsafe_allow_html=True)


# ── Full Results ──────────────────────────────────────────────────────────────
with tab1:
    if st.session_state.get("vdata"):
        vdata = st.session_state["vdata"]
        rdata = st.session_state["rdata"]
        ldata = st.session_state["ldata"]

        gold_div()

        # Deadline tracker
        sec_header("⏰","Deadline Tracker","Time-sensitive — act immediately")
        days = vdata.get("response_deadline_days", 30)
        try: days_int = int(days)
        except: days_int = 30
        deadline_dt = datetime.now() + timedelta(days=days_int)
        urg_color = "var(--red)" if days_int<=3 else "var(--orange)" if days_int<=7 else "var(--amber)" if days_int<=14 else "var(--green)"

        d1,d2,d3,d4 = st.columns(4)
        with d1:
            pct = min(100, max(5, (30-days_int)/30*100))
            st.markdown(f"""<div class="deadline-card">
              <div class="deadline-num" style="color:{urg_color}">{days_int}</div>
              <div class="deadline-lbl">Days to Respond</div>
              <div class="prog-track" style="margin-top:10px"><div class="prog-fill" style="width:{pct}%"></div></div>
            </div>""", unsafe_allow_html=True)
        with d2:
            st.markdown(f"""<div class="deadline-card">
              <div style="font-family:'Cormorant Garamond',serif;font-size:1.5rem;font-weight:700;color:var(--text)">{deadline_dt.strftime('%b %d, %Y')}</div>
              <div class="deadline-lbl">Response Deadline</div>
            </div>""", unsafe_allow_html=True)
        with d3:
            st.markdown(f"""<div class="deadline-card">
              <div style="font-family:'Cormorant Garamond',serif;font-size:1.1rem;font-weight:700;color:var(--text)">{vdata.get('hearing_date','N/A')}</div>
              <div class="deadline-lbl">Hearing Date</div>
            </div>""", unsafe_allow_html=True)
        with d4:
            st.markdown(f"""<div class="deadline-card">
              <div style="font-family:'Cormorant Garamond',serif;font-size:1.2rem;font-weight:700;color:var(--red)">{vdata.get('total_potential_fine','N/A')}</div>
              <div class="deadline-lbl">Total if Ignored</div>
            </div>""", unsafe_allow_html=True)

        gold_div()

        col_a, col_b = st.columns(2, gap="large")
        with col_a:
            sec_header("✅","Action Plan","Do these steps in order")
            for s in rdata.get("action_steps", []):
                p = s.get("priority","MEDIUM")
                p_cls = "urgent" if p=="URGENT" else "high" if p=="HIGH" else ""
                p_color = {"URGENT":"var(--red)","HIGH":"var(--orange)","MEDIUM":"var(--amber)","LOW":"var(--green)"}.get(p,"var(--text3)")
                st.markdown(f"""
                <div class="step">
                  <div class="step-num {p_cls}">{s.get('step','?')}</div>
                  <div style="flex:1">
                    <div class="step-t">{s.get('action','')}</div>
                    <div class="step-d">{s.get('how_to','')}</div>
                    <div style="margin-top:6px;display:flex;gap:10px">
                      <span style="font-size:0.74rem;color:{p_color};font-weight:600">⏰ {s.get('deadline','')}</span>
                      <span style="font-size:0.74rem;color:var(--text3)">💰 {s.get('cost_estimate','$0')}</span>
                    </div>
                  </div>
                </div>""", unsafe_allow_html=True)

            docs = rdata.get("documents_to_gather",[])
            if docs:
                sec_header("📎","Documents to Gather","")
                for d in docs:
                    st.markdown(f'<div class="tip"><span>📄</span><span class="tip-t">{d}</span></div>', unsafe_allow_html=True)

        with col_b:
            rec = rdata.get("recommendation","?")
            rec_css = {"PAY":"rec-pay","FIGHT":"rec-fight","NEGOTIATE":"rec-neg","FIX_AND_CERTIFY":"rec-pay"}.get(rec,"rec-neg")
            rec_icon = {"PAY":"💳","FIGHT":"⚔️","NEGOTIATE":"🤝","FIX_AND_CERTIFY":"🔧"}.get(rec,"⚖️")
            rec_color = {"PAY":"var(--green)","FIGHT":"var(--red)","NEGOTIATE":"var(--amber)","FIX_AND_CERTIFY":"var(--green)"}.get(rec,"var(--text)")

            sec_header("🎯","Recommended Strategy","Based on NYC court outcomes")
            st.markdown(f"""
            <div class="rec-box {rec_css}">
              <div class="rec-title" style="color:{rec_color}">{rec_icon} {rec}</div>
              <p style="color:var(--text2);margin:8px 0 6px;font-size:0.88rem">{rdata.get('recommendation_reason','')}</p>
              <div style="font-size:0.78rem;color:var(--text3)">📊 Appeal rate: <b>{vdata.get('appeal_success_rate','N/A')}</b></div>
            </div>""", unsafe_allow_html=True)

            tips = rdata.get("fine_reduction_strategies",[])
            if tips:
                sec_header("💡","Fine Reduction Tips","Proven strategies in NYC")
                for tip in tips:
                    st.markdown(f'<div class="tip"><span>💡</span><span class="tip-t">{tip}</span></div>', unsafe_allow_html=True)

            defenses = rdata.get("landlord_defenses",[])
            if defenses:
                sec_header("🛡️","Legal Defenses","Arguments that win in NYC court")
                for d in defenses:
                    st.markdown(f'<div class="tip"><span>⚖️</span><span class="tip-t">{d}</span></div>', unsafe_allow_html=True)

        gold_div()
        sec_header("📝","Response Letters","Professional, ready to print and send")

        lt1, lt2 = st.tabs(["  📄  Response Letter  ", "  ⚔️  Appeal Letter  "])
        with lt1:
            letter = ldata.get("response_letter","")
            if letter:
                st.markdown(f'<div class="letter">{letter}</div>', unsafe_allow_html=True)
                cl1, cl2 = st.columns(2)
                cl1.download_button("⬇️ Download Letter", letter,
                    file_name="response_letter.txt", mime="text/plain", use_container_width=True)
                send = ldata.get("send_to_address","")
                if send:
                    st.markdown(f"""<div class="card card-low" style="margin-top:10px">
                      <b>📮 Send to:</b> {send}
                      {"<br><span style='color:var(--text3);font-size:0.82rem'>Method: " + ldata.get('send_method','') + "</span>" if ldata.get('send_method') else ""}
                    </div>""", unsafe_allow_html=True)
        with lt2:
            appeal = ldata.get("appeal_letter","")
            if appeal:
                st.markdown(f'<div class="letter">{appeal}</div>', unsafe_allow_html=True)
                st.download_button("⬇️ Download Appeal", appeal,
                    file_name="appeal_letter.txt", mime="text/plain", use_container_width=True)
                for arg in ldata.get("key_arguments",[]):
                    st.markdown(f'<div class="tip"><span>⚖️</span><span class="tip-t">{arg}</span></div>', unsafe_allow_html=True)

        cert = ldata.get("correction_certificate_notes","")
        if cert:
            with st.expander("📜 How to File Certificate of Correction"):
                st.markdown(cert)

        res = rdata.get("free_resources",[])
        if res:
            gold_div()
            st.markdown("### 📞 Free Resources")
            cols = st.columns(min(len(res),3))
            for i, r in enumerate(res[:3]):
                cols[i%3].markdown(f'<div class="card" style="padding:12px 16px;font-size:0.84rem;color:var(--text2)">{r}</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 — LEGAL CHAT
# ══════════════════════════════════════════════════════════════════════════════
with tab2:
    sec_header("💬","Legal Assistant","Ask anything about NYC property law")

    if "chat" not in st.session_state:
        st.session_state["chat"] = []

    # ── Handle pending question from last rerun ───────────────────────────────
    if st.session_state.get("pending_q"):
        q = st.session_state.pop("pending_q")
        client = get_client()
        if client:
            ctx = ""
            if st.session_state.get("vdata"):
                vd = st.session_state["vdata"]
                rd = st.session_state.get("rdata", {})
                ctx = (f"\nActive violation: {vd.get('violation_type')} | "
                       f"{vd.get('agency')} | Fine: {vd.get('fine_per_day')} | "
                       f"Strategy: {rd.get('recommendation','?')}")
            sys = {"role":"system","content":(
                "You are a senior NYC property law expert helping landlords.\n"
                "Give direct, actionable answers citing specific NYC codes.\n"
                "Mention deadlines and consequences clearly.\n"
                "Recommend consulting a licensed attorney for court matters.\n"
                + ctx
            )}
            msgs = [sys] + st.session_state["chat"][-8:]
            try:
                with st.spinner("⚖️ Researching NYC law..."):
                    r = client.chat.completions.create(model="gpt-4o", messages=msgs,
                                                       temperature=0.2, max_tokens=800, timeout=30)
                    st.session_state["chat"].append({"role":"assistant","content":r.choices[0].message.content})
            except Exception as e:
                st.session_state["chat"].append({"role":"assistant","content":f"Error: {e}. Check your API key."})

    # ── Suggestion buttons ────────────────────────────────────────────────────
    if not st.session_state["chat"]:
        st.markdown("#### 💡 Quick Questions:")
        suggestions = [
            "How do I respond to an HPD Class C violation?",
            "What are my rights when tenant refuses access?",
            "How can I reduce my DOB fine at OATH?",
            "What happens if I miss the hearing date?",
            "How do I file a Certificate of Correction?",
            "Can I evict during open violations?",
        ]
        cols = st.columns(2)
        for i, s in enumerate(suggestions):
            if cols[i%2].button(s, key=f"sq_{i}", use_container_width=True):
                st.session_state["chat"].append({"role":"user","content":s})
                st.session_state["pending_q"] = s
                st.rerun()

    # ── Messages ──────────────────────────────────────────────────────────────
    for msg in st.session_state["chat"]:
        if msg["role"] == "user":
            st.markdown(f"""<div class="chat-user">
              <div class="chat-lbl" style="color:rgba(10,22,40,0.6)">You</div>
              {msg['content']}
            </div>""", unsafe_allow_html=True)
        else:
            st.markdown(f"""<div class="chat-ai">
              <div class="chat-lbl" style="color:var(--accent)">🏛️ LandlordAI</div>
              {msg['content'].replace(chr(10),'<br>')}
            </div>""", unsafe_allow_html=True)

    # ── Input ─────────────────────────────────────────────────────────────────
    question = st.chat_input("Ask your NYC property law question...")
    if question:
        if not st.session_state.get("openai_key"):
            st.error("❌ Enter API key in sidebar")
        else:
            st.session_state["chat"].append({"role":"user","content":question})
            st.session_state["pending_q"] = question
            st.rerun()

    if st.session_state["chat"]:
        if st.button("🗑️ Clear chat", type="secondary"):
            st.session_state["chat"] = []
            st.session_state["pending_q"] = None
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# TAB 3 — CASE HISTORY
# ══════════════════════════════════════════════════════════════════════════════
with tab3:
    sec_header("📂","Case History","All violations analyzed this session")

    history = st.session_state.get("history", [])
    if history:
        m1, m2, m3 = st.columns(3)
        m1.metric("📋 Total Cases", len(history))
        m2.metric("🔴 Critical", sum(1 for h in history if h["severity"]=="CRITICAL"))
        m3.metric("⚔️ Fight Recommended", sum(1 for h in history if h["rec"]=="FIGHT"))
        gold_div()
        for entry in reversed(history):
            sev = entry.get("severity","HIGH")
            sev_css = {"CRITICAL":"critical","HIGH":"high","MEDIUM":"medium","LOW":"low"}.get(sev,"medium")
            rec = entry.get("rec","?")
            rec_color = {"PAY":"var(--green)","FIGHT":"var(--red)","NEGOTIATE":"var(--amber)","FIX_AND_CERTIFY":"var(--green)"}.get(rec,"var(--text3)")
            st.markdown(f"""
            <div class="card card-{sev_css}">
              <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:8px">
                <div>
                  <div style="display:flex;gap:7px;flex-wrap:wrap;margin-bottom:7px">
                    {sev_badge(sev)}
                    <span class="badge badge-info">{entry.get('agency','?')}</span>
                    <span style="color:{rec_color};font-weight:700;font-size:0.8rem;padding:4px 12px;background:var(--bg3);border-radius:100px">→ {rec}</span>
                  </div>
                  <div style="font-family:'Cormorant Garamond',serif;font-size:1.1rem;font-weight:700;color:var(--text)">{entry.get('type','?')}</div>
                  <div style="color:var(--text3);font-size:0.78rem;margin-top:3px">
                    Case: {entry.get('case','?')} &nbsp;|&nbsp; Fine: {entry.get('fine','?')} &nbsp;|&nbsp; {entry.get('days','?')} days
                  </div>
                </div>
                <div style="color:var(--text3);font-size:0.74rem">{entry.get('date','')}</div>
              </div>
            </div>""", unsafe_allow_html=True)
    else:
        st.markdown("""<div class="card" style="text-align:center;padding:52px">
          <div style="font-size:2.5rem;margin-bottom:12px">📂</div>
          <div style="font-family:'Cormorant Garamond',serif;font-size:1.1rem;color:var(--text)">No Cases Yet</div>
          <div style="color:var(--text3);font-size:0.88rem;margin-top:6px">Analyze a violation in Tab 1 to see history here.</div>
        </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 — NYC LAW GUIDE
# ══════════════════════════════════════════════════════════════════════════════
with tab4:
    sec_header("📚","NYC Property Law Guide","Quick reference for landlords")
    g1, g2 = st.columns(2, gap="large")

    with g1:
        st.markdown("#### 🏛️ Violation Classes")
        for cls, info in VIOLATION_CLASSES.items():
            st.markdown(f"""
            <div class="card card-{info['severity']}" style="padding:14px 18px;margin:6px 0">
              <div style="font-weight:600;color:var(--text);font-size:0.92rem">{cls}</div>
              <div style="color:var(--text2);font-size:0.8rem;margin:4px 0">{info['description']}</div>
              <div style="display:flex;gap:14px;margin-top:6px">
                <span style="font-size:0.78rem;color:{info['color']};font-weight:600">⏰ {info['deadline_days']} day(s)</span>
                <span style="font-size:0.78rem;color:var(--text3)">💰 {info['fine_range']}</span>
              </div>
            </div>""", unsafe_allow_html=True)

        st.markdown("#### 💰 Fine Reduction Playbook")
        for title, tip in FINE_REDUCTION_TIPS:
            st.markdown(f'<div class="tip"><span>💡</span><div><b style="color:var(--text)">{title}</b><br><span class="tip-t">{tip}</span></div></div>', unsafe_allow_html=True)

    with g2:
        st.markdown("#### 🏗️ NYC Agencies")
        for code, name, desc, phone in NYC_AGENCIES:
            st.markdown(f"""
            <div class="card" style="padding:14px 18px;margin:6px 0">
              <div style="display:flex;justify-content:space-between;align-items:flex-start">
                <div>
                  <span class="badge badge-info" style="margin-bottom:6px;display:inline-block">{code}</span>
                  <div style="font-weight:600;color:var(--text);font-size:0.88rem">{name}</div>
                  <div style="color:var(--text3);font-size:0.78rem;margin-top:2px">{desc}</div>
                </div>
                <div style="color:var(--text3);font-size:0.76rem;white-space:nowrap">📞 {phone}</div>
              </div>
            </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 5 — SCRAPE & SUMMONS
# ══════════════════════════════════════════════════════════════════════════════
with tab5:
    sec_header("📊","Scrape & Summons","Upload any file → AI extracts all data → Excel database → Legal summons PDFs")

    st.markdown("""
    <div class="flow-banner">
      <div class="flow-step"><div class="flow-icon">📄</div><div class="flow-lbl">UPLOAD</div><div class="flow-sub">Any file type</div></div>
      <div class="flow-arrow">→</div>
      <div class="flow-step"><div class="flow-icon">🤖</div><div class="flow-lbl">AI SCRAPES</div><div class="flow-sub">All key data</div></div>
      <div class="flow-arrow">→</div>
      <div class="flow-step"><div class="flow-icon">📊</div><div class="flow-lbl">EXCEL DB</div><div class="flow-sub">Running database</div></div>
      <div class="flow-arrow">→</div>
      <div class="flow-step"><div class="flow-icon">⚖️</div><div class="flow-lbl">SUMMONS</div><div class="flow-sub">Ready to serve</div></div>
    </div>""", unsafe_allow_html=True)

    col_up, col_db = st.columns([1,1], gap="large")

    with col_up:
        sec_header("📤","Upload & Scrape","Upload any property document")

        ss_file = st.file_uploader("Upload document", type=["pdf","docx","txt","jpg","jpeg","png"],
                                    key="ss_up", label_visibility="collapsed")
        if ss_file:
            fok, ferr = check_file(ss_file)
            if fok:
                st.success(f"✅ **{ss_file.name}**")
                if ss_file.name.lower().endswith((".jpg",".jpeg",".png")):
                    st.image(ss_file, use_column_width=True)
            else:
                st.error(f"❌ {ferr}")

        scrape_btn = st.button("🔍  Scrape All Data", type="primary",
                                use_container_width=True, disabled=not ss_file)

        if scrape_btn:
            if not st.session_state.get("openai_key"):
                st.error("❌ Enter API key in sidebar.")
            else:
                fok, ferr = check_file(ss_file)
                if not fok:
                    st.error(ferr)
                else:
                    client = get_client()
                    with st.status("🤖 Scraping...", expanded=True) as status:
                        st.write("📄 Extracting text...")
                        try:
                            text = extract_text(ss_file, client)
                            tok, terr = check_text(text)
                            if not tok:
                                st.error(terr); st.stop()
                        except Exception as e:
                            st.error(f"❌ {e}"); st.stop()

                        st.write("🧠 AI extracting all fields...")
                        try:
                            scraped = scrape_document(text, client)
                        except Exception as e:
                            st.error(f"❌ AI error: {e}"); st.stop()

                        scraped["source_filename"] = ss_file.name
                        st.session_state["scraped_db"].append(scraped)
                        st.session_state["last_scraped"] = scraped
                        status.update(label="✅ Done!", state="complete")

        if st.session_state.get("last_scraped"):
            rec = st.session_state["last_scraped"]
            urg = rec.get("urgency","MEDIUM")
            urg_css = {"CRITICAL":"critical","HIGH":"high","MEDIUM":"medium","LOW":"low"}.get(urg,"medium")
            sa = rec.get("summons_applicable") in [True,"true","True"]

            gold_div()
            st.markdown("##### Last Scraped:")
            st.markdown(f"""
            <div class="card card-{urg_css}">
              <div style="display:flex;gap:7px;flex-wrap:wrap;margin-bottom:10px">
                {sev_badge(urg)}
                <span class="badge badge-info">{rec.get('document_type','Doc')}</span>
                {"<span class='badge badge-critical'>⚖️ Summons</span>" if sa else ""}
              </div>
              <div style="font-family:'Cormorant Garamond',serif;font-size:1.1rem;font-weight:700;color:var(--text);margin-bottom:8px">
                {rec.get('tenant_name','Unknown')} — Unit {rec.get('tenant_unit','')}
              </div>
              <div style="color:var(--text2);font-size:0.84rem;line-height:1.8">
                📍 {rec.get('tenant_address','')} {rec.get('tenant_city','')}<br>
                💰 Overdue: <b>${rec.get('total_overdue','0') or rec.get('amount_owed','0')}</b><br>
                📋 {rec.get('issue_summary','')}
              </div>
              <div style="margin-top:10px;padding:10px 14px;background:var(--bg3);border-radius:8px;font-size:0.82rem;color:var(--text2)">
                <b>→ Next Step:</b> {rec.get('recommended_action','')}
              </div>
            </div>""", unsafe_allow_html=True)

            with st.expander("🔎 All extracted fields"):
                fields = {
                    "👤 Tenant": rec.get("tenant_name"), "🏠 Unit": rec.get("tenant_unit"),
                    "📍 Address": rec.get("tenant_address"), "📧 Email": rec.get("tenant_email"),
                    "📞 Phone": rec.get("tenant_phone"), "🏢 Landlord": rec.get("landlord_name"),
                    "📋 Case #": rec.get("case_number"), "🏛️ Agency": rec.get("agency"),
                    "⚖️ Violation": rec.get("violation_type"), "💰 Amount": rec.get("amount_owed"),
                    "🗓️ Deadline": rec.get("deadline_date"), "📅 Hearing": rec.get("hearing_date"),
                    "📄 Summons Type": rec.get("summons_type"),
                }
                for k, v in fields.items():
                    if v and v not in ["null","N/A","None"]:
                        st.markdown(f"**{k}:** {v}")

    with col_db:
        sec_header("🗃️","Case Database","Every upload adds a row")

        db = st.session_state["scraped_db"]
        if db:
            total_owed = 0
            for r in db:
                try: total_owed += float(str(r.get("total_overdue") or r.get("amount_owed") or "0").replace(",","").replace("$","") or 0)
                except: pass

            m1,m2,m3,m4 = st.columns(4)
            m1.metric("📁 Cases", len(db))
            m2.metric("🔴 Critical", sum(1 for r in db if r.get("urgency")=="CRITICAL"))
            m3.metric("⚖️ Summons", sum(1 for r in db if r.get("summons_applicable") in [True,"true","True"]))
            m4.metric("💰 Total", f"${total_owed:,.0f}")

            gold_div()

            for rec in reversed(db):
                urg = rec.get("urgency","MEDIUM")
                urg_css = {"CRITICAL":"critical","HIGH":"high","MEDIUM":"medium","LOW":"low"}.get(urg,"medium")
                sa = rec.get("summons_applicable") in [True,"true","True"]
                st.markdown(f"""
                <div class="card card-{urg_css}" style="padding:12px 16px;margin:5px 0">
                  <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:6px">
                    <div>
                      <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:5px">
                        {sev_badge(urg)}
                        {"<span class='badge badge-critical'>⚖️</span>" if sa else ""}
                      </div>
                      <div style="font-weight:600;color:var(--text);font-size:0.9rem">{rec.get('tenant_name','?')} — {rec.get('tenant_unit','')}</div>
                      <div style="color:var(--text3);font-size:0.76rem;margin-top:2px">💰 ${rec.get('total_overdue','0') or rec.get('amount_owed','0')} | 🗓️ {rec.get('deadline_date','N/A')} | 📄 {rec.get('source_filename','')}</div>
                    </div>
                    <div style="color:var(--text3);font-size:0.72rem">{rec.get('extracted_date','')}</div>
                  </div>
                </div>""", unsafe_allow_html=True)

            gold_div()
            st.markdown("#### 📥 Export & Generate")

            # Download Excel
            try:
                excel_bytes = build_excel(db)
                st.download_button(
                    "📊  Download Full Excel Database",
                    data=excel_bytes,
                    file_name=f"LandlordAI_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True, type="primary",
                )
            except Exception as e:
                st.error(f"Excel error: {e}")

            # Summons generation
            summons_recs = [r for r in db if r.get("summons_applicable") in [True,"true","True"]]
            if summons_recs:
                st.markdown(f"**⚖️ {len(summons_recs)} record(s) ready for summons:**")
                doc_type = st.selectbox("Select document type:", SUMMONS_TYPES, key="ss_dtype")

                if st.button(f"⚖️  Generate {len(summons_recs)} Summons PDFs → ZIP",
                              type="primary", use_container_width=True,
                              disabled=not st.session_state.get("openai_key")):
                    client = get_client()
                    owner  = st.session_state.get("owner_name","Property Owner") or "Property Owner"
                    zip_buf = io.BytesIO()
                    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
                        prog = st.progress(0, text="Generating PDFs...")
                        for idx, rec in enumerate(summons_recs):
                            name_s = sanitize_filename(rec.get("tenant_name","tenant"))
                            unit_s = sanitize_filename(str(rec.get("tenant_unit","")))
                            fname  = f"{name_s}_{unit_s}_{doc_type.replace(' ','_')[:30]}.pdf"
                            try:
                                letter_text = generate_summons_text(rec, doc_type, owner, client)
                                pdf_bytes   = build_pdf(letter_text, doc_type, rec.get("tenant_name",""))
                                zf.writestr(fname, pdf_bytes)
                            except Exception as e:
                                zf.writestr(fname.replace(".pdf",".txt"), f"Error: {e}")
                            prog.progress((idx+1)/len(summons_recs), text=f"Generated {idx+1}/{len(summons_recs)}")

                        try:
                            zf.writestr(f"LandlordAI_Database_{datetime.now().strftime('%Y%m%d')}.xlsx", build_excel(db))
                        except Exception:
                            pass

                    st.download_button(
                        f"⬇️  Download ZIP — {len(summons_recs)} PDFs + Excel",
                        data=zip_buf.getvalue(),
                        file_name=f"LandlordAI_Summons_{datetime.now().strftime('%Y%m%d_%H%M')}.zip",
                        mime="application/zip", use_container_width=True,
                    )
                    st.success(f"✅ {len(summons_recs)} summons generated!")

            if st.button("🗑️ Clear database", type="secondary"):
                st.session_state["scraped_db"] = []
                st.session_state["last_scraped"] = None
                st.rerun()
        else:
            st.markdown("""<div class="card" style="text-align:center;padding:52px 28px">
              <div style="font-size:3rem;margin-bottom:14px">📂</div>
              <div style="font-family:'Cormorant Garamond',serif;font-size:1.15rem;color:var(--text);margin-bottom:8px">No Cases Yet</div>
              <div style="color:var(--text3);font-size:0.88rem;line-height:1.8">
                Upload any document on the left.<br>
                Each upload adds one row to your database.<br>
                Upload 10 files → get 10 rows + 10 summons PDFs.
              </div>
            </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# TAB 6 — AUTO MONITOR (Fixed)
# ══════════════════════════════════════════════════════════════════════════════
with tab6:
    sec_header("🔍", "Auto Monitor", "Enter building addresses → AI checks NYC HPD database → auto-analyzes any open violations")

    st.markdown("""
    <div class="flow-banner">
      <div class="flow-step"><div class="flow-icon">🏢</div><div class="flow-lbl">YOUR ADDRESS</div><div class="flow-sub">Enter once</div></div>
      <div class="flow-arrow">→</div>
      <div class="flow-step"><div class="flow-icon">🌐</div><div class="flow-lbl">NYC DATABASE</div><div class="flow-sub">Live HPD API</div></div>
      <div class="flow-arrow">→</div>
      <div class="flow-step"><div class="flow-icon">🤖</div><div class="flow-lbl">4 AI AGENTS</div><div class="flow-sub">Auto-analyze</div></div>
      <div class="flow-arrow">→</div>
      <div class="flow-step"><div class="flow-icon">📋</div><div class="flow-lbl">FULL REPORT</div><div class="flow-sub">Action plan ready</div></div>
    </div>""", unsafe_allow_html=True)

    # ── How to format addresses ───────────────────────────────────────────────
    with st.expander("📖 How to enter addresses for best results"):
        st.markdown("""
        **Format:** `[House Number] [Street Name] [Borough]`

        ✅ **Works well:**
        - `22 Stagg Street Brooklyn`
        - `1780 Grand Concourse Bronx`
        - `430 Clarkson Avenue Brooklyn`
        - `2302 Third Avenue Bronx`

        ⚠️ **Tips:**
        - Borough name at the end helps narrow results
        - Spelling must match NYC records (use full street name)
        - The app searches NYC's live HPD violation database
        - Only **OPEN** violations are shown (closed ones are skipped)
        """)

    # ── Session state ─────────────────────────────────────────────────────────
    if "monitored_addresses" not in st.session_state:
        st.session_state["monitored_addresses"] = []
    if "monitor_results" not in st.session_state:
        st.session_state["monitor_results"] = {}

    col_add, col_res = st.columns([1, 1], gap="large")

    # ── LEFT: Add addresses ───────────────────────────────────────────────────
    with col_add:
        sec_header("🏢", "Your Properties", "Add all your building addresses")

        new_addr = st.text_input(
            "Address", placeholder="e.g. 22 Stagg Street Brooklyn",
            label_visibility="collapsed", key="t6_addr_input"
        )

        add_btn = st.button("➕  Add Address", type="primary",
                             use_container_width=True,
                             disabled=not new_addr.strip())

        if add_btn and new_addr.strip():
            if new_addr.strip() not in st.session_state["monitored_addresses"]:
                st.session_state["monitored_addresses"].append(new_addr.strip())
                st.rerun()
            else:
                st.warning("Already in your list.")

        addrs = st.session_state["monitored_addresses"]

        if addrs:
            gold_div()
            st.markdown(f"**{len(addrs)} address(es) monitored:**")

            for i, addr in enumerate(addrs):
                res = st.session_state["monitor_results"]
                if addr in res:
                    found = len(res[addr])
                    icon  = "🔴" if found > 0 else "✅"
                    status_txt = f"{icon} {found} violation(s) found" if found > 0 else "✅ Clean"
                else:
                    status_txt = "⏳ Pending check"

                c1, c2 = st.columns([5, 1])
                c1.markdown(f"""
                <div class="card" style="padding:10px 14px;margin:4px 0">
                  <div style="font-size:0.88rem;font-weight:600;color:var(--text)">{addr}</div>
                  <div style="font-size:0.75rem;color:var(--text3);margin-top:2px">{status_txt}</div>
                </div>""", unsafe_allow_html=True)
                if c2.button("🗑️", key=f"t6_del_{i}"):
                    st.session_state["monitored_addresses"].pop(i)
                    st.session_state["monitor_results"].pop(addr, None)
                    st.rerun()

            gold_div()

            if not st.session_state.get("openai_key"):
                st.warning("⚠️ Enter your OpenAI API key in the sidebar first.")
            else:
                check_btn = st.button("🔍  Check All Addresses Now",
                                       type="primary", use_container_width=True)

                if check_btn:
                    client = get_client()
                    new_results = dict(st.session_state["monitor_results"])

                    with st.status("🌐 Checking NYC HPD database...", expanded=True) as s:

                        for addr in addrs:

                            st.write(f"🔍 Searching: **{addr}**")
                            try:
                                raw_violations = fetch_violations_from_api(addr)
                            except RuntimeError as e:
                                st.error(f"❌ {e}")
                                new_results[addr] = []
                                continue

                            open_violations = [v for v in raw_violations
                                               if v.get("violationstatus","").lower() == "open"]

                            if not open_violations:
                                st.write(f"✅ **{addr}** — No open violations found")
                                new_results[addr] = []
                                continue

                            # Store raw only — no AI here, keep it fast
                            analyzed = [{"raw": v} for v in open_violations[:10]]
                            new_results[addr] = analyzed
                            st.write(f"⚠️ **{addr}** — {len(analyzed)} open violation(s) found")

                        st.session_state["monitor_results"] = new_results
                        s.update(label="✅ Done! Click 🤖 Deep Analyze on any violation.", state="complete")

                    # ============================================================
                    # IMPROVED: NYC HPD Database Check with Performance & Error Handling
                    # ============================================================
                    
                    # Configuration constants for maintainability
                    MAX_VIOLATIONS_PER_ADDRESS = 5
                    MAX_CONCURRENT_REQUESTS = 3
                    API_RETRY_ATTEMPTS = 3
                    API_RETRY_DELAY = 1.0  # seconds
                    
                    def fetch_violations_with_retry(address: str, max_retries: int = API_RETRY_ATTEMPTS) -> list:
                        """
                        Fetch violations from API with retry logic for resilience.
                        
                        Args:
                            address: The property address to check
                            max_retries: Number of retry attempts on failure
                            
                        Returns:
                            List of violation records from the API
                            
                        Raises:
                            RuntimeError: If all retry attempts fail
                        """
                        import time
                        
                        last_error = None
                        for attempt in range(1, max_retries + 1):
                            try:
                                return fetch_violations_from_api(address)
                            except RuntimeError as e:
                                last_error = e
                                if attempt < max_retries:
                                    time.sleep(API_RETRY_DELAY)
                                continue
                        
                        # All retries exhausted
                        raise RuntimeError(f"Failed after {max_retries} attempts: {last_error}")
                    
                    def filter_open_violations(violations: list) -> list:
                        """
                        Filter violations to only include open ones (case-insensitive).
                        
                        Args:
                            violations: Raw list of violation records
                            
                        Returns:
                            Filtered list containing only open violations
                        """
                        return [
                            v for v in violations
                            if v.get("violationstatus", "").lower() == "open"
                        ]
                    
                    def analyze_single_violation(violation: dict, client) -> dict:
                        """
                        Analyze a single violation with AI agents.
                        
                        Args:
                            violation: The violation record to analyze
                            client: OpenAI client instance
                            
                        Returns:
                            Dictionary with analysis results or error info
                        """
                        try:
                            v_text = format_violation_text(violation)
                            vdata = analyze_violation(v_text, client)
                            rdata = build_action_plan(vdata, client)
                            
                            # Add to Case History tab (side effect, but needed for UI)
                            if "history" not in st.session_state:
                                st.session_state["history"] = []
                            
                            st.session_state["history"].append({
                                "date":     datetime.now().strftime("%b %d, %Y %H:%M"),
                                "type":     vdata.get("violation_type", violation.get("novdescription", "Unknown")[:60]),
                                "agency":   "HPD",
                                "severity": vdata.get("severity", "HIGH"),
                                "fine":     vdata.get("fine_per_day", "N/A"),
                                "rec":      rdata.get("recommendation", "?"),
                                "days":     vdata.get("response_deadline_days", 30),
                                "case":     vdata.get("case_number", violation.get("violationid", "N/A")),
                            })
                            
                            return {
                                "raw":    violation,
                                "vdata":  vdata,
                                "rdata":  rdata,
                            }
                        except Exception as e:
                            return {
                                "raw":   violation,
                                "error": str(e),
                            }
                    
                    def process_single_address(address: str, client) -> tuple:
                        """
                        Process a single address: fetch violations and analyze them.
                        
                        This function is designed to be called in parallel for performance.
                        
                        Args:
                            address: The property address to process
                            client: OpenAI client instance
                            
                        Returns:
                            Tuple of (address, analyzed_results)
                        """
                        # Step 1: Fetch violations with retry logic
                        try:
                            raw_violations = fetch_violations_with_retry(address)
                        except RuntimeError as e:
                            return (address, {"error": str(e), "violations": []})
                        
                        # Step 2: Filter for open violations only
                        open_violations = filter_open_violations(raw_violations)
                        
                        if not open_violations:
                            return (address, {"violations": [], "count": 0})
                        
                        # Step 3: Limit violations to process (performance optimization)
                        violations_to_analyze = open_violations[:MAX_VIOLATIONS_PER_ADDRESS]
                        
                        # Step 4: Analyze each violation with AI
                        analyzed = []
                        for violation in violations_to_analyze:
                            result = analyze_single_violation(violation, client)
                            analyzed.append(result)
                        
                        return (address, {"violations": analyzed, "count": len(analyzed)})
                    
                    # Main execution with progress tracking
                    with st.status("🌐 Checking NYC HPD database...", expanded=True) as status:
                        from concurrent.futures import ThreadPoolExecutor, as_completed
                        
                        # Progress tracking
                        total_addresses = len(addrs)
                        completed = 0
                        
                        # Use thread pool for concurrent API calls (performance optimization)
                        # This significantly speeds up checking multiple addresses
                        with ThreadPoolExecutor(max_workers=MAX_CONCURRENT_REQUESTS) as executor:
                            # Submit all address processing tasks
                            future_to_address = {
                                executor.submit(process_single_address, addr, client): addr
                                for addr in addrs
                            }
                            
                            # Process results as they complete
                            for future in as_completed(future_to_address):
                                addr = future_to_address[future]
                                completed += 1
                                
                                try:
                                    address, result = future.result()
                                    
                                    # Handle API errors
                                    if "error" in result:
                                        st.error(f"❌ {addr}: {result['error']}")
                                        new_results[addr] = []
                                        continue
                                    
                                    # No open violations found
                                    if result["count"] == 0:
                                        st.write(f"✅ **{addr}** — No open violations found")
                                        new_results[addr] = []
                                        continue
                                    
                                    # Violations found - store analysis
                                    new_results[addr] = result["violations"]
                                    st.write(
                                        f"⚠️ **{addr}** — {result['count']} violation(s) analyzed"
                                    )
                                    
                                except Exception as e:
                                    st.error(f"❌ {addr}: Unexpected error - {str(e)}")
                                    new_results[addr] = []
                                
                                # Update progress
                                status.update(
                                    label=f"🔄 Progress: {completed}/{total_addresses} addresses checked",
                                    state="running"
                                )
                    
                    # Persist results to session state
                    st.session_state["monitor_results"] = new_results
                    status.update(
                        label="✅ All addresses checked! Click 🤖 Deep Analyze on any violation.",
                        state="complete"
                    )

        else:
            st.markdown("""
            <div class="card" style="text-align:center;padding:40px 20px">
              <div style="font-size:2.5rem;margin-bottom:12px">🏢</div>
              <div style="font-family:'Cormorant Garamond',serif;font-size:1.1rem;color:var(--text);margin-bottom:6px">No Addresses Yet</div>
              <div style="color:var(--text3);font-size:0.85rem">Add a building address above to start monitoring.</div>
            </div>""", unsafe_allow_html=True)

    # ── RIGHT: Results ────────────────────────────────────────────────────────
    with col_res:
        sec_header("📊", "Monitor Results", "Live AI analysis of open violations")

        results = st.session_state.get("monitor_results", {})

        if results:
            total_v   = sum(len(v) for v in results.values())
            total_crit = 0
            for addr_res in results.values():
                for item in addr_res:
                    if isinstance(item, dict) and item.get("vdata",{}).get("severity") == "CRITICAL":
                        total_crit += 1

            m1, m2, m3 = st.columns(3)
            m1.metric("🏢 Addresses", len(results))
            m2.metric("⚠️ Open Violations", total_v)
            # m3.metric("🔴 Critical", total_crit)
            gold_div()

            for addr, addr_results in results.items():
                for item in addr_results:
                    raw = item.get("raw", {})
                    cls = raw.get("class","?")
                    cls_css = {"C":"critical","B":"high","A":"low"}.get(cls,"high")
                    vid = raw.get("violationid","x")

                    st.markdown(f"""
    <div class="card card-{cls_css}" style="margin:6px 0">
      <div style="display:flex;gap:7px;flex-wrap:wrap;margin-bottom:8px">
        <span class="badge badge-{'red' if cls=='C' else 'amber' if cls=='B' else 'info'}">
          Class {cls} {'🔴 CRITICAL' if cls=='C' else '🟠 HAZARDOUS' if cls=='B' else '🟡 NON-HAZARDOUS'}
        </span>
        <span class="badge badge-info">ID: {vid}</span>
      </div>
      <div style="font-weight:700;color:var(--text);margin-bottom:8px;font-size:0.9rem">
        {raw.get('novdescription','?')[:120]}
      </div>
      <div style="color:var(--text2);font-size:0.81rem;line-height:1.9">
        🏠 Apt <b>{raw.get('apartment','?')}</b> &nbsp;|&nbsp;
        🏗️ Floor <b>{raw.get('story','?')}</b><br>
        📅 Issued: <b>{raw.get('novissueddate','?')[:10] if raw.get('novissueddate') else 'N/A'}</b> &nbsp;|&nbsp;
        ⏰ Correct By: <b>{raw.get('originalcorrectbydate','?')[:10] if raw.get('originalcorrectbydate') else 'N/A'}</b><br>
        🚦 Status: <b style="color:var(--red)">{raw.get('currentstatus','?')}</b>
      </div>
    </div>""", unsafe_allow_html=True)

                    if st.button(f"🤖 Deep Analyze + Get Action Plan",
                                  key=f"t6_analyze_{vid}",
                                  type="primary",
                                  use_container_width=True):
                        client = get_client()
                        with st.spinner("🤖 Running AI agents..."):
                            try:
                                v_text = format_violation_text(raw)
                                vdata  = analyze_violation(v_text, client)
                                rdata  = build_action_plan(vdata, client)
                                st.session_state["vdata"] = vdata
                                st.session_state["rdata"] = rdata
                                st.session_state["ldata"] = {}
                                if "history" not in st.session_state:
                                    st.session_state["history"] = []
                                st.session_state["history"].append({
                                    "date":     datetime.now().strftime("%b %d, %Y %H:%M"),
                                    "type":     vdata.get("violation_type", raw.get("novdescription","?")[:60]),
                                    "agency":   "HPD",
                                    "severity": vdata.get("severity","HIGH"),
                                    "fine":     vdata.get("fine_per_day","N/A"),
                                    "rec":      rdata.get("recommendation","?"),
                                    "days":     vdata.get("response_deadline_days", 30),
                                    "case":     raw.get("violationid","N/A"),
                                })
                                st.success("✅ Done! Go to Tab 1 for full report + letters.")
                            except Exception as e:
                                st.error(f"AI error: {e}")


            if st.button("🗑️  Clear all results", type="secondary"):
                st.session_state["monitor_results"] = {}
                st.rerun()

        else:
            st.markdown("""
            <div class="card" style="text-align:center;padding:52px 28px">
              <div style="font-size:3rem;margin-bottom:14px">🔍</div>
              <div style="font-family:'Cormorant Garamond',serif;font-size:1.15rem;
                          color:var(--text);margin-bottom:8px">No Results Yet</div>
              <div style="color:var(--text3);font-size:0.88rem;line-height:1.8">
                Add your addresses on the left,<br>
                then click "Check All Addresses Now".<br>
                AI agents will auto-analyze any open violations found.
              </div>
            </div>""", unsafe_allow_html=True)
