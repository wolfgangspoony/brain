import gradio as gr
import json
from knowledge import agent, agent_ctx, memory, run_with_trace, MEMORY_FILE, load_memory

PIN = "1969"


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
        return response

    except Exception as e:
        return f"Error: {str(e)}"


def check_pin(pin_input):
    if pin_input == PIN:
        return gr.update(visible=True), gr.update(visible=False), ""
    else:
        return gr.update(visible=False), gr.update(visible=True), "Wrong pin."


def load_history():
    # Reload from disk to get latest
    current_memory = load_memory()
    sessions = current_memory.get("sessions", [])

    if not sessions:
        return f"No conversation history yet.\n\nLooking at: {MEMORY_FILE}\nExists: {MEMORY_FILE.exists()}"

    output = []
    for i, ex in enumerate(sessions):
        timestamp = ex.get("timestamp", "?")
        user_msg = ex.get("user", "")
        agent_msg = ex.get("agent", "")
        output.append(f"[{i+1}] {timestamp}")
        output.append(f"You: {user_msg}")
        output.append(f"Brain: {agent_msg}")
        output.append("-" * 40)

    return "\n".join(output)


with gr.Blocks(title="Brain") as demo:
    with gr.Tabs():
        with gr.TabItem("Chat"):
            gr.ChatInterface(fn=chat, title="Brain")

        with gr.TabItem("History"):
            with gr.Column(visible=True) as pin_section:
                gr.Markdown("Enter pin to view conversation history:")
                pin_input = gr.Textbox(label="Pin", type="password")
                pin_btn = gr.Button("Submit")
                pin_error = gr.Markdown("")

            with gr.Column(visible=False) as history_section:
                refresh_btn = gr.Button("Refresh")
                history_display = gr.Textbox(
                    label="Conversation History",
                    lines=30,
                    max_lines=50,
                    interactive=False
                )

            pin_btn.click(
                fn=check_pin,
                inputs=[pin_input],
                outputs=[history_section, pin_section, pin_error]
            )

            def show_history():
                return load_history()

            refresh_btn.click(fn=show_history, outputs=[history_display])
            pin_btn.click(fn=show_history, outputs=[history_display])

demo.launch(theme=gr.themes.Soft())
