import gradio as gr
from huggingface_hub import InferenceClient

import config

# Setup client
if config.DEEPSEEK_API_KEY:
    client = InferenceClient(
        base_url="https://api.deepseek.com/v1",
        api_key=config.DEEPSEEK_API_KEY
    )
    model = "deepseek-chat"
elif config.HF_TOKEN:
    client = InferenceClient(token=config.HF_TOKEN)
    model = config.MODEL
else:
    client = InferenceClient()
    model = config.MODEL


def chat(message, history):
    messages = [{"role": "system", "content": "You are a helpful assistant."}]

    for h in history:
        messages.append({"role": "user", "content": h[0]})
        if h[1]:
            messages.append({"role": "assistant", "content": h[1]})

    messages.append({"role": "user", "content": message})

    response = ""
    for chunk in client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=2048,
        stream=True
    ):
        if chunk.choices and chunk.choices[0].delta.content:
            response += chunk.choices[0].delta.content
            yield response


with gr.Blocks(title="Brain") as demo:
    gr.Markdown("# Brain\nA simple chatbot.")

    chatbot = gr.Chatbot(height=450)
    msg = gr.Textbox(placeholder="Type a message...", show_label=False)
    clear = gr.Button("Clear")

    def user_input(message, history):
        return "", history + [[message, None]]

    def bot_response(history):
        message = history[-1][0]
        history[-1][1] = ""
        for chunk in chat(message, history[:-1]):
            history[-1][1] = chunk
            yield history

    msg.submit(user_input, [msg, chatbot], [msg, chatbot], queue=False).then(
        bot_response, chatbot, chatbot
    )
    clear.click(lambda: None, None, chatbot, queue=False)

if __name__ == "__main__":
    demo.launch()
