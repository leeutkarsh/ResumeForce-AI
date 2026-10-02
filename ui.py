import base64
import json
from html import escape
import streamlit as st

st.set_page_config(page_title="ResumeForce AI", page_icon="icon.png", layout="centered")

try:
    import main as engine
except RuntimeError as error:  # e.g. missing OLLAMA_API_KEY
    st.error(str(error))
    st.stop()

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@500;700;800&display=swap');

    :root { --accent: #0d9488; }

    .block-container { max-width: 940px; padding-top: 3rem; padding-bottom: 4rem; }
    #MainMenu, footer { visibility: hidden; }

    h1, h2, h3, .brand { font-family: 'Manrope', sans-serif !important; letter-spacing: -0.02em; }
    .brand { font-size: 2.6rem; font-weight: 800; line-height: 1.1; margin: 0; }
    .tagline { opacity: .65; font-size: 1.05rem; margin: .35rem 0 1.75rem 0; }

    .chip {
        display: inline-block; padding: .18rem .75rem; margin: .15rem .3rem .15rem 0;
        border-radius: 999px; font-size: .85rem;
        background: rgba(13, 148, 136, .12); border: 1px solid rgba(13, 148, 136, .35);
    }
    .chip.warn { background: rgba(220, 38, 38, .09); border-color: rgba(220, 38, 38, .35); }
    .chip.soft { background: rgba(128, 128, 128, .12); border-color: rgba(128, 128, 128, .3); }

    button[kind="primaryFormSubmit"], button[data-testid="stBaseButton-primaryFormSubmit"] {
        background: var(--accent); border-color: var(--accent); color: #fff;
    }
    button[kind="primaryFormSubmit"]:hover, button[data-testid="stBaseButton-primaryFormSubmit"]:hover {
        background: #0f766e; border-color: #0f766e; color: #fff;
    }
    div[data-testid="stProgress"] > div > div > div > div { background-color: var(--accent); }
    
    .brand-row { display: flex; align-items: center; gap: .5rem; }
    .brand-row img { border-radius: 10px; }
    </style>
    """,
    unsafe_allow_html=True,
)

def as_list(value):
    if isinstance(value, list):
        return value
    return [] if value in (None, "") else [value]

def txt(value) -> str:
    return "" if value is None else str(value).strip()

def md(value) -> str:
    return txt(value).replace("$", "\\$")

def score(value) -> int:
    try:
        return max(0, min(int(float(value)), 100))
    except (TypeError, ValueError):
        return 0


def band(value: int) -> str:
    if value >= 90:
        return "Exceptional"
    if value >= 70:
        return "Good"
    if value >= 50:
        return "Average"
    return "Weak"


def chips(items, kind=""):
    items = [txt(i) for i in as_list(items) if txt(i)]
    if not items:
        st.caption("Nothing to show.")
        return
    html = "".join(f'<span class="chip {kind}">{escape(i)}</span>' for i in items)
    st.markdown(html, unsafe_allow_html=True)


def bullets(items):
    lines = [f"- {md(i)}" for i in as_list(items) if txt(i)]
    if lines:
        st.markdown("\n".join(lines))
    else:
        st.caption("Nothing to show.")


def score_card(column, label, value):
    value = score(value)
    with column:
        with st.container(border=True):
            st.metric(label, f"{value}/100")
            st.progress(value / 100)
            st.caption(band(value))


def title_line(*parts):
    return " · ".join(md(p) for p in parts if txt(p))


def show_overview(report: dict):
    overall, ats = report.get("overall_score"), report.get("ats_score")
    c1, c2, c3 = st.columns(3)
    score_card(c1, "Overall", overall)
    score_card(c2, "ATS readiness", ats)
    with c3:
        with st.container(border=True):
            st.metric("Career level", txt(report.get("career_level")).title() or "—")
            st.caption("Estimated from your resume")

    if txt(report.get("summary")):
        st.markdown(md(report["summary"]))

    sections = report.get("section_scores") or {}
    if isinstance(sections, dict) and sections:
        st.subheader("Section scores")
        columns = st.columns(len(sections))
        for column, (name, value) in zip(columns, sections.items()):
            with column:
                st.metric(name.replace("_", " ").title(), score(value))
                st.progress(score(value) / 100)

    left, right = st.columns(2)
    with left:
        st.subheader("Strengths")
        for item in as_list(report.get("strengths")):
            st.success(md(item), icon="✅")
    with right:
        st.subheader("To improve")
        weaknesses = as_list(report.get("weaknesses"))
        if not weaknesses:
            st.caption("Nothing to show.")
        for item in weaknesses:
            if isinstance(item, dict):
                label = title_line(item.get("section", "").title(), item.get("issue"))
                with st.expander(label or "Issue"):
                    st.markdown(md(item.get("why_it_matters")))
            else:
                st.warning(md(item))

    red_flags = as_list(report.get("red_flags"))
    if red_flags:
        st.subheader("Red flags")
        for item in red_flags:
            st.error(md(item), icon="🚩")

    st.subheader("Suggested roles")
    chips(report.get("suggested_roles"))

    st.subheader("Missing keywords")
    chips(report.get("missing_keywords"), "warn")

    missing = as_list(report.get("missing_sections"))
    if missing:
        st.subheader("Missing sections")
        chips(missing, "soft")


def compare_block(original, improved, compare: bool):
    if compare:
        left, right = st.columns(2)
        with left:
            st.caption("Original")
            bullets(original)
        with right:
            st.caption("Improved")
            bullets(improved)
    else:
        bullets(improved)


def show_improvements(better: dict, structured: dict):
    st.subheader("Priority actions")
    actions = [md(a) for a in as_list(better.get("priority_actions")) if txt(a)]
    if actions:
        st.markdown("\n".join(f"{n}. {a}" for n, a in enumerate(actions, 1)))
    else:
        st.caption("Nothing to show.")

    st.subheader("Summary")
    with st.container(border=True):
        st.markdown(md(better.get("improved_summary")) or "_No summary generated._")

    st.subheader("Skills")
    chips(better.get("improved_skills"))

    compare = st.toggle("Compare with original wording")

    original_jobs = as_list(structured.get("experience"))
    st.subheader("Experience")
    jobs = as_list(better.get("improved_experience"))
    if not jobs:
        st.caption("Nothing to show.")
    for i, job in enumerate(jobs):
        job = job if isinstance(job, dict) else {}
        original = original_jobs[i] if i < len(original_jobs) and isinstance(original_jobs[i], dict) else {}
        with st.container(border=True):
            st.markdown(f"**{title_line(job.get('role'), job.get('company'))}**")
            compare_block(original.get("bullets"), job.get("bullets"), compare)

    original_projects = as_list(structured.get("projects"))
    st.subheader("Projects")
    projects = as_list(better.get("improved_projects"))
    if not projects:
        st.caption("Nothing to show.")
    for i, project in enumerate(projects):
        project = project if isinstance(project, dict) else {}
        original = original_projects[i] if i < len(original_projects) and isinstance(original_projects[i], dict) else {}
        with st.container(border=True):
            st.markdown(f"**{md(project.get('name'))}**")
            compare_block(original.get("bullets"), project.get("bullets"), compare)

    todo = as_list(better.get("add_these_yourself"))
    if todo:
        st.subheader("Details only you can add")
        st.caption("These need real facts from you, so they were not invented.")
        for item in todo:
            if isinstance(item, dict):
                st.info(f"**{md(item.get('section')).title()}** — {md(item.get('suggestion'))}", icon="✍️")
            else:
                st.info(md(item), icon="✍️")


def show_questions(questions: dict):
    topics = [
        ("technical", "Technical"),
        ("projects", "Projects"),
        ("behavioral", "Behavioral"),
        ("hr", "HR"),
    ]
    shown = False

    st.caption("Try answering before you open the model answer.")
    for key, label in topics:
        items = [q for q in as_list(questions.get(key)) if isinstance(q, dict)]
        if not items:
            continue
        shown = True
        st.subheader(f"{label} ({len(items)})")
        for n, item in enumerate(items, 1):
            with st.expander(f"{n}. {md(item.get('question'))}"):
                st.markdown(md(item.get("answer")))

    if not shown:
        st.info("No interview questions were requested. Set a count above 0 and analyse again.")


def show_resume(structured: dict):
    st.header(txt(structured.get("name")) or "Parsed resume")
    contact = [txt(structured.get(k)) for k in ("email", "phone", "location")]
    st.caption("  ·  ".join(c for c in contact if c))

    links = [txt(link) for link in as_list(structured.get("links")) if txt(link)]
    if links:
        st.markdown("  ".join(f"[{escape(link)}]({link})" for link in links))

    if txt(structured.get("summary")):
        st.markdown(md(structured["summary"]))

    st.subheader("Skills")
    chips(structured.get("skills"))

    st.subheader("Experience")
    for job in as_list(structured.get("experience")):
        if not isinstance(job, dict):
            continue
        with st.container(border=True):
            st.markdown(f"**{title_line(job.get('role'), job.get('company'))}**")
            dates = " – ".join(txt(job.get(k)) for k in ("start_date", "end_date") if txt(job.get(k)))
            st.caption(title_line(dates, job.get("location")))
            bullets(job.get("bullets"))

    st.subheader("Projects")
    for project in as_list(structured.get("projects")):
        if not isinstance(project, dict):
            continue
        with st.container(border=True):
            st.markdown(f"**{md(project.get('name'))}**")
            if txt(project.get("link")):
                st.caption(project["link"])
            chips(project.get("tech_stack"), "soft")
            bullets(project.get("bullets"))

    st.subheader("Education")
    for edu in as_list(structured.get("education")):
        if not isinstance(edu, dict):
            continue
        with st.container(border=True):
            st.markdown(f"**{title_line(edu.get('degree'), edu.get('field'))}**")
            years = " – ".join(txt(edu.get(k)) for k in ("start_year", "end_year") if txt(edu.get(k)))
            st.caption(title_line(edu.get("institution"), years, edu.get("grade")))

    for key, label in (("certifications", "Certifications"), ("achievements", "Achievements"), ("languages", "Languages")):
        items = as_list(structured.get(key))
        if items:
            st.subheader(label)
            bullets(items)

ICON = "icon.png"
with open(ICON, "rb") as f:
    logo_b64 = base64.b64encode(f.read()).decode()

st.markdown(
    f"""
    <div class="brand-row">
        <img src="data:image/png;base64,{logo_b64}" width="26">
        <p class="brand">ResumeForce AI</p>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown(
    '<p class="tagline">Upload a resume. Get scores, sharper wording and interview prep.</p>',
    unsafe_allow_html=True,
)

with st.form("inputs"):
    upload = st.file_uploader("Resume", type=["pdf"], help="Text-based PDFs only. Scanned images can't be read.")

    st.markdown("**Interview questions per topic**")
    c1, c2, c3, c4 = st.columns(4)
    tech = c1.number_input("Technical", 0, 20, 3)
    project = c2.number_input("Projects", 0, 20, 2)
    behavioral = c3.number_input("Behavioral", 0, 20, 2)
    hr = c4.number_input("HR", 0, 20, 2)

    submitted = st.form_submit_button("Analyse resume", type="primary")

if submitted:
    if upload is None:
        st.warning("Upload a PDF resume first.")
    else:
        with st.status("Starting…", expanded=True) as box:
            icons = {"running": "⏳", "done": "✅", "failed": "❌"}

            def on_change(current):
                box.update(label=current["process"])
                box.write(f"{icons.get(current['state'], '•')} {current['process']}")

            try:
                result = engine.run(
                    upload.getvalue(),
                    tech=int(tech),
                    project=int(project),
                    behavioral=int(behavioral),
                    hr=int(hr),
                    on_change=on_change,
                )
            except Exception as error:
                box.update(label="Analysis failed", state="error", expanded=True)
                st.error(f"{error}")
            else:
                box.update(label="Analysis complete", state="complete", expanded=False)
                st.session_state["result"] = {"file": upload.name, **result}

result = st.session_state.get("result")

if result:
    st.divider()
    head, action = st.columns([3, 1], vertical_alignment="center")
    head.markdown(f"### Results for `{result['file']}`")
    action.download_button(
        "Download JSON",
        data=json.dumps(
            {k: v for k, v in result.items() if k != "file"}, indent=2, ensure_ascii=False
        ),
        file_name="resumeforce_report.json",
        mime="application/json",
    )

    overview, improvements, interview, parsed = st.tabs(
        ["Overview", "Improvements", "Interview prep", "Parsed resume"]
    )
    with overview:
        show_overview(result["report"])
    with improvements:
        show_improvements(result["better"], result["structured"])
    with interview:
        show_questions(result["questions"])
    with parsed:
        show_resume(result["structured"])
