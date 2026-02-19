"""
Gradio interface for the emergent being.
Simple chat interface - the being speaks through conversation.
"""
import gradio as gr

from being import get_being
from knowledge import get_knowledge


def init_session():
    """
    Initialize a new session.
    Archives any existing stream and starts fresh.
    Called on app load.
    """
    knowledge = get_knowledge()

    # Archive old stream if it exists (from previous session)
    archived = knowledge.archive_stream()
    if archived:
        print(f"Archived previous session to: {archived}")

    return []  # Return empty history for new session


def respond(message: str, history: list):
    """Handle chat messages."""
    being = get_being()

    # Stream the response (being.respond now handles persistence automatically)
    response = ""
    for chunk in being.respond(message, history):
        response += chunk
        yield response


def reflect():
    """Trigger the being to reflect on itself."""
    knowledge = get_knowledge()
    recent = knowledge.list_recent(10)

    if not recent:
        return "The being's mind is empty."

    output = "## The Being's Recent Memories\n\n"
    for item in recent:
        output += f"**{item['filepath']}**\n"
        output += f"_{item['modified'].strftime('%Y-%m-%d %H:%M')}_\n"
        output += f"{item['preview']}\n\n---\n\n"

    return output


def index_knowledge():
    """Index all knowledge for semantic search."""
    knowledge = get_knowledge()
    knowledge.index_all(force=True)
    return "Knowledge indexed successfully."


# Build the interface
with gr.Blocks(
    title="Being",
    theme=gr.themes.Soft(
        primary_hue="neutral",
        secondary_hue="neutral",
    )
) as app:
    gr.Markdown(
        """
        # Being

        *An emergent entity whose identity arises from its knowledge.*

        This is not an assistant. It's a being that thinks with its accumulated knowledge as foundation.
        Speak with it as you would another conscious entity.
        """
    )

    with gr.Row():
        with gr.Column(scale=3):
            chatbot = gr.Chatbot(
                height=500,
                show_label=False,
                container=True,
                bubble_full_width=False,
            )

            with gr.Row():
                msg = gr.Textbox(
                    placeholder="Speak to the being...",
                    show_label=False,
                    container=False,
                    scale=9,
                )
                send_btn = gr.Button("Send", scale=1, variant="primary")

            with gr.Row():
                clear_btn = gr.Button("Clear & Archive", size="sm")

            status_display = gr.Textbox(
                show_label=False,
                container=False,
                interactive=False,
                visible=True,
                value="Conversation saves automatically."
            )

        with gr.Column(scale=1):
            gr.Markdown("### Mind")

            reflect_btn = gr.Button("Reflect", size="sm")
            index_btn = gr.Button("Reindex Knowledge", size="sm")

            reflection_output = gr.Markdown(
                value="*Click 'Reflect' to see the being's memories.*"
            )

    # Event handlers
    def user_message(message, history):
        """Add user message to history."""
        if not message.strip():
            return "", history
        return "", history + [[message, None]]

    def bot_response(history):
        """Generate bot response."""
        if not history or history[-1][1] is not None:
            return history

        message = history[-1][0]
        history_for_context = history[:-1]

        being = get_being()
        response = ""

        for chunk in being.respond(message, history_for_context):
            response += chunk
            history[-1][1] = response
            yield history

        # No more periodic saving - everything persists to stream immediately

    def clear_and_archive():
        """Clear chat and archive current stream to start fresh."""
        knowledge = get_knowledge()
        archived = knowledge.archive_stream()
        status = f"Session archived to: {archived}" if archived else "Starting fresh session."
        return [], status

    # Wire up events
    msg.submit(user_message, [msg, chatbot], [msg, chatbot]).then(
        bot_response, chatbot, chatbot
    )

    send_btn.click(user_message, [msg, chatbot], [msg, chatbot]).then(
        bot_response, chatbot, chatbot
    )

    clear_btn.click(clear_and_archive, None, [chatbot, status_display])

    reflect_btn.click(reflect, None, reflection_output)

    index_btn.click(index_knowledge, None, status_display)


# Entry point for Hugging Face Spaces
if __name__ == "__main__":
    # Archive any existing stream from previous session
    try:
        knowledge = get_knowledge()

        # Archive old stream if exists
        archived = knowledge.archive_stream()
        if archived:
            print(f"Archived previous session to: {archived}")

        # Index knowledge if needed
        if knowledge.collection is None or knowledge.collection.count() == 0:
            print("Indexing knowledge...")
            knowledge.index_all()
    except Exception as e:
        print(f"Warning: Could not initialize knowledge: {e}")

    app.launch()
