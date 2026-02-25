import gradio as gr
import json
from knowledge import agent, agent_ctx, memory, run_with_trace, MEMORY_FILE

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
    if not MEMORY_FILE.exists():
        return "No conversation history yet."

    try:
        data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
        sessions = data.get("sessions", [])

        if not sessions:
            return "No conversation history yet."

        output = []
        for i, ex in enumerate(sessions):
            timestamp = ex.get("timestamp", "?")
            user_msg = ex.get("user", "")
            agent_msg = ex.get("agent", "")
            output.append(f"--- Exchange {i+1} [{timestamp}] ---")
            output.append(f"User: {user_msg}")
            output.append(f"Response: {agent_msg}")
            output.append("")

        return "\n".join(output)
    except Exception as e:
        return f"Error loading history: {e}"


def load_history_for_chat():
    """Load conversation history as chat format for resuming."""
    if not MEMORY_FILE.exists():
        return []

    try:
        data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
        sessions = data.get("sessions", [])

        if not sessions:
            return []

        # Convert to Gradio chat format: list of [user, assistant] pairs
        history = []
        for ex in sessions:
            user_msg = ex.get("user", "")
            agent_msg = ex.get("agent", "")
            history.append([user_msg, agent_msg])

        return history
    except Exception:
        return []


with gr.Blocks(title="Brain") as demo:
    with gr.Tabs():
        with gr.TabItem("Chat"):
            chatbot = gr.Chatbot(label="Brain", height=500)
            msg = gr.Textbox(label="Message", placeholder="Type here...")
            with gr.Row():
                submit_btn = gr.Button("Send")
                resume_btn = gr.Button("Resume Previous Conversation")
                clear_btn = gr.Button("Clear")

            async def respond(message, history):
                if not message.strip():
                    return "", history

                if agent is None or agent_ctx is None:
                    history.append([message, "Error: System failed to initialize."])
                    return "", history

                try:
                    reasoning, response, searches = await run_with_trace(
                        agent, agent_ctx, message, memory
                    )
                    history.append([message, response])
                    return "", history
                except Exception as e:
                    history.append([message, f"Error: {str(e)}"])
                    return "", history

            def resume_conversation():
                return load_history_for_chat()

            def clear_chat():
                return []

            submit_btn.click(respond, [msg, chatbot], [msg, chatbot])
            msg.submit(respond, [msg, chatbot], [msg, chatbot])
            resume_btn.click(resume_conversation, outputs=[chatbot])
            clear_btn.click(clear_chat, outputs=[chatbot])

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
