from langchain import LLMChain
from langchain.prompts import ChatPromptTemplate

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_community.chat_models import ChatOllama

import re

def chat_model(config):
    if config.langchain.select == "openai":
        return ChatOpenAI(
            model=config.langchain.openai.chat_model,
            openai_api_key=config.langchain.openai.api_key,
            temperature=config.langchain.openai.temperature
        )
    elif config.langchain.select == "anthropic":
        return ChatAnthropic(
            model=config.langchain.anthropic.chat_model,
            api_key=config.langchain.anthropic.api_key,
            temperature=config.langchain.anthropic.temperature
        )
    elif config.langchain.select == "ollama":
        return ChatOllama(
            model=config.langchain.ollama.chat_model
            # temperature=config.langchain.openai.temperature
        )

def run_prompt(prompt, data, llm):
    if isinstance(llm, ChatOpenAI):
        system_prompt = "You are an AI assistant that completes the user query following the examples."
    if isinstance(llm, ChatAnthropic):
        system_prompt = "You are an AI assistant. Complete the last example without any unnecessary outputs."
        # Reformat example tags
        last_example = True
        for example_i in range(10, 0, -1):
            example_tag = f"Example {example_i}"
            if example_tag in prompt:
                if last_example:
                    last_example = False
                    prompt = prompt.replace("\n" + example_tag, "</example>\n")
                elif example_i > 1:
                # if example_i > 1:
                    prompt = prompt.replace("\n" + example_tag, "</example>\n\n<example>")
                else: # example_i == 1
                    prompt = prompt.replace(example_tag, "<example>")
        # print(prompt)
    if isinstance(llm, ChatOllama):
        system_prompt = "You are an AI assistant. Complete the last example without any unnecessary outputs."
        prompt = re.sub("Example [0-9]+\n", "", prompt)

    chain = LLMChain(
        llm=llm,
        prompt=ChatPromptTemplate.from_messages([
            ("system", system_prompt), ("human", prompt)
        ])
    )
    result = str(chain.run(data))
    # print(result); exit()
    return result