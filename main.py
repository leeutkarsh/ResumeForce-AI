from concurrent.futures import ThreadPoolExecutor
from extractor import extract_resume_text
from LLM import llm
from prompts import improve, insight, interview, structure, parse_jd, write_cover_letter
from status import Status

EMPTY_QUESTIONS = {"technical": [], "projects": [], "behavioral": [], "hr": []}
MAX_JD_CHARS = 6000


def _try(prompt):
    try:
        return llm(prompt), None
    except Exception as error:
        return None, str(error)


def analyse(structured, tech=1, project=1, behavioral=1, hr=1, jd=None, want_letter=False):
    """Run insight, improvement, interview and (optionally) cover letter in parallel."""
    wants_questions = any(count > 0 for count in (tech, project, behavioral, hr))

    prompts = [insight(structured, jd), improve(structured, jd)]
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


def run(source, tech=1, project=1, behavioral=1, hr=1, on_change=None,
        jd_text=None, cover_letter=False):
    status = Status(on_change=on_change)
    jd_text = (jd_text or "").strip()[:MAX_JD_CHARS]

    try:
        status.update("extracting", "Reading resume PDF")
        text = extract_resume_text(source)

        status.update(
            "structuring",
            "Organising resume and job description" if jd_text else "Organising resume data",
        )
        structured, jd, jd_error = _structure_all(text, jd_text)

        status.update(
            "analysing",
            "Insights, improvements, interview questions and cover letter"
            if cover_letter
            else "Insights, improvements and interview questions",
        )
        report, better, questions, letter, letter_error = analyse(
            structured, tech, project, behavioral, hr, jd, cover_letter
        )

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
    }
