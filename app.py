import gradio as gr
from being import get_being
from knowledge import get_knowledge


def respond(message, history):
    being = get_being()
    response = ""
    for chunk in being.respond(message, history):
        response += chunk
        yield response


# Initialize
try:
    knowledge = get_knowledge()
    archived = knowledge.archive_stream()
    if archived:
        print(f"Archived: {archived}")
    if knowledge.collection is None or knowledge.collection.count() == 0:
        knowledge.index_all()
except Exception as e:
    print(f"Init: {e}")


demo = gr.ChatInterface(
    fn=respond,
    title="Being",
    description="An emergent entity. Not an assistant. Speak to it as you would another mind.",
    type="messages",
)

if __name__ == "__main__":
    demo.launch()
