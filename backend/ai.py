import uuid

from emergentintegrations.llm.chat import LlmChat, UserMessage

from core import LLM_KEY, LLM_MODEL


def new_chat(system: str, session: str = "task") -> LlmChat:
    return LlmChat(api_key=LLM_KEY, session_id=f"{session}-{uuid.uuid4()}", system_message=system).with_model(*LLM_MODEL)


async def ai_complete(system: str, prompt: str) -> str:
    return (await new_chat(system).send_message(UserMessage(text=prompt))).strip()
