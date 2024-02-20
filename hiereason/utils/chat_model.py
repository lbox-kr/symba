from langchain.chat_models import ChatOpenAI

def openai_chat_model(config):
    return ChatOpenAI(
        model=config.langchain.openai.chat_model,
        openai_api_key=config.langchain.openai.api_key,
        temperature=config.langchain.openai.temperature
    )
