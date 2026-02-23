import os
import gradio as gr
from huggingface_hub import InferenceClient
from knowledge import kb

client = InferenceClient(
    base_url="https://api.deepseek.com/v1",
    api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
)

# Index the knowledge base at startup
kb.index()


def get_text(content):
    """Extract plain text from Gradio 6 content blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(b.get("text", "") for b in content if b.get("type") == "text")
    return str(content)


SYSTEM_BASE = """You are a knowledgeable assistant with access to the user's personal knowledge base.
When relevant context from their notes is provided below, use it to ground your responses.
If your answer draws on their notes, mention which source it came from.
If the notes don't cover the topic, just answer normally — don't pretend you have context you don't."""


def chat(message, history):
    user_text = get_text(message)

    # Retrieve relevant chunks from the knowledge base
    hits = kb.search(user_text, k=5)

    system = SYSTEM_BASE
    if hits:
        context = "\n\n---\n\n".join(h["content"] for h in hits)
        sources = ", ".join(set(h["source"] for h in hits))
        system += f"\n\n=== RELEVANT CONTEXT FROM USER'S NOTES ===\n(Sources: {sources})\n\n{context}\n\n=== END CONTEXT ==="

    messages = [{"role": "system", "content": system}]
    for msg in history:
        messages.append({"role": msg["role"], "content": get_text(msg["content"])})
    messages.append({"role": "user", "content": user_text})

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
