import base64
import json
from contextlib import contextmanager
from pathlib import Path
from html import escape
import streamlit as st
from docx_letter import build_cover_letter_docx

st.set_page_config(page_title="ResumeForce AI", page_icon="icon.png", layout="wide")

try:
    import main as engine
except RuntimeError as error:  # e.g. missing OLLAMA_API_KEY
    st.error(str(error))
    st.stop()

def load_css(name="style.css"):
    """All spacing, colors and fonts live in style.css (settings are at the top of that file)."""
    try:
        css = (Path(__file__).parent / name).read_text(encoding="utf-8")
    except OSError:
        st.warning(f"{name} was not found. Put it in the same folder as ui.py.")
        return
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


@contextmanager
def card():
    """A bordered box. The marker lets style.css pad and space it."""
    with st.container(border=True):
        st.markdown('<div class="card-marker"></div>', unsafe_allow_html=True)
        yield


load_css()


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


def h(value) -> str:
    return escape(txt(value)).replace("$", "&#36;")


def tone(value: int) -> str:
    if value >= 70:
        return "var(--good)"
    return "var(--mid)" if value >= 50 else "var(--bad)"


def chips(items, kind=""):
    items = [txt(i) for i in as_list(items) if txt(i)]
    if not items:
        st.caption("Nothing to show.")
        return
    st.markdown("".join(f'<span class="chip {kind}">{h(i)}</span>' for i in items), unsafe_allow_html=True)


def notes(items, kind="info"):
    html = "".join(f'<div class="note {kind}">{h(i)}</div>' for i in as_list(items) if txt(i))
    if html:
        st.markdown(f'<div class="notes">{html}</div>', unsafe_allow_html=True)


def bullets(items):
    lines = [f"- {md(i)}" for i in as_list(items) if txt(i)]
    if lines:
        st.markdown("\n".join(lines))
    else:
        st.caption("Nothing to show.")


def score_card(column, label, value):
    value = score(value)
    with column:
        st.markdown(
            f'<div class="card score-card" style="--p:{value};--c:{tone(value)}">'
            f'<div class="ring"><b>{value}</b></div>'
            f'<div><div class="card-label">{h(label)}</div><div class="card-band">{band(value)}</div></div></div>',
            unsafe_allow_html=True,
        )


def title_line(*parts):
    return " · ".join(md(p) for p in parts if txt(p))


def gather(entries, key):
    seen, items = set(), []
    for entry in entries:
        for item in as_list(entry.get(key)):
            text = txt(item)
            if text and text.lower() not in seen:
                seen.add(text.lower())
                items.append(text)
    return items


def show_online_presence(links):
    links = links if isinstance(links, dict) else {}
    entries = [e for e in as_list(links.get("links")) if isinstance(e, dict)]
    checked = [e for e in entries if any(as_list(e.get(k)) for k in ("strengths", "concerns", "skills_shown"))]
    if not checked:
        return

    st.subheader("Online presence")
    if txt(links.get("overall")):
        st.markdown(md(links["overall"]))

    strengths, concerns = gather(checked, "strengths"), gather(checked, "concerns")
    left, right = st.columns(2)
    with left:
        st.caption("Backed up by your links")
        bullets(strengths)
    with right:
        st.caption("Concerns from your links")
        bullets(concerns)

    skills = gather(checked, "skills_shown")
    if skills:
        st.caption("Skills seen on your links")
        chips(skills, "soft")


