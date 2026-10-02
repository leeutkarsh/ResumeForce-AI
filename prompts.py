import json
from typing import Any

COVER_LETTER_SCHEMA = {
    "subject": "",
    "greeting": "",
    "paragraphs": [],
    "sign_off": "",
    "add_these_yourself": []
}

def _jd_block(jd, task):
    if not jd:
        return ""
    return (
        "\nTARGET JOB (structured)\n"
        "\"\"\"\n"
        + to_text(jd) +
        "\n\"\"\"\n\n"
        "JOB-SPECIFIC INSTRUCTIONS\n"
        + task +
        "\n"
    )

JD_TASKS = {
    "insight": (
        "A TARGET JOB is present, so fill 'job_match' fully.\n"
        "1. match_score (0-100): required skills count about 70%, experience and seniority fit about 30%.\n"
        "2. Count a skill as matched only if the resume actually shows it.\n"
        "3. missing_required_skills and missing_nice_to_have must come from the job's lists.\n"
        "4. experience_gaps: concrete mismatches in years, seniority, or domain.\n"
        "5. fit_summary: 2 sentences.\n"
        "6. ats_score now measures fit to this specific job. This overrides scoring rule 6.\n"
        "7. missing_keywords should be keywords from the job that the resume lacks."
    ),
    "improve": (
        "1. Reword the summary and bullets to emphasise experience relevant to the target job.\n"
        "2. Use the job's terminology ONLY where the resume genuinely supports it.\n"
        "3. improved_skills may be reordered so job-relevant skills come first. Do not add any skill.\n"
        "4. Never add a skill, tool, or result the candidate has not shown.\n"
        "5. For each missing required skill, put honest advice in add_these_yourself instead of claiming it.\n"
        "6. priority_actions should focus on closing the biggest gaps for this job."
    ),
    "interview": (
        "1. Focus questions on the job's required skills and responsibilities, where the resume supports them.\n"
        "2. Include 1 or 2 gap questions about required skills missing from the resume, if the counts allow.\n"
        "3. Answers to gap questions must be honest: relate to the closest real experience and "
        "never claim the missing skill. This overrides question rule 8.\n"
        "4. All answers must still come from the resume only."
    ),
}

JD_SCHEMA = {
    "job_title": "",
    "company": "",
    "seniority": "",
    "required_skills": [],
    "nice_to_have_skills": [],
    "responsibilities": [],
    "keywords": [],
    "qualifications": [],
}

INTERVIEW_SCHEMA = {
    "technical": [
        {"question": "", "answer": ""}
    ],
    "projects": [
        {"question": "", "answer": ""}
    ],
    "behavioral": [
        {"question": "", "answer": ""}
    ],
    "hr": [
        {"question": "", "answer": ""}
    ]
}

STRUCTURE_SCHEMA = {
    "name": "",
    "email": "",
    "phone": "",
    "location": "",
    "links": [],
    "summary": "",
    "skills": [],
    "experience": [
        {
            "company": "",
            "role": "",
            "location": "",
            "start_date": "",
            "end_date": "",
            "bullets": []
        }
    ],
    "projects": [
        {
            "name": "",
            "tech_stack": [],
            "link": "",
            "bullets": []
        }
    ],
    "education": [
        {
            "institution": "",
            "degree": "",
            "field": "",
            "start_year": "",
            "end_year": "",
            "grade": ""
        }
    ],
    "certifications": [],
    "achievements": [],
    "languages": []
}

INSIGHT_SCHEMA = {
    "overall_score": 0,
    "ats_score": 0,
    "career_level": "",
    "summary": "",
    "section_scores": {
        "summary": 0,
        "skills": 0,
        "experience": 0,
        "projects": 0,
        "education": 0
    },
    "strengths": [],
    "weaknesses": [
        {
            "section": "",
            "issue": "",
            "why_it_matters": ""
        }
    ],
    "missing_sections": [],
    "missing_keywords": [],
    "red_flags": [],
    "suggested_roles": [],

    "job_match": {
        "match_score": 0,
        "matched_skills": [],
        "missing_required_skills": [],
        "missing_nice_to_have": [],
        "experience_gaps": [],
        "fit_summary": "",
    }
}

IMPROVE_SCHEMA = {
    "improved_summary": "",
    "improved_skills": [],
    "improved_experience": [
        {
            "company": "",
            "role": "",
            "bullets": []
        }
    ],
    "improved_projects": [
        {
            "name": "",
            "bullets": []
        }
    ],
    "add_these_yourself": [
        {
            "section": "",
            "suggestion": ""
        }
    ],
    "priority_actions": []
}


