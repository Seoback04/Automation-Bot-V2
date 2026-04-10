from __future__ import annotations

from textwrap import dedent

import requests

from jobbot.config.models import OllamaSettings, ProfileData


class OllamaClient:
    def __init__(self, settings: OllamaSettings) -> None:
        self.settings = settings

    @property
    def enabled(self) -> bool:
        return self.settings.enabled

    def analyze_job_description(self, job: dict, profile: ProfileData) -> str:
        fallback = self._fallback_analysis(job, profile)
        if not self.enabled:
            return fallback

        prompt = dedent(
            f"""
            Analyze the job description for fit, risks, and talking points.
            Keep it concise and structured for a local job automation dashboard.

            Candidate summary:
            {profile.summary}

            Skills:
            {", ".join(profile.skills)}

            Job title: {job.get("title", "")}
            Company: {job.get("company", "")}
            Location: {job.get("location", "")}
            Description:
            {job.get("description", "")}
            """
        ).strip()
        return self._generate(prompt, fallback)

    def generate_cover_letter(self, job: dict, profile: ProfileData) -> str:
        fallback = self._fallback_cover_letter(job, profile)
        if not self.enabled:
            return fallback

        prompt = dedent(
            f"""
            Draft a concise, tailored cover letter in plain text.
            Make it specific, professional, and realistic.

            Candidate:
            Name: {profile.full_name}
            Summary: {profile.summary}
            Skills: {", ".join(profile.skills)}

            Job:
            Title: {job.get("title", "")}
            Company: {job.get("company", "")}
            Description:
            {job.get("description", "")}
            """
        ).strip()
        return self._generate(prompt, fallback)

    def answer_application_question(self, question: str, job: dict, profile: ProfileData) -> str:
        for key, answer in profile.custom_answers.items():
            if key.lower() in question.lower():
                return answer

        fallback = (
            f"{profile.full_name} is interested in the {job.get('title', 'role')} position "
            f"and brings relevant experience in {', '.join(profile.skills[:3])}."
        )
        if not self.enabled:
            return fallback

        prompt = dedent(
            f"""
            Answer this job application question briefly and professionally.

            Question:
            {question}

            Candidate summary:
            {profile.summary}

            Skills:
            {", ".join(profile.skills)}

            Job details:
            Title: {job.get("title", "")}
            Company: {job.get("company", "")}
            Description:
            {job.get("description", "")}
            """
        ).strip()
        return self._generate(prompt, fallback)

    def healthcheck(self) -> tuple[bool, str]:
        if not self.enabled:
            return True, "Ollama disabled in settings."
        try:
            response = requests.get(
                f"{self.settings.base_url.rstrip('/')}/api/tags",
                timeout=self.settings.request_timeout_seconds,
            )
            response.raise_for_status()
            return True, "Ollama reachable."
        except requests.RequestException as exc:
            return False, f"Ollama unavailable: {exc}"

    def _generate(self, prompt: str, fallback: str) -> str:
        try:
            response = requests.post(
                f"{self.settings.base_url.rstrip('/')}/api/generate",
                json={
                    "model": self.settings.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": self.settings.temperature},
                },
                timeout=self.settings.request_timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
            generated = payload.get("response", "").strip()
            return generated or fallback
        except requests.RequestException:
            return fallback

    def _fallback_analysis(self, job: dict, profile: ProfileData) -> str:
        lines = [
            f"Role fit summary for {job.get('title', 'this role')}:",
            f"- Matches candidate skills: {', '.join(profile.skills[:5]) or 'No skills listed'}",
            f"- Candidate location: {profile.location or 'Not set'}",
            f"- Review work authorization and salary expectations before submission.",
        ]
        return "\n".join(lines)

    def _fallback_cover_letter(self, job: dict, profile: ProfileData) -> str:
        return dedent(
            f"""
            Dear Hiring Team,

            I am interested in the {job.get('title', 'position')} role at {job.get('company', 'your company')}.
            My background includes {profile.summary or 'hands-on work in software delivery and automation'}, and I would bring practical experience in {', '.join(profile.skills[:4]) or 'relevant technical skills'}.

            I would welcome the chance to contribute and discuss how my experience aligns with your team.

            Kind regards,
            {profile.full_name or 'Candidate'}
            """
        ).strip()
