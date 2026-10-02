import json
from typing import Any

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
    "suggested_roles": []
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


def insight(structured_data: Any) -> str:
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
        "STRUCTURED RESUME\n"
        "\"\"\"\n"
        + resume_text +
        "\n\"\"\"\n\n"
        "Return only the JSON object."
    )


def improve(structured_data: Any) -> str:
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
        "\n\"\"\"\n\n"
        "Return only the JSON object."
    )


def interview(
    structured_data: Any,
    tech_ques: Any,
    behavior_ques: Any,
    hr_ques: Any,
    project_ques: Any
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
        "\n\"\"\"\n\n"
        "Return only the JSON object."
    )