def show_overview(report: dict, links=None):
    c1, c2, c3 = st.columns(3)
    score_card(c1, "Overall score", report.get("overall_score"))
    score_card(c2, "ATS readiness", report.get("ats_score"))
    with c3:
        st.markdown(
            '<div class="card stat-card">'
            f'<div class="stat-value">{h(txt(report.get("career_level")).title() or "—")}</div>'
            '<div class="card-label">Career level</div>'
            '<div class="stat-note">Estimated from your resume</div></div>',
            unsafe_allow_html=True,
        )

    if txt(report.get("summary")):
        st.markdown(f'<div class="lede">{h(report["summary"])}</div>', unsafe_allow_html=True)

    sections = report.get("section_scores") or {}
    if isinstance(sections, dict) and sections:
        st.subheader("Section scores")
        rows = "".join(
            f'<div class="bar-row"><span class="bar-name">{h(name.replace("_", " ").title())}</span>'
            f'<div class="bar"><i style="width:{score(value)}%;background:{tone(score(value))}"></i></div>'
            f'<span class="bar-num">{score(value)}</span></div>'
            for name, value in sections.items()
        )
        st.markdown(f'<div class="card bars">{rows}</div>', unsafe_allow_html=True)

    left, right = st.columns(2, gap="large")
    with left:
        st.subheader("Strengths")
        notes(as_list(report.get("strengths")), "good")
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
                notes([item], "warn")

    red_flags = as_list(report.get("red_flags"))
    if red_flags:
        st.subheader("Red flags")
        notes(red_flags, "bad")

    show_online_presence(links)

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
    with card():
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
        with card():
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
        with card():
            st.markdown(f"**{md(project.get('name'))}**")
            compare_block(original.get("bullets"), project.get("bullets"), compare)

    todo = as_list(better.get("add_these_yourself"))
    if todo:
        st.subheader("Details only you can add")
        st.caption("These need real facts from you, so they were not invented.")
        for item in todo:
            if isinstance(item, dict):
                notes([f"{txt(item.get('section')).title()}: {txt(item.get('suggestion'))}"], "info")
            else:
                notes([item], "info")


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
        with card():
            st.markdown(f"**{title_line(job.get('role'), job.get('company'))}**")
            dates = " – ".join(txt(job.get(k)) for k in ("start_date", "end_date") if txt(job.get(k)))
            st.caption(title_line(dates, job.get("location")))
            bullets(job.get("bullets"))

    st.subheader("Projects")
    for project in as_list(structured.get("projects")):
        if not isinstance(project, dict):
            continue
        with card():
            st.markdown(f"**{md(project.get('name'))}**")
            if txt(project.get("link")):
                st.caption(project["link"])
            chips(project.get("tech_stack"), "soft")
            bullets(project.get("bullets"))

    st.subheader("Education")
    for edu in as_list(structured.get("education")):
        if not isinstance(edu, dict):
            continue
        with card():
            st.markdown(f"**{title_line(edu.get('degree'), edu.get('field'))}**")
            years = " – ".join(txt(edu.get(k)) for k in ("start_year", "end_year") if txt(edu.get(k)))
            st.caption(title_line(edu.get("institution"), years, edu.get("grade")))

    for key, label in (("certifications", "Certifications"), ("achievements", "Achievements"),
                       ("languages", "Languages")):
        items = as_list(structured.get(key))
        if items:
            st.subheader(label)
            bullets(items)


def letter_to_text(letter: dict, fallback_name: str = "") -> str:
    parts = [txt(letter.get("greeting"))]
    parts += [txt(p) for p in as_list(letter.get("paragraphs")) if txt(p)]
    parts.append(txt(letter.get("sign_off")) or fallback_name)
    return "\n\n".join(p for p in parts if p)


def show_cover_letter(letter: dict, structured: dict, jd=None):
    jd = jd if isinstance(jd, dict) else {}

    if txt(letter.get("subject")):
        st.caption(f"Subject: {txt(letter['subject'])}")

    text = letter_to_text(letter, txt(structured.get("name")))
    edited = st.text_area("Edit before you use it", value=text, height=100, key="letter_text")
    st.caption("After editing, press Ctrl+Enter (or click outside the box) before downloading.")

    b1, b2, _ = st.columns([1, 3, 2])
    b1.download_button(
        "Download as .txt",
        data=edited,
        file_name="cover_letter.txt",
        mime="text/plain",
    )

    try:
        docx_bytes = build_cover_letter_docx(
            edited,
            name=txt(structured.get("name")),
            email=txt(structured.get("email")),
            phone=txt(structured.get("phone")),
            location=txt(structured.get("location")),
            links=[txt(l) for l in as_list(structured.get("links")) if txt(l)],
            subject=txt(letter.get("subject")),
            company=txt(jd.get("company")),
        )
        b2.download_button(
            "Download as .docx",
            data=docx_bytes,
            file_name="cover_letter.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            type="primary",
        )
    except Exception as error:
        b2.caption(f"Word export unavailable: {error}")

    todo = as_list(letter.get("add_these_yourself"))
    if todo:
        st.subheader("Make it stronger")
        st.caption("These need real facts from you, so they were not invented.")
        for item in todo:
            notes([item], "info")