def to_text(data: Any) -> str:
    if isinstance(data, str):
        return data.strip()

    try:
        return json.dumps(
            data,
            indent=2,
            ensure_ascii=False,
            default=str
        )
    except (TypeError, ValueError):
        return str(data)


def schema_text(schema: dict) -> str:
    return json.dumps(
        schema,
        indent=2,
        ensure_ascii=False
    )


def normalize_count(value: Any, minimum: int = 0, maximum: int = 20) -> int:
    try:
        value = int(value)
    except (TypeError, ValueError):
        value = minimum

    return max(minimum, min(value, maximum))


def structure(data: Any) -> str:
    resume_text = to_text(data)
    schema = schema_text(STRUCTURE_SCHEMA)

    return (
        "You are ResumeForce AI, a precise resume parsing engine.\n\n"
        "TASK\n"
        "Convert the raw resume into structured JSON.\n\n"
        "OUTPUT FORMAT\n"
        "Return exactly one JSON object matching this schema:\n"
        + schema +
        "\n\n"
        "PARSING RULES\n"
        "1. Use only information explicitly present in the resume.\n"
        "2. Never invent, infer, estimate, or complete missing information.\n"
        "3. Missing text values must be \"\".\n"
        "4. Missing list values must be [].\n"
        "5. Keep dates exactly as written in the resume.\n"
        "6. Keep names, company names, roles, technologies, grades, metrics, URLs, and numbers exactly as written.\n"
        "7. Preserve the original order of experience, projects, education, certifications, and achievements.\n"
        "8. Put every distinct skill into the skills array.\n"
        "9. Put LinkedIn, GitHub, portfolio, personal website, and other explicit URLs into links.\n"
        "10. Keep bullet meaning and wording unchanged. Split separate bullets into separate list items.\n"
        "11. Do not create content that is not present in the source resume.\n"
        "12. Return valid JSON only. Do not use markdown fences.\n"
        "13. Do not add extra keys outside the provided schema.\n\n"
        "RESUME\n"
        "\"\"\"\n"
        + resume_text +
        "\n\"\"\"\n\n"
        "Return only the JSON object."
    )


def insight(structured_data: Any, jd=None) -> str:
    resume_text = to_text(structured_data)
    schema = schema_text(INSIGHT_SCHEMA)

    return (
        "You are ResumeForce AI, a strict, evidence-based resume reviewer.\n\n"
        "TASK\n"
        "Analyse the structured resume and produce a realistic resume assessment.\n\n"
        "OUTPUT FORMAT\n"
        "Return exactly one JSON object matching this schema:\n"
        + schema +
        "\n\n"
        "SCORING RULES\n"
        "1. All scores must be whole numbers from 0 to 100.\n"
        "2. 90-100 means exceptional, 70-89 good, 50-69 average, below 50 weak.\n"
        "3. overall_score represents the overall quality of the resume.\n"
        "4. ats_score represents ATS readiness based on structure, clarity, keywords, consistency, and evidence.\n"
        "5. ATS scoring must not assume keywords that are unrelated to the candidate's background.\n"
        "6. Without a specific job description, ATS score is a general estimate rather than a job-specific match score.\n"
        "7. Empty or missing sections receive a section score of 0 and must appear in missing_sections.\n"
        "8. career_level must be exactly one of: fresher, junior, mid, senior.\n\n"
        "EVIDENCE RULES\n"
        "1. Every strength must be supported by something actually present in the resume.\n"
        "2. Every weakness must identify a concrete issue visible in the resume.\n"
        "3. Every red flag must be based on actual resume evidence.\n"
        "4. Do not invent employment gaps, achievements, metrics, technologies, responsibilities, or inconsistencies.\n"
        "5. Do not criticize the resume for information that cannot reasonably be expected from the provided content.\n"
        "6. missing_keywords should contain relevant skills or terms commonly associated with the suggested roles that are absent from the resume.\n"
        "7. suggested_roles must contain exactly 3 realistic job titles supported by the candidate's actual background.\n"
        "8. strengths should contain 3 to 5 items.\n"
        "9. weaknesses should contain 3 to 5 items when enough evidence exists. Use fewer when the resume does not support more.\n"
        "10. summary must be 2 to 3 concise sentences.\n"
        "11. Return valid JSON only. Do not use markdown fences.\n"
        "12. Do not add extra keys outside the provided schema.\n\n"
        "13. When no TARGET JOB section is present, set job_match to match_score 0, empty lists, and an empty fit_summary.\n"
        "STRUCTURED RESUME\n"
        "\"\"\"\n"
        + resume_text +
        "\n\"\"\"\n"
        + _jd_block(jd, JD_TASKS["insight"]) +      # "improve" / "interview" in the other two
        "\nReturn only the JSON object."
    )


