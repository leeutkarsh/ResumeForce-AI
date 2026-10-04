import json
from concurrent.futures import ThreadPoolExecutor

from agent_llm import (
    answer_reported_questions,
    build_company_profile,
    decide_next,
    generate_likely_questions,
    summarise_resume_links,
)
from tools import read_resume_links, run_tool

MAX_STEPS = 6
MAX_REPEATS = 2

STEP_TEXT = {
    "company_overview": "Reading the company website and news",
    "past_questions": "Searching past interview questions",
    "trending_questions": "Searching trending interview questions",
    "find_job_posts": "Looking for job descriptions",
    "role_skill_trends": "Checking skills in demand",
    "search_web": "Searching the web",
    "fetch_page": "Reading a web page",
    "find_official_site": "Finding the official website",
    "read_link": "Reading a link",
}


def do_nothing(text):
    return None


def attempt(function, *args):
    try:
        return function(*args), None
    except Exception as error:
        return None, str(error)


def is_ok(result):
    return isinstance(result, dict) and not result.get("error")


def pick_company(company, jd):
    if company and company.strip():
        return company.strip()
    if isinstance(jd, dict) and jd.get("company"):
        return str(jd["company"]).strip()
    return ""


def pick_role(role, jd, resume):
    if role and role.strip():
        return role.strip()
    if isinstance(jd, dict) and jd.get("job_title"):
        return str(jd["job_title"]).strip()
    experience = resume.get("experience") or []
    if experience and isinstance(experience[0], dict):
        return str(experience[0].get("role", "")).strip()
    return ""


def summarise_result(result):
    if isinstance(result, list):
        return f"{len(result)} results"
    if not isinstance(result, dict):
        return "done"
    if result.get("error"):
        return "failed: " + str(result["error"])
    if "questions" in result:
        return f"{len(result['questions'])} questions found"
    if "pages" in result:
        return f"{len(result['pages'])} pages read"
    if "text" in result:
        return f"page read ({len(result['text'])} characters)"
    return "done"


def choose_step(state):
    try:
        decision = decide_next(state)
        return str(decision["action"]), dict(decision["args"])
    except Exception:
        return "finish", {}


def run_loop(state, say):
    gathered = {}
    tried = set()
    repeats = 0

    while state["steps_left"] > 0:
        action, args = choose_step(state)
        if action == "finish":
            break

        call = action + json.dumps(args, sort_keys=True, default=str)
        if call in tried:
            repeats += 1
            state["history"].append(f"{action} skipped because it was already done")
            if repeats >= MAX_REPEATS:
                break
            continue
        tried.add(call)

        state["steps_left"] -= 1
        say(STEP_TEXT.get(action, f"Running {action}"))
        result = run_tool(action, args)
        gathered[action] = result
        state["history"].append(f"{action} {json.dumps(args, default=str)} -> {summarise_result(result)}")

    return gathered


def pick_questions(gathered, company, role, skills, problems):
    if company:
        if "past_questions" not in gathered:
            gathered["past_questions"] = run_tool("past_questions", {"company": company, "role": role or None})

        reports = gathered["past_questions"]
        if is_ok(reports) and reports["questions"]:
            return reports["questions"], reports["sources"], "reported"

        problems.append(f"No interview reports were found for {company}. Showing trending questions instead.")

    if "trending_questions" not in gathered or not is_ok(gathered["trending_questions"]):
        gathered["trending_questions"] = run_tool("trending_questions", {"role": role or None, "skills": skills})

    trending = gathered["trending_questions"]
    if is_ok(trending):
        return trending["questions"], trending["sources"], "trending"

    problems.append("Could not find interview questions online.")
    return [], [], "trending"


def online_job_text(gathered):
    posts = gathered.get("find_job_posts")
    if not is_ok(posts):
        return None
    pages = [{"url": page["url"], "text": page["text"][:1500]} for page in posts.get("pages", [])[:2]]
    return pages or None


def analyse_links(resume):
    pages = read_resume_links(resume)
    if not pages:
        return None
    return summarise_resume_links(pages, resume)


def add_problem(problems, name, error):
    if error:
        problems.append(f"{name} failed: {error}")


def research_company(resume, company=None, role=None, jd=None, progress=None, max_steps=MAX_STEPS,
                     resume_links=None, check_links=True):
    say = progress or do_nothing
    resume = resume or {}
    company = pick_company(company, jd)
    role = pick_role(role, jd, resume)
    skills = list(resume.get("skills") or [])[:3]
    problems = []

    state = {
        "company": company or "not given",
        "role": role or "not given",
        "job_description_given": bool(jd),
        "history": [],
        "steps_left": max_steps,
    }

    with ThreadPoolExecutor(max_workers=3) as pool:
        links_future = pool.submit(attempt, analyse_links, resume) if check_links else None

        gathered = run_loop(state, say)
        if company and "company_overview" not in gathered:
            say(STEP_TEXT["company_overview"])
            gathered["company_overview"] = run_tool("company_overview", {"company": company})

        say("Collecting interview questions")
        found, sources, label = pick_questions(gathered, company, role, skills, problems)

        say("Writing the company profile and answers")
        overview = gathered.get("company_overview")
        profile_future = None
        if is_ok(overview):
            profile_future = pool.submit(attempt, build_company_profile, overview)
        answers_future = pool.submit(attempt, answer_reported_questions, found, resume, role)

        profile, profile_error = profile_future.result() if profile_future else (None, None)
        answers, answers_error = answers_future.result()
        links, links_error = links_future.result() if links_future else (resume_links, None)

    add_problem(problems, "Company profile", profile_error)
    add_problem(problems, "Writing answers", answers_error)
    add_problem(problems, "Resume link check", links_error)

    answers = answers or []
    for item in answers:
        item["label"] = label

    say("Predicting likely questions")
    known = [item["question"] for item in answers]
    job_context = jd or online_job_text(gathered)
    likely, likely_error = attempt(generate_likely_questions, profile, resume, job_context, role, known)
    add_problem(problems, "Likely questions", likely_error)

    return {
        "company": company or None,
        "role": role or None,
        "website": overview.get("website") if is_ok(overview) else None,
        "profile": profile,
        "questions": answers,
        "question_type": label,
        "likely": likely or [],
        "sources": sources,
        "news": overview.get("news", []) if is_ok(overview) else [],
        "resume_links": links,
        "steps": state["history"],
        "problems": problems,
    }