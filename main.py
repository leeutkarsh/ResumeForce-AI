"""ResumeForce central system.

Every part of the pipeline (extract -> structure -> analyse) is wired together
here. The Streamlit UI (ui.py) and the command line both call `run()`.
"""

import json
from concurrent.futures import ThreadPoolExecutor
from extractor import extract_resume_text
from LLM import llm
from prompts import improve, insight, interview, structure
from status import Status

EMPTY_QUESTIONS = {"technical": [], "projects": [], "behavioral": [], "hr": []}


def analyse(structured, tech=1, project=1, behavioral=1, hr=1):
    """Run insight, improvement and interview generation in parallel."""
    wants_questions = any(count > 0 for count in (tech, project, behavioral, hr))

    prompts = [insight(structured), improve(structured)]
    if wants_questions:
        prompts.append(interview(structured, tech, behavioral, hr, project))

    with ThreadPoolExecutor(max_workers=len(prompts)) as pool:
        results = list(pool.map(llm, prompts))

    report, better = results[0], results[1]
    questions = results[2] if wants_questions else dict(EMPTY_QUESTIONS)

    return report, better, questions


def run(source, tech=1, project=1, behavioral=1, hr=1, on_change=None):
    """Full pipeline.

    source:     path to a PDF, or the raw PDF bytes (e.g. from an upload).
    on_change:  optional callback that receives the status dict on every step.
    returns:    {"structured", "report", "better", "questions"}
    """
    status = Status(on_change=on_change)

    try:
        status.update("extracting", "Reading resume PDF")
        text = extract_resume_text(source)

        status.update("structuring", "Organising resume data")
        structured = llm(structure(text))

        status.update("analysing", "Insights, improvements and interview questions")
        report, better, questions = analyse(structured, tech, project, behavioral, hr)

        status.done()

    except Exception as error:
        status.fail(error)
        raise

    return {
        "structured": structured,
        "report": report,
        "better": better,
        "questions": questions,
    }