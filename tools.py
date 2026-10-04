import functools
import ipaddress
import os
import re
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx

from LLM import client

USER_AGENT = "Mozilla/5.0 (compatible; ResumeForceBot/1.0)"
TIMEOUT = 15
PAGE_LIMIT = 6000
CACHE_SECONDS = 3600

NOT_OFFICIAL = (
    "linkedin.com", "glassdoor.com", "glassdoor.co.in", "indeed.com", "wikipedia.org",
    "facebook.com", "twitter.com", "x.com", "instagram.com", "youtube.com",
    "crunchbase.com", "ambitionbox.com", "naukri.com", "zaubacorp.com",
    "bloomberg.com", "reddit.com", "medium.com", "quora.com",
)
UNREADABLE = ("linkedin.com", "youtube.com", "facebook.com", "instagram.com", "twitter.com", "x.com")
USEFUL_PAGE_WORDS = ("about", "career", "jobs", "culture", "values", "products", "technology", "engineering")

KNOWN_HOSTS = (
    "github.com", "gitlab.com", "linkedin.com", "behance.net", "medium.com", "kaggle.com",
    "leetcode.com", "codeforces.com", "codechef.com", "hackerrank.com", "huggingface.co",
    "dev.to", "dribbble.com", "npmjs.com", "pypi.org", "github.io", "netlify.app",
    "vercel.app", "streamlit.app", "herokuapp.com", "onrender.com",
)
LIVE_DEMO_HOSTS = ("github.io", "netlify.app", "vercel.app", "streamlit.app", "herokuapp.com", "onrender.com")

LINK_PATTERN = re.compile(
    r"https?://[^\s,;<>\"')\]]+"
    r"|(?<![\w@.-])(?:[\w-]+\.)*(?:"
    + "|".join(re.escape(host) for host in KNOWN_HOSTS)
    + r")(?:/[^\s,;<>\"')\]]*)?",
    re.I,
)

QUESTION_PREFIX = re.compile(r"^(?:q(?:uestion)?\s*\d*\s*[:.)-]\s*|\d+\s*[.):-]\s*)+", re.I)
QUESTION_STARTS = (
    "what", "why", "how", "when", "where", "which", "who", "explain", "describe",
    "tell me", "can you", "could you", "do you", "does", "did", "is ", "are ",
    "have you", "would you", "will you", "write", "difference",
)
BAD_QUESTION_WORDS = (
    "click here", "subscribe", "sign up", "log in", "cookie", "newsletter",
    "privacy policy", "share this", "read more", "leave a comment",
)
BLOCK_TAGS = {"p", "br", "div", "li", "ul", "ol", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article"}
SKIP_TAGS = {"script", "style", "noscript", "svg"}


def cached(seconds=CACHE_SECONDS):
    def decorator(function):
        store = {}

        @functools.wraps(function)
        def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            hit = store.get(key)
            if hit and time.time() - hit[0] < seconds:
                return hit[1]

            value = function(*args, **kwargs)
            failed = not value or (isinstance(value, dict) and value.get("error"))
            if not failed:
                store[key] = (time.time(), value)
            return value

        return wrapper

    return decorator


def clean_text(text, limit=PAGE_LIMIT):
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in (text or "").splitlines()]
    return "\n".join(line for line in lines if line)[:limit]


def _matches(host, domains):
    host = host.lower().removeprefix("www.")
    return any(host == domain or host.endswith("." + domain) for domain in domains)


def _page(url="", title="", text="", links=None, error=None, kind="page"):
    return {"url": url, "kind": kind, "title": title, "text": text, "links": links or [], "error": error}


def looks_like_url(text):
    pattern = r"^(https?://)?(www\.)?[\w-]+(\.[\w-]+)+(/\S*)?$"
    return bool(re.match(pattern, (text or "").strip(), re.I))


def normalise_url(text):
    text = (text or "").strip().strip("<>()[]\"',.;")
    if not text or " " in text or text.lower().startswith(("mailto:", "tel:")):
        return None
    if not re.match(r"^https?://", text, re.I):
        text = "https://" + text
    if "." not in urlparse(text).netloc:
        return None
    return text


def is_safe_url(url):
    parsed = urlparse(url or "")
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False

    try:
        addresses = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror:
        return False

    for item in addresses:
        try:
            ip = ipaddress.ip_address(item[4][0])
        except ValueError:
            return False
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
            return False
    return True


def company_name_from_url(url):
    host = urlparse(normalise_url(url) or "").netloc.lower()
    skip = {"www", "com", "co", "in", "org", "net", "io", "ai", "careers", "jobs"}
    parts = [part for part in host.split(".") if part not in skip]
    name = parts[-1] if parts else host
    return name.replace("-", " ").title()


def _company_name(company):
    company = (company or "").strip()
    return company_name_from_url(company) if looks_like_url(company) else company