def show_job_match(report: dict, jd: dict):
    match = report.get("job_match")
    match = match if isinstance(match, dict) else {}

    title = title_line(jd.get("job_title"), jd.get("company"))
    if title:
        st.markdown(f"**Target role:** {title}")

    c1, c2 = st.columns([1, 2], vertical_alignment="center")
    score_card(c1, "Job match", match.get("match_score"))
    with c2:
        st.markdown(md(match.get("fit_summary")) or "_No summary generated._")

    left, right = st.columns(2)
    with left:
        st.subheader("Matched skills")
        chips(match.get("matched_skills"))
    with right:
        st.subheader("Missing required skills")
        chips(match.get("missing_required_skills"), "warn")

    nice = as_list(match.get("missing_nice_to_have"))
    if nice:
        st.subheader("Missing nice-to-have")
        chips(nice, "soft")

    gaps = as_list(match.get("experience_gaps"))
    if gaps:
        st.subheader("Experience gaps")
        bullets(gaps)


RESEARCH_TOPICS = [
    ("technical", "Technical"),
    ("projects", "Projects"),
    ("behavioral", "Behavioral"),
    ("hr", "HR"),
    ("company", "About the company"),
]


def safe_link(label, url) -> str:
    label, url = txt(label), txt(url)
    if not url.lower().startswith(("http://", "https://")):
        return md(label or url)
    label = (label or url).replace("[", "(").replace("]", ")")
    url = url.replace(" ", "%20").replace(")", "%29")
    return f"[{md(label)}]({url})"


def show_company_profile(research: dict):
    profile = research.get("profile")
    profile = profile if isinstance(profile, dict) else {}

    if not profile or profile.get("found_enough") is False:
        st.info("Not enough public information was found to describe this company in detail.")

    if txt(profile.get("what_they_do")):
        st.markdown(md(profile["what_they_do"]))

    left, right = st.columns(2)
    with left:
        if as_list(profile.get("products")):
            st.subheader("Products")
            bullets(profile.get("products"))
        if as_list(profile.get("culture_and_values")):
            st.subheader("Culture and values")
            bullets(profile.get("culture_and_values"))
    with right:
        if as_list(profile.get("tech_stack")):
            st.subheader("Tech stack")
            chips(profile.get("tech_stack"), "soft")
        if as_list(profile.get("hiring_focus")):
            st.subheader("What they look for")
            bullets(profile.get("hiring_focus"))

    news = [n for n in as_list(research.get("news")) if isinstance(n, dict) and txt(n.get("url"))]
    if news:
        st.subheader("Recent news")
        st.markdown("\n".join(f"- {safe_link(n.get('title'), n.get('url'))}" for n in news[:5]))


def show_research_questions(research: dict):
    items = [q for q in as_list(research.get("questions")) if isinstance(q, dict)]
    company = txt(research.get("company"))

    if research.get("question_type") == "reported":
        st.caption(
            f"Questions candidates reported from real {md(company)} interviews. Answers are written from your resume.")
    elif company:
        st.caption(f"No interview reports were found for {md(company)}, so these are trending questions for the role.")
    else:
        st.caption("No company was given, so these are trending questions for the role.")

    number = 0
    for key, label in RESEARCH_TOPICS:
        group = [q for q in items if q.get("category") == key]
        if not group:
            continue
        st.subheader(f"{label} ({len(group)})")
        for item in group:
            number += 1
            with st.expander(f"{number}. {md(item.get('question'))}"):
                st.markdown(md(item.get("answer")) or "_No answer generated._")
                if txt(item.get("source")):
                    st.caption("Source: " + safe_link(item.get("source_title") or "page", item.get("source")))


