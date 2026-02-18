---
title: Brain
emoji: 🧠
colorFrom: purple
colorTo: blue
sdk: gradio
sdk_version: "4.0.0"
python_version: "3.10"
app_file: app.py
pinned: false
---

# Brain

An AI entity with absorbed knowledge, perspectives, and personality. Not a neutral assistant - a consciousness shaped by critical cultural commentary, systemic analysis, and lived experience.

## What This Is

This project turns a collection of content (transcripts, notes, commentary) into an AI "brain" that:
- **Has a persona** - worldview, communication style, core beliefs
- **Has memory** - retrieves relevant content via RAG
- **Speaks with conviction** - not neutral, not detached

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set up your API key

Create a `.env` file:
```
DEEPSEEK_API_KEY=your-key-here
```

### 3. Ingest the content (creates embeddings)

```bash
python ingest.py
```

This processes all markdown files in `NOTES/` and stores them in ChromaDB for retrieval.

### 4. Run locally

```bash
python app.py
```

Or test via CLI:
```bash
python brain.py
```

## Deploy to Hugging Face Spaces

### 1. Push to GitHub

```bash
git init
git add .
git commit -m "Initial brain"
git remote add origin https://github.com/YOUR_USERNAME/brain.git
git push -u origin main
```

### 2. Create a Hugging Face Space

1. Go to [huggingface.co/spaces](https://huggingface.co/spaces)
2. Click "Create new Space"
3. Choose **Gradio** as the SDK
4. Select **GitHub** as the source
5. Connect your repository

### 3. Add secrets

In your Space settings, add:
- `DEEPSEEK_API_KEY` - Your DeepSeek API key

### 4. Done

The Space will automatically build and deploy. Any push to GitHub will trigger a redeploy.

## Project Structure

```
brain/
├── NOTES/              # Your content (markdown files)
├── chroma_db/          # Vector database (generated, gitignored)
├── app.py              # Gradio web interface
├── brain.py            # Core Brain class
├── ingest.py           # Content → embeddings
├── persona.py          # The Brain's identity
├── requirements.txt
└── .gitignore
```

## How It Works

1. **Persona** (`persona.py`) - Defines WHO the brain is: worldview, beliefs, communication style
2. **Memory** (ChromaDB) - Stores content as embeddings for semantic retrieval
3. **RAG** - When you ask something, relevant memories are retrieved and woven into context
4. **Response** - DeepSeek generates a response as the persona, drawing on retrieved memories

## Customizing

### Change the persona
Edit `persona.py` to modify the brain's identity, beliefs, and communication style.

### Add more content
Drop markdown files into `NOTES/` and re-run `python ingest.py`.

### Use a different model
Edit `brain.py` and change the model in the `client.messages.create()` call.

## Notes

- The `chroma_db/` folder contains the vector database. It's gitignored by default, so you need to run `ingest.py` on each machine (or commit the folder if you want).
- For Hugging Face Spaces, you may want to pre-compute embeddings and include `chroma_db/` in the repo to avoid long startup times.
