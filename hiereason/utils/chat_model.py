from langchain import LLMChain
from langchain.prompts import ChatPromptTemplate

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_community.chat_models import ChatOllama

import re

def chat_model(config, stop_on_newline=False):
    if config.langchain.select == "openai":
        return ChatOpenAI(
            model=config.langchain.openai.chat_model,
            openai_api_key=config.langchain.openai.api_key,
            temperature=config.langchain.openai.temperature,
            model_kwargs={"stop":["\n"]} if stop_on_newline else {}
        )
    elif config.langchain.select == "anthropic":
        return ChatAnthropic(
            model=config.langchain.anthropic.chat_model,
            api_key=config.langchain.anthropic.api_key,
            temperature=config.langchain.anthropic.temperature,
            # model_kwargs={"stop_sequences":["\n"]} if stop_on_newline else {}
        )
    elif config.langchain.select == "ollama":
        return ChatOllama(
            model=config.langchain.ollama.chat_model,
            temperature=config.langchain.openai.temperature,
            stop=["\n", "<|eot_id|>"] if stop_on_newline else None
        )

def run_prompt(prompt, data, llm):
    if isinstance(llm, ChatOpenAI):
        system_prompt = "You are an AI assistant that completes the user query following the examples."
    if isinstance(llm, ChatAnthropic):
        system_prompt = "You are an AI assistant. Complete the last example without any unnecessary outputs."
        if "A." in prompt: # Least to most
            system_prompt += " Answer with only one sentence."
        elif "read?\nAnswer: 42." in prompt or "rest?\nAnswer: 36." in prompt: # Standard + GSM8k/MAWPS
            system_prompt += " Print only the answer number without any chain-of-thought outputs."
        elif "#### Yes" in prompt: # CoT - bool
            system_prompt += " Think step by step, and end your answer with `#### Yes` or `#### No`."
        elif "####" in prompt: # CoT - numeric
            system_prompt += " Think step by step, and end your answer with `#### (number)` . (ex. #### 62)"
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
        if "A." in prompt: # Least to most
            system_prompt += " Answer with only one sentence."
        elif "read?\nAnswer: 42." in prompt or "rest?\nAnswer: 36." in prompt: # Standard + GSM8k/MAWPS
            system_prompt += " Print only the answer number without any chain-of-thought outputs."
        elif "#### yes" in prompt:
            system_prompt += " End your answer with `#### Yes` or `#### No`."
        elif "####" in prompt:
            system_prompt += " End your answer with #### (Answer)."
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