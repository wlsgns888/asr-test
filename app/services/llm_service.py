from dataclasses import dataclass

from openai import OpenAI
from openai.types.chat import ChatCompletionMessageParam

from app.config import LLMProvider, Settings

FIXED_MINUTES_SAFETY_PROMPT = (
    "아래 음성 변환 원본을 기반으로 회의록을 작성한다.\n"
    "내용을 과장하거나 없는 내용을 추가하지 않는다.\n"
    '불명확한 내용은 "확인 필요"로 표시한다.'
)


class LLMConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class LLMService:
    settings: Settings

    def generate_minutes(
        self,
        transcript: str,
        template: str,
        summary_prompt: str,
    ) -> str:
        if self.settings.llm_provider is LLMProvider.FAKE:
            return self._generate_fake_minutes(transcript, template, summary_prompt)
        if self.settings.llm_api_key.get_secret_value() == "":
            raise LLMConfigurationError
        client = OpenAI(
            base_url=self.settings.llm_base_url,
            api_key=self.settings.llm_api_key.get_secret_value(),
        )
        response = client.chat.completions.create(
            model=self.settings.llm_model,
            messages=self.build_messages(transcript, template, summary_prompt),
        )
        content = response.choices[0].message.content
        if content is None:
            raise LLMConfigurationError
        return content

    def _generate_fake_minutes(
        self,
        transcript: str,
        template: str,
        summary_prompt: str,
    ) -> str:
        return (
            "# 회의록\n\n"
            "## 회의 개요\n"
            f"- 변환 원본 요약: {transcript}\n\n"
            "## 고정 지침\n"
            f"{FIXED_MINUTES_SAFETY_PROMPT}\n\n"
            "## 요약 지침\n"
            f"{summary_prompt}\n\n"
            "## 주요 논의사항\n"
            "- 확인 필요\n\n"
            "## 결정사항\n"
            "- 확인 필요\n\n"
            "## 액션아이템\n"
            "- 확인 필요\n\n"
            "## 후속 확인사항\n"
            f"- 적용 템플릿:\n{template}\n"
        )

    def _prompt(self, transcript: str, template: str, summary_prompt: str) -> str:
        return (
            f"[요약 지침]\n{summary_prompt}\n\n"
            f"[출력 형식]\n{template}\n\n"
            f"[음성 변환 원본]\n{transcript}"
        )

    def build_messages(
        self,
        transcript: str,
        template: str,
        summary_prompt: str,
    ) -> list[ChatCompletionMessageParam]:
        return [
            {
                "role": "system",
                "content": (
                    f"너는 사내 회의록 작성 전문가다.\n\n{FIXED_MINUTES_SAFETY_PROMPT}"
                ),
            },
            {
                "role": "user",
                "content": self._prompt(transcript, template, summary_prompt),
            },
        ]
