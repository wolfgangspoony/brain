import os
import gradio as gr
from huggingface_hub import InferenceClient

client = InferenceClient(
    base_url="https://api.deepseek.com/v1",
    api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
)


def get_text(content):
    """Extract plain text from Gradio 6 content blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(b.get("text", "") for b in content if b.get("type") == "text")
    return str(content)


def chat(message, history):
    messages = [{"role": "system", "content": "You are a helpful assistant."}]
    for msg in history:
        messages.append({"role": msg["role"], "content": get_text(msg["content"])})
    messages.append({"role": "user", "content": get_text(message)})

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


with gr.Blocks(theme=gr.themes.Soft(), title="Brain") as demo:
    gr.ChatInterface(fn=chat, title="Brain")

demo.launch()