def _root(url):
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.links = []
        self.title = ""
        self.skip_depth = 0
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in SKIP_TAGS:
            self.skip_depth += 1
        elif tag == "title":
            self.in_title = True
        elif tag == "a":
            href = dict(attrs).get("href")
            if href:
                self.links.append(href)
        if tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS:
            self.skip_depth = max(0, self.skip_depth - 1)
        elif tag == "title":
            self.in_title = False
        if tag in BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        elif not self.skip_depth:
            self.parts.append(data)


def _get(url):
    for _ in range(4):
        if not is_safe_url(url):
            raise ValueError("address is blocked or unreachable")

        response = httpx.get(url, headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT)
        location = response.headers.get("location")
        if response.status_code in (301, 302, 303, 307, 308) and location:
            url = urljoin(url, location)
            continue

        response.raise_for_status()
        return response
    raise ValueError("too many redirects")


def _fetch_directly(url, limit):
    try:
        response = _get(url)
        content_type = response.headers.get("content-type", "")
        if "html" not in content_type and "text" not in content_type:
            return _page(url, error="This link is not a readable page")

        parser = _TextParser()
        parser.feed(response.text)
        text = clean_text("".join(parser.parts), limit)
        if not text:
            return _page(url, error="The page had no readable text")

        links = [urljoin(url, link) for link in parser.links][:60]
        return _page(url, clean_text(parser.title, 200), text, links)
    except Exception as error:
        return _page(url, error=f"Could not open page: {error}")


@cached()
def search_web(query, max_results=5):
    try:
        data = client.web_search(query=query, max_results=max_results).model_dump()
    except Exception:
        return []

    return [
        {
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "content": clean_text(item.get("content", ""), 800),
        }
        for item in data.get("results", [])
        if item.get("url")
    ]


@cached()
def fetch_page(url, limit=PAGE_LIMIT):
    url = normalise_url(url)
    if not url:
        return _page(error="That is not a valid link")

    try:
        data = client.web_fetch(url=url).model_dump()
        text = clean_text(data.get("content", ""), limit)
        if text:
            return _page(url, clean_text(data.get("title", ""), 200), text, data.get("links") or [])
    except Exception:
        pass

    return _fetch_directly(url, limit)


def fetch_many(urls, limit=PAGE_LIMIT):
    if not urls:
        return []
    with ThreadPoolExecutor(max_workers=min(len(urls), 5)) as pool:
        return list(pool.map(lambda url: fetch_page(url, limit), urls))


def find_official_site(company):
    company = (company or "").strip()
    if not company:
        return None
    if looks_like_url(company):
        return _root(normalise_url(company))

    words = [word for word in re.findall(r"[a-z0-9]+", company.lower()) if len(word) > 2]
    if len(words) > 1:
        words.append("".join(word[0] for word in words))

    allowed = []
    for result in search_web(f"{company} official website", 8):
        host = urlparse(result["url"]).netloc.lower().removeprefix("www.")
        if _matches(host, NOT_OFFICIAL):
            continue
        if any(word in host for word in words):
            return _root(result["url"])
        allowed.append(result["url"])

    if not allowed:
        return None
    allowed.sort(key=lambda url: len([part for part in urlparse(url).path.split("/") if part]))
    return _root(allowed[0])


def _useful_links(page, website):
    host = urlparse(website).netloc
    found = []
    for word in USEFUL_PAGE_WORDS:
        for link in page.get("links", []):
            full = urljoin(website, link)
            parsed = urlparse(full)
            if parsed.netloc != host or word not in parsed.path.lower():
                continue
            full = full.split("#")[0]
            if full.rstrip("/") != website.rstrip("/") and full not in found:
                found.append(full)
    return found


def company_overview(company):
    name = _company_name(company)
    website = find_official_site(company)

    pages = []
    if website:
        home = fetch_page(website)
        pages.append(home)
        pages.extend(fetch_many(_useful_links(home, website)[:3]))

    return {
        "name": name,
        "website": website,
        "pages": [page for page in pages if page["text"]],
        "news": search_web(f"{name} company news", 5),
        "about": search_web(f"{name} what the company does products tech stack", 5),
    }


def _as_question(line):
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", line.strip())
    text = re.sub(r"^[#>\s*_`-]+", "", text)
    text = QUESTION_PREFIX.sub("", text).strip(" *_`")

    if not text.endswith("?"):
        return None
    if not 4 <= len(text.split()) <= 35:
        return None

    lowered = text.lower()
    if any(word in lowered for word in BAD_QUESTION_WORDS):
        return None
    if not lowered.startswith(QUESTION_STARTS):
        return None
    return text


def _answer_hint(lines, index):
    hint = []
    for line in lines[index + 1:index + 4]:
        if _as_question(line):
            break
        if any(word in line.lower() for word in BAD_QUESTION_WORDS):
            continue
        hint.append(line)
    return clean_text(" ".join(hint), 400)


