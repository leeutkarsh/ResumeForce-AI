from concurrent.futures import ThreadPoolExecutor
from agent import research_company
from agent_llm import summarise_resume_links
from extractor import extract_resume_text
from LLM import llm
from prompts import improve, insight, interview, structure, parse_jd, write_cover_letter
from status import Status
from tools import read_resume_links

EMPTY_QUESTIONS = {"technical": [], "projects": [], "behavioral": [], "hr": []}
MAX_JD_CHARS = 6000


def _try(prompt):
    try:
        return llm(prompt), None
    except Exception as error:
        return None, str(error)


def analyse(structured, tech=1, project=1, behavioral=1, hr=1, jd=None, want_letter=False, links=None):
    """Run insight, improvement, interview and (optionally) cover letter in parallel."""
    wants_questions = any(count > 0 for count in (tech, project, behavioral, hr))

    prompts = [insight(structured, jd, links), improve(structured, jd, links)]
    if wants_questions:
        prompts.append(interview(structured, tech, behavioral, hr, project, jd))

    with ThreadPoolExecutor(max_workers=len(prompts) + 1) as pool:
        letter_future = (
            pool.submit(_try, write_cover_letter(structured, jd)) if want_letter else None
        )
        results = list(pool.map(llm, prompts))  # these still fail the run, as before
        letter, letter_error = letter_future.result() if letter_future else (None, None)

    report, better = results[0], results[1]
    questions = results[2] if wants_questions else dict(EMPTY_QUESTIONS)

    return report, better, questions, letter, letter_error


def _structure_all(text, jd_text):
    if not jd_text:
        return llm(structure(text)), None, None

    with ThreadPoolExecutor(max_workers=2) as pool:
        resume_future = pool.submit(llm, structure(text))
        jd_future = pool.submit(llm, parse_jd(jd_text))

        structured = resume_future.result()  # resume failure still fails the run
        try:
            return structured, jd_future.result(), None
        except Exception as error:
            return structured, None, f"Job description could not be read: {error}"


def _read_links(text):
    try:
        return read_resume_links(text), None
    except Exception as error:
        return [], f"Resume links could not be read: {error}"


def _check_links(pages, structured):
    if not pages:
        return None, None
    try:
        return summarise_resume_links(pages, structured), None
    except Exception as error:
        return None, f"Resume link check failed: {error}"


def _research(structured, company, jd, status, links):
    try:
        research = research_company(
            structured,
            company=company,
            jd=jd,
            progress=lambda text: status.update("researching", text),
            resume_links=links,
            check_links=False,
        )
        return research, None
    except Exception as error:
        return None, str(error)


def run(source, tech=1, project=1, behavioral=1, hr=1, on_change=None,
        jd_text=None, cover_letter=False, company=None, deep_research=False):
    status = Status(on_change=on_change)
    jd_text = (jd_text or "").strip()[:MAX_JD_CHARS]

    try:
        status.update("extracting", "Reading resume PDF")
        text = extract_resume_text(source)

        status.update(
            "structuring",
            "Organising resume and job description" if jd_text else "Organising resume data",
        )
        with ThreadPoolExecutor(max_workers=1) as pool:
            pages_future = pool.submit(_read_links, text) if deep_research else None
            structured, jd, jd_error = _structure_all(text, jd_text)
            pages, links_error = pages_future.result() if pages_future else ([], None)

        links = None
        if deep_research:
            status.update("researching", "Checking the links in your resume")
            links, check_error = _check_links(pages, structured)
            links_error = links_error or check_error

        status.update(
            "analysing",
            "Insights, improvements, interview questions and cover letter"
            if cover_letter
            else "Insights, improvements and interview questions",
        )
        research, research_error = None, None
        with ThreadPoolExecutor(max_workers=1) as pool:
            analysis = pool.submit(
                analyse, structured, tech, project, behavioral, hr, jd, cover_letter, links
            )

            if deep_research:
                status.update("researching", "Researching the company")
                research, research_error = _research(structured, company, jd, status, links)
                if not analysis.done():
                    status.update("analysing", "Finishing the resume analysis")

            report, better, questions, letter, letter_error = analysis.result()

        status.done()

    except Exception as error:
        status.fail(error)
        raise

    return {
        "structured": structured,
        "report": report,
        "better": better,
        "questions": questions,
        "jd": jd,
        "jd_error": jd_error,
        "cover_letter": letter,
        "cover_letter_error": letter_error,
        "research": research,
        "research_error": research_error,
        "resume_links": links,
        "links_error": links_error,
    }