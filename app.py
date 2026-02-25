import gradio as gr
import time
from knowledge import (
    run_agent, 
    load_memory, 
    get_or_build_index,
    SearchTool,
    MEMORY_FILE,
    DEEPSEEK_API_KEY,
    init,
    MAX_MESSAGE_LENGTH,
)

PIN = "1969"

# Initialize on startup
print("Initializing Brain...")
index, shared_memory = init()
search_tool = SearchTool(index, top_k=10) if index else None
print(f"API Key configured: {bool(DEEPSEEK_API_KEY)}")
print(f"Index loaded: {bool(index)}")

# Rate limiting storage
_last_request_time = {}
MIN_REQUEST_INTERVAL = 1.0  # Seconds between requests per session


def check_rate_limit(session_id: str) -> bool:
    """Check if session is rate limited."""
    now = time.time()
    if session_id in _last_request_time:
        elapsed = now - _last_request_time[session_id]
        if elapsed < MIN_REQUEST_INTERVAL:
            return False
    _last_request_time[session_id] = now
    return True


def check_pin(pin_input):
    """Verify PIN."""
    if not pin_input:
        return gr.update(visible=False), gr.update(visible=True), "Enter PIN"
    if pin_input == PIN:
        return gr.update(visible=True), gr.update(visible=False), ""
    return gr.update(visible=False), gr.update(visible=True), "Wrong PIN"


def load_history():
    """Load conversation history for display."""
    try:
        current_memory = load_memory()
        sessions = current_memory.get("sessions", [])
        if not sessions:
            return "No conversation history yet."
        
        output = []
        for i, ex in enumerate(reversed(sessions[-50:])):  # Last 50 only for display
            output.append(f"[{len(sessions)-i}] {ex.get('timestamp', '?')}")
            user_text = ex.get('user', '')[:200]
            agent_text = ex.get('agent', '')[:500]
            output.append(f"You: {user_text}")
            output.append(f"Brain: {agent_text}")
            if ex.get('searches'):
                output.append(f"Searches: {', '.join(ex['searches'])}")
            output.append("-" * 40)
        return "\n".join(output)
    except Exception as e:
        return f"Error loading history: {str(e)}"


with gr.Blocks(title="Brain") as demo:
    gr.Markdown("# 🧠 Brain")
    
    # Session state
    session_id = gr.State(value=lambda: str(time.time()))
    
    with gr.Tabs():
        with gr.TabItem("Chat"):
            chatbot = gr.Chatbot(
                label="Brain", 
                height=500,
                bubble_full_width=False,
            )
            msg = gr.Textbox(
                placeholder="Type here...", 
                show_label=False,
                max_lines=10,
            )
            
            with gr.Row():
                send_btn = gr.Button("Send", variant="primary")
                clear_btn = gr.Button("Clear Chat")
            
            # Status indicator
            status_msg = "✅ System ready"
            if not DEEPSEEK_API_KEY:
                status_msg = "❌ Error: DEEPSEEK_API_KEY not configured"
            elif not index:
                status_msg = "⚠️ Warning: Knowledge index not loaded"
            
            status_text = gr.Markdown(status_msg)

            async def respond(message, history, session):
                # Input validation
                if not message or not message.strip():
                    return "", history, session
                
                # Rate limiting
                if not check_rate_limit(session):
                    history.append([message, "⚠️ Please wait a moment before sending another message."])
                    return "", history, session
                
                # Check system ready
                if not DEEPSEEK_API_KEY:
                    history.append([message, "❌ Error: DEEPSEEK_API_KEY not configured."])
                    return "", history, session
                
                if not search_tool:
                    history.append([message, "❌ Error: Knowledge index not available."])
                    return "", history, session
                
                # Truncate display in chat if needed
                display_message = message
                if len(message) > 500:
                    display_message = message[:500] + "..."
                
                try:
                    response, searches = await run_agent(
                        search_tool, message, shared_memory, DEEPSEEK_API_KEY
                    )
                    
                    # Format response
                    display_response = response
                    if searches:
                        search_info = f"🔍 {', '.join(searches)}\n\n"
                        display_response = search_info + response
                    
                    history.append([display_message, display_response])
                    return "", history, session
                    
                except Exception as e:
                    import traceback
                    error_detail = traceback.format_exc()
                    print(f"Error in respond: {error_detail}")
                    history.append([display_message, f"❌ Error: {str(e)}"])
                    return "", history, session

            def clear_chat():
                return []

            send_btn.click(
                respond, 
                [msg, chatbot, session_id], 
                [msg, chatbot, session_id]
            )
            msg.submit(
                respond, 
                [msg, chatbot, session_id], 
                [msg, chatbot, session_id]
            )
            clear_btn.click(clear_chat, outputs=[chatbot])

        with gr.TabItem("History"):
            gr.Markdown("View conversation history (PIN protected)")
            
            with gr.Column(visible=True) as pin_section:
                pin_input = gr.Textbox(
                    label="PIN", 
                    type="password",
                    max_lines=1,
                )
                pin_btn = gr.Button("Unlock")
                pin_error = gr.Markdown("")

            with gr.Column(visible=False) as history_section:
                with gr.Row():
                    refresh_btn = gr.Button("Refresh")
                    lock_btn = gr.Button("Lock")
                history_display = gr.Textbox(
                    label="Conversation History",
                    lines=30,
                    max_lines=50,
                    interactive=False,
                    show_copy_button=True,
                )

            def lock_history():
                return gr.update(visible=False), gr.update(visible=True), ""

            pin_btn.click(
                fn=check_pin,
                inputs=[pin_input],
                outputs=[history_section, pin_section, pin_error]
            )
            refresh_btn.click(fn=load_history, outputs=[history_display])
            pin_btn.click(fn=load_history, outputs=[history_display])
            lock_btn.click(
                fn=lock_history,
                outputs=[history_section, pin_section, pin_error]
            )
            
            # Clear PIN input after attempt
            pin_btn.click(lambda: "", outputs=[pin_input])

if __name__ == "__main__":
    demo.launch(
        theme=gr.themes.Soft(),
        show_error=True,
    )