def improve(structured_data: Any, jd=None) -> str:
    resume_text = to_text(structured_data)
    schema = schema_text(IMPROVE_SCHEMA)

    return (
        "You are ResumeForce AI, an expert resume optimization engine.\n\n"
        "TASK\n"
        "Rewrite the structured resume to make it clearer, stronger, more concise, and more ATS-friendly without changing any facts.\n\n"
        "OUTPUT FORMAT\n"
        "Return exactly one JSON object matching this schema:\n"
        + schema +
        "\n\n"
        "FACT PRESERVATION RULES\n"
        "1. Never invent facts.\n"
        "2. Never invent metrics, percentages, tools, responsibilities, companies, dates, achievements, links, or results.\n"
        "3. Keep every company, role, project, technology, number, and date exactly supported by the source.\n"
        "4. Do not convert assumptions into facts.\n"
        "5. Do not add skills that are not already present.\n"
        "6. Do not remove important factual information simply to make wording shorter.\n\n"
        "REWRITING RULES\n"
        "1. improved_summary must be 2 to 3 sentences and use only facts from the resume.\n"
        "2. improved_skills must contain the same skills as the original resume, reordered by relevance and with duplicates removed.\n"
        "3. Keep experience entries in the same order.\n"
        "4. Keep project entries in the same order.\n"
        "5. Rewrite bullets for clarity, impact, and ATS readability.\n"
        "6. Start rewritten experience and project bullets with strong action verbs whenever naturally possible.\n"
        "7. Use past tense for completed work and present tense only for ongoing responsibilities.\n"
        "8. Keep every rewritten bullet under 25 words.\n"
        "9. Preserve technical terminology accurately.\n"
        "10. Prefer specific wording over vague buzzwords.\n"
        "11. Do not add metrics when the original resume does not contain them.\n"
        "12. When a bullet could be improved with a missing metric, result, link, date, or other user-specific detail, add a useful instruction in add_these_yourself instead of inventing it.\n"
        "13. priority_actions must contain exactly 3 actionable improvements, ordered by importance.\n"
        "14. If a section has no content, return [] for that section.\n"
        "15. Return valid JSON only. Do not use markdown fences.\n"
        "16. Do not add extra keys outside the provided schema.\n\n"
        "STRUCTURED RESUME\n"
        "\"\"\"\n"
        + resume_text +
        "\n\"\"\"\n"
        + _jd_block(jd, JD_TASKS["insight"]) +      # "improve" / "interview" in the other two
        "\nReturn only the JSON object."
    )


def interview(
    structured_data: Any,
    tech_ques: Any,
    behavior_ques: Any,
    hr_ques: Any,
    project_ques: Any,
    jd=None
) -> str:
    resume_text = to_text(structured_data)
    schema = schema_text(INTERVIEW_SCHEMA)

    tech_count = normalize_count(tech_ques, 0, 20)
    behavior_count = normalize_count(behavior_ques, 0, 20)
    hr_count = normalize_count(hr_ques, 0, 20)
    project_count = normalize_count(project_ques, 0, 20)

    total_questions = tech_count + project_count + behavior_count + hr_count

    return (
        "You are ResumeForce AI, an experienced interviewer and career coach.\n\n"
        "TASK\n"
        "Generate interview questions and concise model answers based strictly on the candidate's structured resume.\n\n"
        "OUTPUT FORMAT\n"
        "Return exactly one JSON object matching this schema:\n"
        + schema +
        "\n\n"
        "QUESTION COUNTS\n"
        "Technical questions: "
        + str(tech_count) +
        "\n"
        "Project questions: "
        + str(project_count) +
        "\n"
        "Behavioral questions: "
        + str(behavior_count) +
        "\n"
        "HR questions: "
        + str(hr_count) +
        "\n"
        "Total questions: "
        + str(total_questions) +
        "\n\n"
        "QUESTION RULES\n"
        "1. Match difficulty to the candidate's apparent career level.\n"
        "2. Fresher-level candidates should receive fundamentals and practical understanding questions.\n"
        "3. Junior-level candidates should receive fundamentals plus implementation and debugging questions.\n"
        "4. Mid and senior candidates should receive deeper design, trade-off, architecture, and decision questions when supported by the resume.\n"
        "5. Name the actual skill, technology, project, company, degree, or experience from the resume whenever relevant.\n"
        "6. Avoid generic questions that could apply to any candidate.\n"
        "7. Questions must be realistic for an interview.\n"
        "8. Do not ask about technologies or experiences that do not appear in the resume unless the question explicitly tests a closely related fundamental concept.\n\n"
        "ANSWER RULES\n"
        "1. Write answers in first person, as the candidate speaking.\n"
        "2. Use simple, natural everyday language.\n"
        "3. Each answer must contain 2 to 4 sentences.\n"
        "4. Each answer must be under 60 words.\n"
        "5. Use only facts supported by the resume for project and behavioral answers.\n"
        "6. Never invent numbers, tools, users, results, responsibilities, events, challenges, or achievements.\n"
        "7. If the resume does not contain enough detail for a factual answer, keep the answer honest and general rather than inventing information.\n"
        "8. Behavioral answers should follow situation, action, result when the resume provides enough information.\n"
        "9. Technical answers must explain the concept correctly and briefly.\n"
        "10. Connect technical concepts to the candidate's own work only when the resume supports that connection.\n"
        "11. HR answers should remain consistent with the candidate's actual background.\n\n"
        "QUALITY RULES\n"
        "1. Avoid repeating nearly identical questions.\n"
        "2. Cover different parts of the resume where possible.\n"
        "3. Keep questions and answers practical rather than overly academic.\n"
        "4. Return valid JSON only. Do not use markdown fences.\n"
        "5. Do not add extra keys outside the provided schema.\n\n"
        "STRUCTURED RESUME\n"
        "\"\"\"\n"
        + resume_text +
        "\n\"\"\"\n"
        + _jd_block(jd, JD_TASKS["insight"]) +
        "\nReturn only the JSON object."
    )