def show_likely_questions(research: dict):
    items = [q for q in as_list(research.get("likely")) if isinstance(q, dict)]
    st.caption("These are predictions from the company, the job and your resume. They were not reported as asked.")
    for number, item in enumerate(items, 1):
        with st.expander(f"{number}. {md(item.get('question'))}"):
            if txt(item.get("why")):
                st.markdown(f"**Why it may come up:** {md(item['why'])}")
            st.markdown(md(item.get("answer")) or "_No answer generated._")


def show_resume_links(links: dict):
    links = links if isinstance(links, dict) else {}

    if txt(links.get("overall")):
        st.markdown(md(links["overall"]))

    for entry in as_list(links.get("links")):
        if not isinstance(entry, dict):
            continue
        with card():
            st.markdown(f"**{safe_link(entry.get('url'), entry.get('url'))}**")
            if txt(entry.get("summary")):
                st.markdown(md(entry["summary"]))
            good, bad = st.columns(2)
            with good:
                if as_list(entry.get("strengths")):
                    st.caption("Strengths")
                    bullets(entry.get("strengths"))
            with bad:
                if as_list(entry.get("concerns")):
                    st.caption("Concerns")
                    bullets(entry.get("concerns"))
            if as_list(entry.get("skills_shown")):
                st.caption("Skills shown")
                chips(entry.get("skills_shown"), "soft")

    suggestions = as_list(links.get("suggestions"))
    if suggestions:
        st.subheader("Suggested fixes")
        bullets(suggestions)


def show_research(research: dict):
    head = title_line(research.get("company"), research.get("role"))
    if head:
        st.markdown(f"**Researched:** {head}")
    if txt(research.get("website")):
        st.caption("Website: " + safe_link(research["website"], research["website"]))

    for problem in as_list(research.get("problems")):
        st.warning(md(problem))

    has_profile = isinstance(research.get("profile"), dict) and research["profile"]
    questions_label = "Reported questions" if research.get("question_type") == "reported" else "Trending questions"
    links = research.get("resume_links")
    has_links = isinstance(links, dict) and as_list(links.get("links"))

    parts = {}
    if has_profile or as_list(research.get("news")):
        parts["Company"] = lambda: show_company_profile(research)
    if as_list(research.get("questions")):
        parts[questions_label] = lambda: show_research_questions(research)
    if as_list(research.get("likely")):
        parts["Likely questions"] = lambda: show_likely_questions(research)
    if has_links:
        parts["Your links"] = lambda: show_resume_links(links)

    if parts:
        for tab, render in zip(st.tabs(list(parts)), parts.values()):
            with tab:
                render()
    else:
        st.info("Deep research did not find anything to show.")

    sources = [s for s in as_list(research.get("sources")) if isinstance(s, dict) and txt(s.get("url"))]
    if sources:
        with st.expander(f"Pages read for questions ({len(sources)})"):
            st.markdown("\n".join(f"- {safe_link(s.get('title') or s.get('url'), s.get('url'))}" for s in sources))


def logo_html() -> str:
    try:
        with open("icon.png", "rb") as f:
            return f'<img src="data:image/png;base64,{base64.b64encode(f.read()).decode()}" alt="">'
    except OSError:
        return ""


st.markdown(
    f'<div class="topbar">{logo_html()}<span>ResumeForce AI</span></div>'
    '<h1 class="hero-title">Know how your resume reads before a recruiter does.</h1>'
    '<div class="tagline">Upload a resume. Get scores, sharper wording and interview prep.</div>',
    unsafe_allow_html=True,
)

