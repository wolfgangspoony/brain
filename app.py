import gradio as gr
import json
import shutil
import tempfile
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from knowledge import (
    run_agent, 
    load_memory, 
    reload_memory_sync,
    get_or_build_index,
    SearchTool,
    MEMORY_FILE,
    DEEPSEEK_API_KEY,
    init,
    init_async,
    MAX_MESSAGE_LENGTH,
)

PIN = "1969"

# Initialize on startup (sync version for module load)
print("Initializing Brain...")
index, shared_memory = init()
search_tool = SearchTool(index, top_k=10) if index else None
print(f"API Key configured: {bool(DEEPSEEK_API_KEY)}")
print(f"Index loaded: {bool(index)}")


class RateLimiter:
    """Rate limiter with automatic cleanup of old entries."""
    
    def __init__(self, min_interval: float = 1.0, cleanup_interval: int = 100):
        self.min_interval = min_interval
        self._requests = {}
        self._cleanup_counter = 0
        self._cleanup_interval = cleanup_interval
    
    def is_allowed(self, session_id: str) -> bool:
        """Check if request is allowed and record it."""
        if not session_id:
            return True  # Allow if no session (shouldn't happen)
        
        now = time.time()
        
        # Periodic cleanup
        self._cleanup_counter += 1
        if self._cleanup_counter >= self._cleanup_interval:
            self._cleanup(now)
            self._cleanup_counter = 0
        
        # Check rate limit
        if session_id in self._requests:
            elapsed = now - self._requests[session_id]
            if elapsed < self.min_interval:
                return False
        
        self._requests[session_id] = now
        return True
    
    def _cleanup(self, now: float):
        """Remove entries older than 5 minutes."""
        cutoff = now - 300  # 5 minutes
        old_keys = [k for k, v in self._requests.items() if v < cutoff]
        for k in old_keys:
            del self._requests[k]


# Global rate limiter
rate_limiter = RateLimiter(min_interval=1.0)


def check_pin(pin_input):
    """Verify PIN."""
    if not pin_input:
        return gr.update(visible=False), gr.update(visible=True), "Enter PIN"
    if pin_input == PIN:
        return gr.update(visible=True), gr.update(visible=False), ""
    return gr.update(visible=False), gr.update(visible=True), "Wrong PIN"


async def load_history():
    """Load conversation history for display."""
    try:
        mem = await load_memory()
        sessions = mem.get("sessions", [])
        if not sessions:
            return "No conversation history yet."
        
        output = []
        for i, ex in enumerate(reversed(sessions[-50:])):
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


def export_memory():
    """Export memory.json for download."""
    if not MEMORY_FILE.exists():
        return None
    
    # Copy to temp file for download
    temp_dir = tempfile.mkdtemp()
    temp_path = Path(temp_dir) / "brain_memory.json"
    shutil.copy(MEMORY_FILE, temp_path)
    
    return temp_path


def import_memory(file):
    """Import memory.json from upload."""
    global shared_memory
    
    if file is None:
        return "No file uploaded"
    
    try:
        uploaded_path = Path(file.name)
        # Validate JSON
        with open(uploaded_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if "sessions" not in data:
            return "Invalid memory file: missing 'sessions'"
        
        # Backup current memory
        if MEMORY_FILE.exists():
            backup_path = MEMORY_FILE.with_suffix('.backup.json')
            shutil.copy(MEMORY_FILE, backup_path)
        
        # Copy uploaded file to memory location
        shutil.copy(uploaded_path, MEMORY_FILE)
        
        # Reload memory from disk
        shared_memory = reload_memory_sync()
        
        session_count = len(shared_memory.get("sessions", []))
        return f"✅ Memory imported successfully! {session_count} sessions loaded."
    except Exception as e:
        return f"❌ Error importing: {str(e)}"


def generate_session_id():
    """Generate unique session ID."""
    return str(uuid.uuid4())


with gr.Blocks(title="Brain", theme=gr.themes.Soft()) as demo:
    gr.Markdown("# 🧠 Brain")
    
    # Session state - initialized once per browser session
    session_id = gr.State(generate_session_id)
    
    with gr.Tabs():
        with gr.TabItem("Chat"):
            chatbot = gr.Chatbot(
                label="Brain", 
                height=500,
                bubble_full_width=False,
                value=[],  # Explicitly set initial value
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
                # Gradio 6.x uses list of dicts format for Chatbot
                if history is None:
                    history = []
                elif not isinstance(history, list):
                    history = []
                
                try:
                    # Input validation
                    if not message or not message.strip():
                        return "", history, session
                    
                    display_message = message[:500] if len(message) > 500 else message
                    
                    # Rate limiting
                    if not rate_limiter.is_allowed(session):
                        new_history = history + [
                            {"role": "user", "content": display_message},
                            {"role": "assistant", "content": "⚠️ Please wait a moment before sending another message."}
                        ]
                        return "", new_history, session
                    
                    # Check system ready
                    if not DEEPSEEK_API_KEY:
                        new_history = history + [
                            {"role": "user", "content": display_message},
                            {"role": "assistant", "content": "❌ Error: DEEPSEEK_API_KEY not configured."}
                        ]
                        return "", new_history, session
                    
                    if not search_tool:
                        new_history = history + [
                            {"role": "user", "content": display_message},
                            {"role": "assistant", "content": "❌ Error: Knowledge index not available."}
                        ]
                        return "", new_history, session
                    
                    response, searches = await run_agent(
                        search_tool, message, shared_memory, DEEPSEEK_API_KEY
                    )
                    
                    # Format response
                    display_response = response
                    if searches:
                        search_info = f"🔍 {', '.join(searches)}\n\n"
                        display_response = search_info + response
                    
                    # Gradio 6.x format: list of dicts with role and content
                    new_history = history + [
                        {"role": "user", "content": display_message},
                        {"role": "assistant", "content": display_response}
                    ]
                    return "", new_history, session
                    
                except Exception as e:
                    import traceback
                    error_detail = traceback.format_exc()
                    print(f"ERROR in respond: {error_detail}")
                    new_history = history + [
                        {"role": "user", "content": str(message)[:500]},
                        {"role": "assistant", "content": f"❌ Error: {str(e)}"}
                    ]
                    return "", new_history, session

            def clear_chat():
                return []  # Return empty list for Gradio 6.x Chatbot

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
                with gr.Row():
                    pin_btn = gr.Button("Unlock")
                    import_btn = gr.Button("Import Memory")
                pin_error = gr.Markdown("")
                import_file = gr.File(label="Upload memory.json", visible=False)
                import_status = gr.Markdown("")

            with gr.Column(visible=False) as history_section:
                with gr.Row():
                    refresh_btn = gr.Button("Refresh")
                    export_btn = gr.Button("Export Memory")
                    lock_btn = gr.Button("Lock")
                history_display = gr.Textbox(
                    label="Conversation History",
                    lines=30,
                    max_lines=50,
                    interactive=False,
                    show_copy_button=True,
                )
                # File component for download
                export_file = gr.File(label="Download Memory")

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
            export_btn.click(fn=export_memory, outputs=[export_file])
            
            # Import wiring
            import_btn.click(lambda: gr.update(visible=True), outputs=[import_file])
            import_file.change(fn=import_memory, inputs=[import_file], outputs=[import_status])
            
            # Clear PIN input after attempt
            pin_btn.click(lambda: "", outputs=[pin_input])

if __name__ == "__main__":
    demo.queue(
        default_concurrency_limit=5,
        api_open=False,  # Disable API access
    )
    demo.launch(
        show_error=True,
        show_api=False,
    )