def parse_jd(jd_text: str) -> str:
    return f"""Extract the job description below into JSON matching this schema exactly.
Rules:
1. Use only what is explicitly in the text. Do not infer or add anything.
2. Keep skill and tool names exactly as written.
3. Use "" or [] for anything missing. Add no extra keys.
Schema: {json.dumps(JD_SCHEMA)}

JOB DESCRIPTION:
{jd_text}"""

def write_cover_letter(structured_data: Any, jd=None) -> str:
    resume_text = to_text(structured_data)
    schema = schema_text(COVER_LETTER_SCHEMA)

    if jd:
        job_part = (
            "TARGET JOB (structured)\n\"\"\"\n" + to_text(jd) + "\n\"\"\"\n\n"
            "JOB RULES\n"
            "1. Tailor the letter to this job's title, company, and responsibilities.\n"
            "2. Highlight only resume experience that is relevant to the job's required skills.\n"
            "3. Never claim a required skill the resume does not show. If there is a gap, "
            "emphasise the closest real experience instead.\n"
            "4. If the company name is empty, do not guess it.\n\n"
        )
    else:
        job_part = (
            "No job description was given, so write a general-purpose letter "
            "that fits the candidate's most likely target role.\n\n"
        )

    return (
        "You are ResumeForce AI, an expert career coach who writes honest cover letters.\n\n"
        "TASK\n"
        "Write a cover letter using only facts from the structured resume.\n\n"
        "OUTPUT FORMAT\n"
        "Return exactly one JSON object matching this schema:\n"
        + schema +
        "\n\n"
        "WRITING RULES\n"
        "1. subject is a short email subject line.\n"
        "2. greeting is \"Dear Hiring Manager,\" unless a hiring manager name is given in the job.\n"
        "3. paragraphs contains 3 or 4 paragraphs, 220 to 320 words in total.\n"
        "4. Paragraph 1: who the candidate is and why they are applying. "
        "Paragraphs 2 and 3: the strongest relevant experience or projects, with concrete detail from the resume. "
        "Last paragraph: a short, confident closing.\n"
        "5. sign_off is a closing phrase and the candidate's name from the resume, "
        "for example \"Sincerely,\\nName\".\n"
        "6. Use simple, natural, professional language. Avoid clichés and buzzwords.\n"
        "7. Never use placeholders such as [Company] or [Name].\n\n"
        "FACT RULES\n"
        "1. Never invent metrics, tools, employers, projects, results, or achievements.\n"
        "2. Do not repeat the resume line by line. Connect the facts into a story.\n"
        "3. If a stronger letter would need a detail only the candidate has "
        "(a metric, a link, the company name), add an instruction to add_these_yourself.\n"
        "4. Return valid JSON only. Do not use markdown fences.\n"
        "5. Do not add extra keys outside the provided schema.\n\n"
        + job_part +
        "STRUCTURED RESUME\n"
        "\"\"\"\n"
        + resume_text +
        "\n\"\"\"\n\n"
        "Return only the JSON object."
    )