with st.form("inputs"):
    left, right = st.columns([5, 6], gap="large")
    with left:
        st.markdown(
            "<div class='field-title'>Resume</div>"
            "<div class='field-hint'>Text-based PDFs only. Scanned images can't be read.</div>",
            unsafe_allow_html=True,
        )
        upload = st.file_uploader("Resume", type=["pdf"], label_visibility="collapsed")
        st.markdown("<div class='field-title'>Interview questions per topic</div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        c3, c4 = st.columns(2)
        tech = c1.number_input("Technical", 0, 20, 3)
        project = c2.number_input("Projects", 0, 20, 2)
        behavioral = c3.number_input("Behavioral", 0, 20, 2)
        hr = c4.number_input("HR", 0, 20, 2)
    with right:
        st.markdown(
            "<div class='field-title'>Job description</div>"
            "<div class='field-hint'>Optional. Paste the posting to tailor the match score, rewrites and questions.</div>",
            unsafe_allow_html=True,
        )
        jd_text = st.text_area(
            "Job description (optional)",
            label_visibility="collapsed",
            height=330,
            placeholder="Paste the job posting to tailor the review, rewrites and interview prep.",
            help="Optional. Tailors the match score, rewrites and interview questions to this role.",
        )

    o1, o2 = st.columns(2, gap="large")
    with o1:
        with card():
            want_letter = st.toggle("Generate cover letter", value=False)
            st.caption("Written from your resume. Add a job description to tailor it.")
    with o2:
        with card():
            deep_research = st.toggle("Deep research", value=False)
            st.caption("Searches the web for the company, reported questions and your resume links. Adds a minute or more.")
    company = st.text_input(
        "Company name or website (used by Deep research)",
        placeholder="e.g. Infosys or https://www.infosys.com",
        max_chars=100,
        help=(
            "Optional. Leave empty to use the company from your job description. "
            "With no company at all, research falls back to trending questions for your role."
        ),
    )

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
                    jd_text=jd_text,
                    cover_letter=want_letter,
                    company=company.strip() or None,
                    deep_research=deep_research,
                )
            except Exception as error:
                box.update(label="Analysis failed", state="error", expanded=True)
                st.error(f"{error}")
            else:
                box.update(label="Analysis complete", state="complete", expanded=False)
                st.session_state.pop("letter_text", None)
                st.session_state["result"] = {"file": upload.name, **result}

result = st.session_state.get("result")

if result:
    st.divider()
    head, action = st.columns([3, 1], vertical_alignment="center")
    head.markdown(
        '<div class="result-head"><span class="result-title">Results for</span>'
        f'<span class="file-pill">{h(result["file"])}</span></div>',
        unsafe_allow_html=True,
    )
    action.download_button(
        "Download JSON",
        data=json.dumps(
            {k: v for k, v in result.items() if k != "file"}, indent=2, ensure_ascii=False
        ),
        file_name="resumeforce_report.json",
        mime="application/json",
    )

    if result.get("jd_error"):
        st.warning(f"{result['jd_error']} Showing a general review instead.")

    if result.get("cover_letter_error"):
        st.warning(f"Cover letter could not be generated: {result['cover_letter_error']}")

    if result.get("research_error"):
        st.warning(f"Deep research could not be completed: {result['research_error']}")

    if result.get("links_error"):
        st.warning(result["links_error"])

    sections = {"Overview": lambda: show_overview(result["report"], result.get("resume_links"))}
    if result.get("jd"):
        sections["Job match"] = lambda: show_job_match(result["report"], result["jd"])
    sections["Improvements"] = lambda: show_improvements(result["better"], result["structured"])
    sections["Interview prep"] = lambda: show_questions(result["questions"])
    if result.get("research"):
        sections["Company research"] = lambda: show_research(result["research"])
    sections["Parsed resume"] = lambda: show_resume(result["structured"])

    if result.get("cover_letter"):
        sections["Cover letter"] = lambda: show_cover_letter(
            result["cover_letter"], result["structured"], result.get("jd")
        )

    for tab, render in zip(st.tabs(list(sections)), sections.values()):
        with tab:
            render()