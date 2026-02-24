import gradio as gr
from knowledge import agent, run_agent_async


def get_text(content):
    """Extract plain text from Gradio 6 content blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(b.get("text", "") for b in content if b.get("type") == "text")
    return str(content)


async def chat(message, history):
    user_text = get_text(message)

    if agent is None:
        return "Error: Agent failed to initialize. Check the logs."

    try:
        response = await run_agent_async(agent, user_text)
        return response
    except Exception as e:
        return f"Error: {str(e)}"


with gr.Blocks(title="Brain") as demo:
    gr.ChatInterface(fn=chat, title="Brain")

demo.launch(theme=gr.themes.Soft())
