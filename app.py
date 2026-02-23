import gradio as gr
from knowledge import agent, run_agent


def get_text(content):
    """Extract plain text from Gradio 6 content blocks."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(b.get("text", "") for b in content if b.get("type") == "text")
    return str(content)


def chat(message, history):
    user_text = get_text(message)

    if agent is None:
        return "Error: Agent failed to initialize. Check the logs."

    try:
        reasoning, response, sources = run_agent(agent, user_text)

        # Build output with reasoning trace
        output = ""

        # Show search queries the agent made
        if sources:
            output += "**🔍 Search Trace:**\n"
            for i, s in enumerate(sources):
                output += f"- Query {i+1}: `{s['query']}`\n"
            output += "\n"

        # Show full reasoning trace (collapsed)
        if reasoning.strip():
            output += "**💭 Reasoning:**\n"
            # Clean up the verbose output for readability
            lines = reasoning.strip().split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                if line.startswith('Thought:'):
                    output += f"\n> **Thought:** {line[8:].strip()}\n"
                elif line.startswith('Action:'):
                    output += f"> **Action:** {line[7:].strip()}\n"
                elif line.startswith('Observation:'):
                    # Truncate long observations
                    obs = line[12:].strip()
                    if len(obs) > 300:
                        obs = obs[:300] + "..."
                    output += f"> **Observation:** {obs}\n"
                elif line.startswith('Answer:'):
                    pass  # Skip, we show the full response below
            output += "\n---\n\n"

        output += response
        return output

    except Exception as e:
        return f"Error: {str(e)}"


with gr.Blocks(title="Brain") as demo:
    gr.ChatInterface(fn=chat, title="Brain")

demo.launch(theme=gr.themes.Soft())
