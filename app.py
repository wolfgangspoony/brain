import os
import gradio as gr
from huggingface_hub import InferenceClient

client = InferenceClient(
    base_url="https://api.deepseek.com/v1",
    api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
)


def chat(message, history):
    messages = [{"role": "system", "content": "You are a helpful assistant."}]
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": message})

    response = ""
    for chunk in client.chat.completions.create(
        model="deepseek-chat",
        messages=messages,
        max_tokens=2048,
        stream=True,
    ):
        if chunk.choices and chunk.choices[0].delta.content:
            response += chunk.choices[0].delta.content
            yield response


demo = gr.ChatInterface(
    fn=chat,
    title="Brain",
    type="messages",
    theme=gr.themes.Soft(),
)

demo.launch()
