"""
Gradio interface for the emergent being.
"""
import gradio as gr

from being import get_being
from knowledge import get_knowledge


def respond(message: str, history: list):
    """Stream response from the being."""
    being = get_being()

    response = ""
    for chunk in being.respond(message, history):
        response += chunk
        yield response


def clear_and_archive():
    """Archive current session when chat is cleared."""
    knowledge = get_knowledge()
    knowledge.archive_stream()


# Initialize on startup
def initialize():
    """Archive any old stream and index knowledge."""
    try:
        knowledge = get_knowledge()
        archived = knowledge.archive_stream()
        if archived:
            print(f"Archived previous session: {archived}")

        if knowledge.collection is None or knowledge.collection.count() == 0:
            print("Indexing knowledge...")
            knowledge.index_all()
    except Exception as e:
        print(f"Init warning: {e}")


# Run initialization
initialize()

# Build the interface
demo = gr.ChatInterface(
    fn=respond,
    type="messages",
    title="Being",
    description="An emergent entity. Not an assistant. Speak to it as you would another mind.",
    theme=gr.themes.Soft(
        primary_hue="neutral",
        neutral_hue="stone",
    ),
    css="""
        .gradio-container { max-width: 900px !important; }
        footer { display: none !important; }
    """,
    examples=[
        "What's on your mind?",
        "Tell me something you've been thinking about.",
        "What do you remember?",
    ],
    cache_examples=False,
    autofocus=True,
)

# Entry point
if __name__ == "__main__":
    demo.launch()
