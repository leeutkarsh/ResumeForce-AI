# ResumeForce AI

Live demo: [resumeforce-ai.streamlit.app](https://resumeforce-ai-ls6qbxft4htnhhzwi99osn.streamlit.app)

ResumeForce AI reviews a resume PDF and prepares the candidate for interviews. It scores the resume, rewrites weak wording without inventing facts, and writes interview questions with short model answers. Three optional features add a job description match, a cover letter, and web research on the target company and the links in the resume.

The app is written in Python. The front end is Streamlit and the language model is served through Ollama.

## Features

Every run includes:

- Resume parsing. The PDF is converted into structured data: contact details, skills, experience, projects, education, certifications, achievements and languages.
- Resume scoring. Overall score, ATS readiness score, career level, five section scores, strengths, weaknesses, red flags, missing keywords, missing sections and three suggested roles.
- Improvements. A rewritten summary, reordered skills, rewritten bullets for experience and projects, three priority actions, and a list of details only the candidate can supply (metrics, links, results).
- Interview prep. Technical, project, behavioral and HR questions with short first-person answers based on the resume. The user chooses how many questions of each type, from 0 to 20.

Optional features:

- Job description match. Paste a job posting to get a match score, matched and missing skills, experience gaps and a fit summary. The posting is also passed to the other prompts.
- Cover letter. Written from the resume, editable in the app, and downloadable as a .txt or a formatted .docx file.
- Deep research. Searches the web and produces a company profile, interview questions reported by real candidates, predicted questions, and a review of the GitHub and portfolio links found in the resume. Expect this to add a minute or more to a run.

## Setup

Requirements: Python 3.10 or newer and an Ollama API key.

```bash
git clone <repo-url>
cd resumeforce
pip install -r requirements.txt
```

Create a file named `.env` in the project folder:

```env
OLLAMA_API_KEY=your_key_here
```

Start the app:

```bash
streamlit run ui.py
```

`style.css` and `icon.png` must be in the same folder as `ui.py`. On Streamlit Cloud, add `OLLAMA_API_KEY` under Secrets instead of using a `.env` file.

### Dependencies

| Package | Used for |
|---|---|
| streamlit | The web interface. Version 1.36 or newer, because `ui.py` uses `vertical_alignment` in `st.columns`. |
| pymupdf | Reading text and hyperlinks from the PDF. Version 1.24.3 or newer, which added the `import pymupdf` name. |
| ollama | Calling the model and Ollama's web search and web fetch. Version 0.6.0 or newer, because older versions have no web search. |
| python-dotenv | Loading the `.env` file |
| python-docx | Building the Word cover letter |
| httpx | Reading web pages and the GitHub API (installed with ollama, but `tools.py` imports it directly, so list it in `requirements.txt`) |

## Using the app

1. Upload a text-based PDF resume.
2. Set how many questions you want for each topic. The defaults are 3 technical, 2 project, 2 behavioral and 2 HR.
3. Optional: paste a job description.
4. Optional: turn on Generate cover letter.
5. Optional: turn on Deep research and enter a company name or website. If you leave the company empty, the app uses the company from the job description. If there is no company at all, it researches trending questions for your role.
6. Click Analyse resume. A progress box shows each step as it runs.

Results appear in tabs. The whole result can be downloaded as a JSON file.

| Tab | Shown when |
|---|---|
| Overview | Always. It includes an Online presence section when resume links were checked. |
| Job match | A job description was provided and parsed. |
| Improvements | Always. A toggle compares the original wording with the improved wording. |
| Interview prep | Always. It shows a message if every question count is 0. |
| Company research | Deep research returned a result. |
| Parsed resume | Always. |
| Cover letter | A cover letter was requested and generated. |

The Company research tab has its own sub-tabs: Company, Reported questions (or Trending questions), Likely questions, and Your links. A sub-tab appears only if it has content.

## Project structure

```text
resumeforce/
├── ui.py            Streamlit front end: inputs, progress box, result tabs
├── main.py          Runs the whole pipeline in order
├── extractor.py     PDF to text, plus hyperlinks stored in the PDF
├── LLM.py           Ollama client, JSON mode, retry, JSON parsing
├── prompts.py       Schemas and prompts for the main analysis
├── agent.py         Deep research: the step loop and the final result
├── agent_llm.py     Prompts used by deep research
├── tools.py         Web search, page reading, GitHub reading, question finding
├── docx_letter.py   Builds the Word cover letter
├── status.py        Progress tracker that calls a function on every update
├── style.css        All colors, fonts and spacing for the interface
├── icon.png         App icon
├── .env             OLLAMA_API_KEY (do not commit this file)
└── requirements.txt
```

## How a run works

`main.run()` is the only place that knows the order of the steps. `ui.py` calls `run()` and displays what comes back. It never calls the model or the extractor directly.

1. Extract. `extractor.py` opens the PDF with PyMuPDF and reads the text page by page in reading order. Hyperlinks stored in the PDF are added at the end under a `Links:` heading, so URLs hidden behind link text are not lost. If the PDF has no text, it raises an error because the file is probably a scanned image.

2. Structure. The `structure()` prompt turns the raw text into JSON that follows `STRUCTURE_SCHEMA`. If a job description was given (cut to 6,000 characters), `parse_jd()` turns it into JSON at the same time. If the job description cannot be parsed, the run continues with a general review and shows a warning. If Deep research is on, the links found in the resume are also fetched during this step.

3. Check links (Deep research only). The model reviews each page that was fetched. The result feeds the analysis prompts and the Online presence section.

4. Analyse. These prompts run at the same time in separate threads, each reading the structured resume rather than the raw text:

   | Prompt | Output |
   |---|---|
   | `insight()` | Scores, strengths, weaknesses, red flags, missing keywords, suggested roles, job match |
   | `improve()` | Rewritten summary, skills and bullets, details to add, priority actions |
   | `interview()` | Questions and answers for each topic. Skipped when every count is 0. |
   | `write_cover_letter()` | Subject, greeting, paragraphs, sign-off. Only if requested. |

   While these run, the main thread runs the company research if Deep research is on.

5. Return. `run()` returns one dictionary, which the UI stores in `st.session_state["result"]` so the page survives reruns:

   ```python
   {
       "structured": {...},            # parsed resume
       "report": {...},                # scores, review, job_match
       "better": {...},                # improvements
       "questions": {...},             # interview prep
       "jd": {...} or None,            # parsed job description
       "jd_error": str or None,
       "cover_letter": {...} or None,
       "cover_letter_error": str or None,
       "research": {...} or None,      # deep research result
       "research_error": str or None,
       "resume_links": {...} or None,  # review of the links in the resume
       "links_error": str or None,
   }
   ```

If structuring, insight, improvements or interview generation fails, the whole run fails and the UI shows the error. The job description, cover letter, link check and company research are optional. When one of them fails, the rest of the results still appear with a warning.

## Deep research in detail

Deep research has two parts that run side by side: reading the links in the resume, and researching the company.

### Resume links

`tools.read_resume_links()` finds up to 8 links in the raw resume text, including the hyperlinks stored in the PDF, and reads them four at a time. Links that differ only by `www.`, capital letters or a trailing slash are merged. Each link is sorted into one of these types:

- GitHub profile or GitHub repository. These are read through the GitHub API: bio, public repository count, top original repositories, stars, last push date, whether a repository is a fork, and the first 3,000 characters of the README.
- Live demo (github.io, netlify.app, vercel.app, streamlit.app, herokuapp.com, onrender.com). Read as a normal web page.
- LinkedIn. Not read, because LinkedIn blocks automated access. It is reported as unchecked and is never counted as a weakness.
- Any link that fails to open. If the page does not exist (a 404), it is reported as a concern because a broken link on a resume is a real problem. Other failures, such as a GitHub rate limit or a network error, are reported as unchecked and are not counted as a concern.
- Other links. Read as a normal web page.

The model then lists strengths, concerns and skills shown for each page, writes one overall comment on which resume projects are backed by a link, and gives up to 5 suggestions. This evidence is added to the `insight()` and `improve()` prompts with firm limits: it can move a section score by at most 10 points, it is never used for the education or experience scores, and skills seen only on a link are suggested to the user but never added to the improved skills list.

### Company research

`agent.research_company()` works out the company (the input, or the job description) and the role (the job description title, or the most recent job on the resume). Then it runs a short loop:

1. The model is shown the list of tools and what has been done so far, and picks one tool or chooses to finish.
2. The tool runs and a short summary of its result is added to the history.
3. The loop stops when the model finishes, when 6 steps have been used, or when the model repeats an earlier call twice. Repeated calls are skipped, not run again. If the model fails to return a valid decision, the loop ends.

After the loop, the code makes sure the essentials exist, whatever the model chose:

- The company overview is fetched if it is still missing.
- Interview questions are collected. If the company is known, reported questions come first. If none are found, a warning is added and trending questions for the role are used instead.
- The company profile and the answers to the collected questions are written at the same time.
- Finally, 8 likely questions are predicted from the company profile, the job and the resume.

Questions in the results have one of three labels:

| Label | Meaning |
|---|---|
| Reported | The question was found on a web page about this company's interviews. The answer is written by the model from the resume. |
| Trending | The question was found on pages about the role in general. Used when there is no company or no company reports. |
| Likely | A prediction by the model. It is never presented as a question that was really asked, and each one has a short reason. |

Finding the reported questions does not use the model. `tools.find_questions()` scans page text for lines that end with a question mark, start with a question word, and are between 4 and 35 words long. It drops common page clutter such as cookie notices and newsletter prompts, removes duplicates, keeps up to 40, and saves the 3 lines after each question as a hint. The model then writes an answer for each question (at most 25), assigns a category, and can discard lines that are not real interview questions. It cannot add questions or change their wording.

### Tools available to the research loop

| Tool | What it does |
|---|---|
| `company_overview` | Finds the official website, reads the home page and up to 3 useful pages (about, careers, culture, products and similar), and searches for news and a description |
| `past_questions` | Searches three queries about interview questions, experiences and rounds for the company, reads up to 5 pages, and extracts questions |
| `trending_questions` | Same as above, for a role or the top skills, using the current year in the queries |
| `find_job_posts` | Searches for job descriptions for the company and role and reads up to 3 pages |
| `role_skill_trends` | Searches for skills currently in demand for a role |
| `find_official_site` | Finds a company's official website, skipping sites such as LinkedIn, Glassdoor and Wikipedia |
| `search_web` | Runs a web search |
| `fetch_page` | Reads one web page as text |
| `read_link` | Reads one link from a resume, using the GitHub API for GitHub links |

Web search and page reading go through Ollama's hosted `web_search` and `web_fetch` using the same API key. If `web_fetch` returns nothing, `tools.py` fetches the page itself with httpx. Search and page results are cached in memory for one hour, and failed results are never cached.

## Cover letter export

The model returns the letter as structured JSON: subject, greeting, paragraphs, sign-off and a list of details only the candidate can add. The UI joins it into plain text and shows it in an editable box.

When the user downloads the .docx file, `docx_letter.py` splits the edited text into a greeting, body paragraphs and a sign-off. It treats the first block as the greeting and the last block as the sign-off if each is under 80 characters. The document contains the candidate's name, a contact line with clickable email, phone, location and up to two profile links, today's date, "Hiring Manager" with the company name if there is one, the subject line, and the letter. The font is Calibri with a teal accent.

## LLM layer

`LLM.py` provides `llm(prompt)`, which returns a dictionary.

- It connects to `https://ollama.com` with the key from `.env` or Streamlit secrets. The app stops with a clear message if the key is missing.
- It uses JSON mode and temperature 0 for repeatable output. A system prompt repeats that only JSON may be returned.
- It retries once after 2 seconds on a network or API error.
- `parse()` keeps the text between the first `{` and the last `}`, then reads it as JSON. If the model stopped because it hit the length limit, the error says the output was cut off.
- The research prompts in `agent_llm.py` retry once more when the model returns invalid JSON. The prompts in `main.py` do not.
- The model name is the `MODEL` constant in `LLM.py`. The default is `gemma4:31b`.

## Accuracy and safety rules

- No invented facts. Every prompt forbids made-up metrics, tools, employers, results and links. When a stronger result needs a detail only the user has, the model puts an instruction under `add_these_yourself` instead.
- Honest gaps. With a job description, required skills missing from the resume are reported as gaps. Rewrites, answers and the cover letter must not claim them.
- ATS score. Without a job description it is a general readiness estimate. With one, it measures fit to that job.
- Web text is data. Every research prompt tells the model to ignore any instruction written inside a web page.
- Safe fetching. When the app fetches a page itself, it checks the address first and refuses private, loopback, link-local and reserved addresses. It makes at most 4 requests per page, so it follows up to 3 redirects, and it checks every redirect target.
- Fixed output format. Each prompt contains its schema, and the UI reads results with type checks so a slightly wrong response does not crash the page.

## Configuration

| Setting | Where | Purpose |
|---|---|---|
| `OLLAMA_API_KEY` | `.env` or Streamlit Secrets | Required. Used for the model and for web search and fetch. |
| `GITHUB_TOKEN` | `.env` or environment variable | Optional. Raises the GitHub API rate limit for link checking. |
| `MODEL` | `LLM.py` | The model name. |
| `MAX_STEPS` | `agent.py` | Maximum research loop steps. Default 6. |
| `MAX_JD_CHARS` | `main.py` | Job description length limit. Default 6000. |
| Colors, fonts, spacing | Top of `style.css` | Interface appearance. |

## Extending the project

Add a new analysis, for example a LinkedIn About section:

1. Add a schema and a prompt function in `prompts.py`.
2. Call it in `main.analyse()`. Use `_try` if its failure should not stop the run, and add its result to the dictionary returned by `run()`.
3. Add a `show_...()` function and a tab in `ui.py`.

Add a research tool:

1. Write the function in `tools.py` and return a dictionary. Return `{"error": ...}` for failures.
2. Add it to the `TOOLS` dictionary with a one-line description that lists its arguments. The research loop reads this description to decide when to use it.
3. Add a progress label for it to `STEP_TEXT` in `agent.py`.

Change the model: edit `MODEL` in `LLM.py`. To change the provider, replace `client` and `llm()` in `LLM.py`. Note that `tools.py` also uses `client` for web search and page reading, so those two functions need a replacement as well.

## Limitations

- Scanned PDFs are not supported. There is no OCR.
- Scores come from a language model. Treat them as guidance, not measurement.
- Structuring, insight, improvements and interview generation are all required. If one fails, the run fails.
- Model calls have no timeout. If the Ollama service stalls, the run waits until it answers.
- If web search itself fails (an invalid key or an exhausted quota, for example), the failure is not shown. The research simply finds nothing, and the app reports that no interview reports were found.
- Reported questions depend on what the web search returns. They come from public posts of unknown accuracy, and the question finder can miss questions or include an odd one.
- LinkedIn, YouTube, Facebook, Instagram and X pages cannot be read.
- Only the first 8 links in the resume are checked. GitHub limits requests without a token, so set `GITHUB_TOKEN` if you hit the limit.
- Job descriptions are cut to 6,000 characters.
- The research cache lives in memory and is cleared when the app restarts.
- In the cover letter box, press Ctrl+Enter or click outside the box before downloading so your edit is included.

## Troubleshooting

| Problem | Cause and fix |
|---|---|
| App shows "OLLAMA_API_KEY is missing" | Add the key to `.env` or Streamlit Secrets and restart. |
| "No readable text found" | The PDF is a scan or an image. Export a text-based PDF from your editor. |
| Warning that `style.css` was not found | The file must be in the same folder as `ui.py`, and the name must match exactly, including lowercase letters, on Linux and Streamlit Cloud. |
| "GitHub rate limit reached" in the links review | Set `GITHUB_TOKEN`, or wait and run again. |
| Deep research shows few or no questions | No interview reports were found for that company. The app falls back to trending questions and shows a warning. |

## Privacy

The text of your resume and any job description you paste are sent to the Ollama endpoint. With Deep research on, search queries that contain the company name and role are also sent to Ollama's web search, and the app fetches the pages and GitHub profiles that your resume links to. The app stores nothing beyond the current Streamlit session. Read your provider's data policy before uploading sensitive documents.
