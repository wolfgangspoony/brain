import gradio as gr
import json
from knowledge import agent, agent_ctx, memory, run_with_trace, MEMORY_FILE, load_memory

PIN = "1969"


def check_pin(pin_input):
    if pin_input == PIN:
        return gr.update(visible=True), gr.update(visible=False), ""
    else:
        return gr.update(visible=False), gr.update(visible=True), "Wrong pin."


def load_history():
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
            chatbot = gr.Chatbot(label="Brain", height=500)
            msg = gr.Textbox(label="Message", placeholder="Type here...", show_label=False)
            send_btn = gr.Button("Send")

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

            send_btn.click(respond, [msg, chatbot], [msg, chatbot])
            msg.submit(respond, [msg, chatbot], [msg, chatbot])

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
