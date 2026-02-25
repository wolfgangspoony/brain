import gradio as gr
from knowledge import (
    run_agent, 
    load_memory, 
    get_or_build_index,
    SearchTool,
    MEMORY_FILE,
    DEEPSEEK_API_KEY,
    init,
)

PIN = "1969"

# Initialize on startup
print("Initializing Brain...")
index, memory = init()
search_tool = SearchTool(index, top_k=10) if index else None
print(f"API Key configured: {bool(DEEPSEEK_API_KEY)}")
print(f"Index loaded: {bool(index)}")


def check_pin(pin_input):
    if pin_input == PIN:
        return gr.update(visible=True), gr.update(visible=False), ""
    return gr.update(visible=False), gr.update(visible=True), "Wrong pin."


def load_history():
    current_memory = load_memory()
    sessions = current_memory.get("sessions", [])
    if not sessions:
        return "No conversation history yet."
    output = []
    for i, ex in enumerate(reversed(sessions)):  # Most recent first
        output.append(f"[{len(sessions)-i}] {ex.get('timestamp', '?')}")
        output.append(f"You: {ex.get('user', '')}")
        output.append(f"Brain: {ex.get('agent', '')}")
        if ex.get('searches'):
            output.append(f"Searches: {', '.join(ex['searches'])}")
        output.append("-" * 40)
    return "\n".join(output)


with gr.Blocks(title="Brain") as demo:
    with gr.Tabs():
        with gr.TabItem("Chat"):
            chatbot = gr.Chatbot(label="Brain", height=500)
            msg = gr.Textbox(placeholder="Type here...", show_label=False)
            send_btn = gr.Button("Send")
            
            # Status indicator
            status_msg = "✅ System ready"
            if not DEEPSEEK_API_KEY:
                status_msg = "❌ Error: DEEPSEEK_API_KEY not configured"
            elif not index:
                status_msg = "⚠️ Warning: Knowledge index not loaded"
            
            status_text = gr.Markdown(status_msg)

            async def respond(message, history):
                if not message.strip():
                    return "", history
                
                if not DEEPSEEK_API_KEY:
                    history.append([message, "Error: DEEPSEEK_API_KEY not configured."])
                    return "", history
                
                if not search_tool:
                    history.append([message, "Error: Knowledge index not available."])
                    return "", history
                
                try:
                    response, searches = await run_agent(
                        search_tool, message, memory, DEEPSEEK_API_KEY
                    )
                    
                    # Format response with search indicator
                    display_response = response
                    if searches:
                        search_info = f"🔍 Searches: {', '.join(searches)}\n\n"
                        display_response = search_info + response
                    
                    history.append([message, display_response])
                    return "", history
                    
                except Exception as e:
                    import traceback
                    error_msg = f"Error: {str(e)}\n{traceback.format_exc()}"
                    print(error_msg)
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
            refresh_btn.click(fn=load_history, outputs=[history_display])
            pin_btn.click(fn=load_history, outputs=[history_display])

if __name__ == "__main__":
    demo.launch(theme=gr.themes.Soft())
