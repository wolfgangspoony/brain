import gradio as gr
from knowledge import agent, agent_ctx, memory, run_with_trace


def get_text(content):
    """Extract plain text from Gradio 6 content blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(b.get("text", "") for b in content if b.get("type") == "text")
    return str(content)


async def chat(message, history):
    user_text = get_text(message)

    if agent is None or agent_ctx is None:
        return "Error: System failed to initialize. Check the logs."

    try:
        reasoning, response, searches = await run_with_trace(
            agent, agent_ctx, user_text, memory
        )

        # Build output with Glass Box reasoning trace
        output = ""

        if searches:
            output += "**🔍 Searches:**\n"
            for i, s in enumerate(searches):
                output += f"- `{s}`\n"
            output += "\n"

        if reasoning:
            output += "**💭 Reasoning Trace:**\n"
            for step in reasoning:
                if step["type"] == "tool_call":
                    output += f"> **Tool:** {step['tool']}\n"
                    output += f"> **Found:** {step['result_preview']}\n\n"
            output += "---\n\n"

        output += response
        return output

    except Exception as e:
        return f"Error: {str(e)}"


with gr.Blocks(title="Brain") as demo:
    gr.ChatInterface(fn=chat, title="Brain")

demo.launch(theme=gr.themes.Soft())
