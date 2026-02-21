import gradio as gr
from huggingface_hub import InferenceClient

import config

# Simple client setup
if config.DEEPSEEK_API_KEY:
    client = InferenceClient(
        base_url="https://api.deepseek.com/v1",
        api_key=config.DEEPSEEK_API_KEY
    )
    model = "deepseek-chat"
elif config.HF_TOKEN:
    client = InferenceClient(token=config.HF_TOKEN)
    model = config.MODEL
else:
    client = InferenceClient()
    model = config.MODEL


def respond(message, history):
    messages = [{"role": "system", "content": "You are a helpful assistant."}]

    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": message})

    response = ""
    for chunk in client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=2048,
        stream=True
    ):
        if chunk.choices and chunk.choices[0].delta.content:
            response += chunk.choices[0].delta.content
            yield response


demo = gr.ChatInterface(
    fn=respond,
    chatbot=gr.Chatbot(height=500),
    textbox=gr.Textbox(placeholder="Type a message...", container=False, scale=7),
    title="Brain",
    description="A simple chatbot",
    examples=["Hello", "What can you help me with?", "Tell me a joke"],
    cache_examples=False,
)

if __name__ == "__main__":
    demo.launch()