def find_questions(pages, limit=40):
    found, seen = [], set()
    for page in pages:
        lines = (page.get("text") or "").splitlines()
        for index, line in enumerate(lines):
            question = _as_question(line)
            if not question:
                continue

            key = re.sub(r"\W+", " ", question.lower()).strip()
            if key in seen:
                continue
            seen.add(key)

            found.append({
                "question": question,
                "source": page["url"],
                "title": page.get("title", ""),
                "answer_hint": _answer_hint(lines, index),
            })
            if len(found) >= limit:
                return found
    return found


def _research_questions(queries, max_pages):
    with ThreadPoolExecutor(max_workers=len(queries)) as pool:
        batches = list(pool.map(search_web, queries))

    results, seen = [], set()
    for batch in batches:
        for item in batch:
            host = urlparse(item["url"]).netloc
            if item["url"] in seen or _matches(host, UNREADABLE):
                continue
            seen.add(item["url"])
            results.append(item)

    pages = [page for page in fetch_many([item["url"] for item in results[:max_pages]], 8000) if page["text"]]

    return {
        "questions": find_questions(pages),
        "sources": [{"title": page["title"], "url": page["url"]} for page in pages],
        "pages": [
            {"url": page["url"], "title": page["title"], "text": page["text"][:2500]}
            for page in pages
        ],
        "search_results": results,
    }


def past_questions(company, role=None, max_pages=5):
    name = _company_name(company)
    role_text = f" {role}" if role else ""
    queries = [
        f"{name}{role_text} interview questions",
        f"{name}{role_text} interview experience",
        f"{name}{role_text} interview process rounds",
    ]
    result = _research_questions(queries, max_pages)
    return {"company": name, "role": role, **result}


def trending_questions(role=None, skills=None, max_pages=5):
    year = date.today().year
    topic = role or (" ".join(skills[:3]) if skills else "") or "software developer"
    queries = [
        f"most asked {topic} interview questions {year}",
        f"{topic} interview questions and answers",
        f"latest {topic} interview questions {year}",
    ]
    result = _research_questions(queries, max_pages)
    return {"company": None, "role": topic, **result}


def interview_questions(company=None, role=None, skills=None, max_pages=5):
    if company and company.strip():
        return past_questions(company, role, max_pages)
    return trending_questions(role, skills, max_pages)


def role_skill_trends(role):
    year = date.today().year
    queries = [f"in demand skills for {role} {year}", f"{role} job requirements skills"]
    with ThreadPoolExecutor(max_workers=2) as pool:
        batches = list(pool.map(search_web, queries))
    return {"role": role, "results": [item for batch in batches for item in batch]}


def find_job_posts(company, role=None, max_pages=3):
    name = _company_name(company)
    role_text = f" {role}" if role else ""
    results = search_web(f"{name}{role_text} job description requirements responsibilities", 6)
    readable = [item for item in results if not _matches(urlparse(item["url"]).netloc, UNREADABLE)]
    pages = [page for page in fetch_many([item["url"] for item in readable[:max_pages]]) if page["text"]]
    return {"company": name, "role": role, "results": readable, "pages": pages}


def _walk(data, strings):
    if isinstance(data, str):
        strings.append(data)
    elif isinstance(data, dict):
        for value in data.values():
            _walk(value, strings)
    elif isinstance(data, (list, tuple)):
        for value in data:
            _walk(value, strings)


def collect_links(data):
    strings = []
    _walk(data, strings)

    found = {}
    for text in strings:
        for match in LINK_PATTERN.findall(text):
            url = normalise_url(match.rstrip(".,;:!?"))
            if url:
                key = re.sub(r"^https?://(www\.)?", "", url).rstrip("/").lower()
                found.setdefault(key, url)
    return list(found.values())


def classify_link(url):
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    parts = [part for part in parsed.path.split("/") if part]

    if host == "github.com":
        if len(parts) == 1:
            return "github_profile"
        if len(parts) >= 2:
            return "github_repo"
    if _matches(host, ("linkedin.com",)):
        return "linkedin"
    if _matches(host, LIVE_DEMO_HOSTS):
        return "live_demo"
    return "other"


def _github_get(path, raw=False):
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/vnd.github.raw+json" if raw else "application/vnd.github+json",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    response = httpx.get(f"https://api.github.com{path}", headers=headers, timeout=TIMEOUT)
    if response.status_code == 404:
        raise ValueError("GitHub page not found")
    if response.status_code == 403:
        raise ValueError("GitHub rate limit reached")
    response.raise_for_status()
    return response.text if raw else response.json()


