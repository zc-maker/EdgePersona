from abc import ABC, abstractmethod
import openai
import logging


logger = logging.getLogger(__name__)


class LLM(ABC):
    @abstractmethod
    def response(self, dialogue):
        pass


class OpenAILLM(LLM):
    def __init__(self, *args, **kwargs):
        self.model_name = 'qwq:latest'
        self.api_key = 'null'
        # self.base_url = 'http://localhost:11434/v1'
        self.client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)

    def response(self, dialogue):
        # dialogue = [{"role": "user", "content": "hello"}]
        try:
            responses = self.client.chat.completions.create(  #) ChatCompletion.create(
                model=self.model_name,
                messages=dialogue,
                stream=True
            )
            for chunk in responses:
                yield chunk.choices[0].delta.content

        except Exception as e:
            logger.error(f"Error in response generation: {e}")

    def response_call(self, dialogue, functions_call):
        print("dialogue", dialogue)
        print("functions_call", functions_call)
        # dialogue = [{"role": "user", "content": "hello"}]
        try:
            responses = self.client.chat.completions.create(  #) ChatCompletion.create(
                model=self.model_name,
                messages=dialogue,
                stream=True,
            )
            for chunk in responses:
                yield chunk.choices[0].delta.content, chunk.choices[0].delta.tool_calls

        except Exception as e:
            logger.error(f"Error in response generation: {e}")


def create_instance(class_name, *args, **kwargs):
    # 获取类对象
    cls = globals().get(class_name)
    if cls:
        # 创建并返回实例
        return cls(*args, **kwargs)
    else:
        raise ValueError(f"Class {class_name} not found")


if __name__ == "__main__":
    # 创建 DeepSeekLLM 的实例
    # deepseek = create_instance("OpenAILLM", api_key="llm", base_url="http://localhost:11434/v1")
    deepseek = create_instance("OpenAILLM",'llm')
    dialogue = [{"role": "user", "content": "hello"}]

    # 打印逐步生成的响应内容
    for chunk in deepseek.response(dialogue):
        print(chunk)