def _github_profile(url, user):
    info = _github_get(f"/users/{user}")
    repos = _github_get(f"/users/{user}/repos?sort=pushed&per_page=30")
    own = [repo for repo in repos if not repo.get("fork")]
    own.sort(key=lambda repo: (repo.get("stargazers_count", 0), repo.get("pushed_at", "")), reverse=True)

    lines = [
        f"GitHub user: {info.get('login')}",
        f"Name: {info.get('name') or 'not set'}",
        f"Bio: {info.get('bio') or 'not set'}",
        f"Public repos: {info.get('public_repos', 0)}",
        f"Followers: {info.get('followers', 0)}",
        f"Account created: {(info.get('created_at') or '')[:4]}",
        "",
        "Top repositories:",
    ]
    for repo in own[:6]:
        lines.append(
            f"- {repo['name']} ({repo.get('language') or 'n/a'}, "
            f"{repo.get('stargazers_count', 0)} stars, last push {(repo.get('pushed_at') or '')[:10]}): "
            f"{repo.get('description') or 'no description'}"
        )
    if not own:
        lines.append("- no original repositories")

    return _page(url, f"GitHub profile: {user}", "\n".join(lines), kind="github_profile")


def _github_repo(url, owner, name):
    info = _github_get(f"/repos/{owner}/{name}")
    try:
        readme = clean_text(_github_get(f"/repos/{owner}/{name}/readme", raw=True), 3000)
    except Exception:
        readme = ""

    lines = [
        f"Repository: {info.get('full_name')}",
        f"Description: {info.get('description') or 'none'}",
        f"Language: {info.get('language') or 'n/a'}",
        f"Stars: {info.get('stargazers_count', 0)}, forks: {info.get('forks_count', 0)}",
        f"Topics: {', '.join(info.get('topics') or []) or 'none'}",
        f"Last push: {(info.get('pushed_at') or '')[:10]}",
        f"Live site: {info.get('homepage') or 'none'}",
        f"Is a fork: {info.get('fork', False)}",
        "",
        "README:",
        readme or "(no README)",
    ]
    return _page(url, info.get("full_name", name), "\n".join(lines), kind="github_repo")


def read_github(url):
    parts = [part for part in urlparse(url).path.split("/") if part]
    try:
        if len(parts) == 1:
            return _github_profile(url, parts[0])
        if len(parts) >= 2:
            return _github_repo(url, parts[0], parts[1].removesuffix(".git"))
        return _page(url, error="This GitHub link has no user or repository")
    except Exception as error:
        return _page(url, error=str(error))


def read_link(url):
    url = normalise_url(url)
    if not url:
        return _page(error="That is not a valid link")

    kind = classify_link(url)
    if kind == "linkedin":
        return _page(url, kind=kind, error="LinkedIn blocks automated reading")

    if kind in ("github_profile", "github_repo"):
        page = read_github(url)
        if page["error"] and "not found" not in page["error"]:
            fallback = fetch_page(url)
            if not fallback["error"]:
                page = fallback
    else:
        page = fetch_page(url)

    return {**page, "kind": kind}


def read_resume_links(data, limit=8):
    links = collect_links(data)[:limit]
    if not links:
        return []
    with ThreadPoolExecutor(max_workers=min(len(links), 4)) as pool:
        return list(pool.map(read_link, links))


TOOLS = {
    "search_web": {
        "function": search_web,
        "description": "Search the internet. args: query (text), max_results (number, optional)",
    },
    "fetch_page": {
        "function": fetch_page,
        "description": "Read any web page as text. args: url",
    },
    "find_official_site": {
        "function": find_official_site,
        "description": "Find a company's official website from its name or url. args: company",
    },
    "company_overview": {
        "function": company_overview,
        "description": "Read a company's website pages and recent news. args: company (name or url)",
    },
    "past_questions": {
        "function": past_questions,
        "description": "Find interview questions reported for a company, with sources. args: company, role (optional)",
    },
    "trending_questions": {
        "function": trending_questions,
        "description": "Find currently trending interview questions when no company is known. args: role (optional)",
    },
    "role_skill_trends": {
        "function": role_skill_trends,
        "description": "Find skills currently in demand for a role. args: role",
    },
    "find_job_posts": {
        "function": find_job_posts,
        "description": "Find job descriptions for a company and role. args: company, role (optional)",
    },
    "read_link": {
        "function": read_link,
        "description": "Read a link from a resume such as GitHub, a project or a live demo. args: url",
    },
}


def tool_guide():
    return "\n".join(f"- {name}: {tool['description']}" for name, tool in TOOLS.items())


def run_tool(name, args=None):
    tool = TOOLS.get(name)
    if not tool:
        return {"error": f"Unknown tool: {name}"}

    try:
        return tool["function"](**(args or {}))
    except TypeError as error:
        return {"error": f"Bad arguments for {name}: {error}"}
    except Exception as error:
        return {"error": f"{name} failed: {error}"}
