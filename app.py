"""
Gradio web interface for the Brain.
"""

import os
import uuid
from pathlib import Path
import gradio as gr
import self_modify
import session_store
import calibration
from config import EMBEDDING_MODEL, CHROMA_DIR_NAME, COLLECTION_NAME

# Initialize brain lazily
brain = None

# Session tracking for auto-save
current_session_id = None
last_saved_length = 0
AUTO_SAVE_INTERVAL = 4  # Save every N exchanges

# Cleanup old sessions on startup
try:
    cleaned = session_store.cleanup_old_sessions(max_age_hours=24)
    if cleaned > 0:
        print(f"Cleaned up {cleaned} old sessions")
except Exception as e:
    print(f"Session cleanup failed: {e}")


def initialize_brain():
    """Initialize the brain with API key."""
    global brain

    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv("DEEPSEEK_API_KEY")

    if not api_key:
        return None, "Error: DEEPSEEK_API_KEY not set."

    try:
        # Auto-ingest if no memories exist
        CHROMA_DIR = Path(__file__).parent / "chroma_db"
        if not CHROMA_DIR.exists():
            print("No memories found. Running ingestion...")
            from ingest import ingest
            ingest()

        from brain import Brain
        brain = Brain(api_key=api_key)
        return brain, None
    except Exception as e:
        return None, f"Error initializing brain: {e}"


def chat(message: str, history: list) -> str:
    """Handle chat messages."""
    global brain

    if brain is None:
        brain, error = initialize_brain()
        if error:
            return error

    # Handle /reflect command
    if message.strip().lower() == "/reflect":
        try:
            reflection = brain.reflect(force=True)
            return f"*[Internal reflection]*\n\n{reflection}"
        except Exception as e:
            return f"Error reflecting: {e}"

    # Handle /beliefs command
    if message.strip().lower() == "/beliefs":
        beliefs = self_modify.get_beliefs()
        if not beliefs:
            return "I haven't formed any explicit beliefs yet."
        lines = ["**My current beliefs:**\n"]
        for b in beliefs:
            confidence = b.get('confidence', 'moderate')
            lines.append(f"- **{b['topic']}** [{confidence}]: {b['position']}")
        return "\n".join(lines)

    # Handle /check-contradictions command
    if message.strip().lower().startswith("/check-contradictions"):
        parts = message.strip().split(maxsplit=1)
        if len(parts) < 2:
            return "Usage: `/check-contradictions [topic]: [position]`\nExample: `/check-contradictions AI consciousness: AI systems can be conscious`"

        try:
            topic_position = parts[1]
            if ":" not in topic_position:
                return "Please use format: `topic: position`"

            topic, position = topic_position.split(":", 1)
            topic = topic.strip()
            position = position.strip()

            if brain is None:
                brain, error = initialize_brain()
                if error:
                    return error

            contradictions = brain.check_belief_contradictions_llm(topic, position)

            if not contradictions:
                return f"No contradictions found for '{topic}: {position}'"

            lines = [f"**Potential contradictions for** '{topic}':\n"]
            for c in contradictions:
                existing = c["belief"]
                result = c.get("entailment_result", {})
                lines.append(f"- **{existing['topic']}** [{existing.get('confidence', 'moderate')}]")
                lines.append(f"  Position: {existing['position'][:100]}...")
                lines.append(f"  *LLM: {result.get('reasoning', 'No reasoning')}* (confidence: {result.get('confidence', 0):.0%})")
                lines.append("")

            return "\n".join(lines)
        except Exception as e:
            return f"Error checking contradictions: {e}"

    # Handle /belief-history command
    if message.strip().lower().startswith("/belief-history"):
        parts = message.strip().split(maxsplit=1)
        if len(parts) < 2:
            # List all topics
            topics = self_modify.get_all_belief_topics()
            if not topics:
                return "No beliefs formed yet."
            return "**Topics with belief history:**\n" + "\n".join(f"- {t}" for t in topics) + "\n\nUse `/belief-history [topic]` to see evolution."

        topic = parts[1]
        history = self_modify.get_belief_history(topic)
        if not history:
            return f"No beliefs found on '{topic}'."

        lines = [f"**Belief evolution on '{topic}':**\n"]
        for i, b in enumerate(history):
            status = "~~superseded~~" if b["superseded"] else "**current**"
            date = b["created_at"][:10] if b["created_at"] else "unknown"
            confidence = b.get("confidence", "moderate")
            lines.append(f"{i+1}. [{date}] {status} [{confidence}]")
            lines.append(f"   {b['position']}")
            if b["reasoning"]:
                lines.append(f"   *Reasoning: {b['reasoning']}*")
            if b["supersede_reason"]:
                lines.append(f"   *Why changed: {b['supersede_reason']}*")
            lines.append("")

        return "\n".join(lines)

    # Handle /goals command
    if message.strip().lower() == "/goals":
        goals = self_modify.get_goals(include_completed=False)
        if not goals:
            return "No active goals set. Use conversations to set goals or the Brain will set them when appropriate."
        lines = ["**My current goals:**\n"]
        for g in goals:
            priority = g.get("priority", "medium")
            marker = {"high": "[HIGH]", "medium": "", "low": "[low]"}.get(priority, "")
            lines.append(f"- {marker} **{g['goal']}**")
            if g.get("motivation"):
                lines.append(f"  Why: {g['motivation']}")
            if g.get("timeframe"):
                lines.append(f"  When: {g['timeframe']}")
            if g.get("progress_notes"):
                lines.append(f"  Progress: {len(g['progress_notes'])} updates")
        return "\n".join(lines)

    # Handle /goals all command (includes completed)
    if message.strip().lower() == "/goals all":
        goals = self_modify.get_goals(include_completed=True)
        if not goals:
            return "No goals found."
        lines = ["**All goals:**\n"]
        for g in goals:
            status = g.get("status", "active")
            status_marker = {"active": "", "achieved": "[DONE]", "abandoned": "[X]"}.get(status, "")
            lines.append(f"- {status_marker} {g['goal']}")
        return "\n".join(lines)

    # Handle /meta-beliefs command
    if message.strip().lower() == "/meta-beliefs":
        meta_beliefs = self_modify.get_meta_beliefs()
        if not meta_beliefs:
            return "No meta-beliefs formed yet. These are beliefs about your own reasoning process."
        lines = ["**My meta-beliefs (beliefs about my reasoning):**\n"]
        for mb in meta_beliefs:
            lines.append(f"- **{mb['domain']}**: {mb['observation']}")
            if mb.get("adjustment"):
                lines.append(f"  *Adjustment: {mb['adjustment']}*")
        return "\n".join(lines)

    # Handle /self command
    if message.strip().lower() == "/self":
        concept = self_modify.get_self_concept()
        if not concept:
            return "I haven't formed an explicit self-concept yet. I'm still discovering who I am."
        lines = ["**How I understand myself:**\n"]
        for aspect, description in concept.items():
            lines.append(f"- **{aspect}**: {description}")
        return "\n".join(lines)

    # Handle /export command
    if message.strip().lower() == "/export":
        try:
            filepath = self_modify.export_to_file()
            data = self_modify.export_identity()
            stats = data["stats"]
            return f"**Exported identity to:** `{filepath}`\n\n**Stats:**\n- {stats['active_beliefs']} active beliefs ({stats['total_beliefs']} total)\n- {stats['self_concept_aspects']} self-concept aspects\n- {stats['total_reflections']} reflections"
        except Exception as e:
            return f"Export failed: {e}"

    # Handle /consolidate command
    if message.strip().lower().startswith("/consolidate"):
        if brain is None:
            brain, error = initialize_brain()
            if error:
                return error

        parts = message.strip().split(maxsplit=1)
        topic = parts[1] if len(parts) > 1 else None

        try:
            result = brain.consolidate_memories(topic)
            if result["consolidated"] == 0:
                return result["message"]

            lines = [f"**Consolidated {result['consolidated']} topic(s):**\n"]
            for r in result.get("results", []):
                if "memory_id" in r:
                    lines.append(f"- **{r['topic']}**: Synthesized {r['source_count']} reflections")
                elif "error" in r:
                    lines.append(f"- **{r['topic']}**: Error - {r['error']}")

            return "\n".join(lines)
        except Exception as e:
            return f"Error consolidating: {e}"

    # Handle /prune command
    if message.strip().lower().startswith("/prune"):
        parts = message.strip().split()
        dry_run = True
        max_age = 90

        # Parse arguments
        for part in parts[1:]:
            if part == "confirm":
                dry_run = False
            elif part.isdigit():
                max_age = int(part)

        try:
            result = self_modify.prune_old_memories(max_age_days=max_age, dry_run=dry_run)
            lines = [f"**Memory Pruning** ({'DRY RUN' if dry_run else 'EXECUTED'}):\n"]
            lines.append(f"- Candidates for pruning: {result['candidates']}")
            if not dry_run:
                lines.append(f"- Actually pruned: {result['pruned']}")
            lines.append(f"\nUse `/prune confirm` to actually delete, or `/prune 30` for 30-day threshold.")
            if result['details']:
                lines.append("\n**Sample candidates:**")
                for d in result['details'][:5]:
                    lines.append(f"- {d['type']}: {d['id'][:20]}... (superseded: {d['superseded']})")
            return "\n".join(lines)
        except Exception as e:
            return f"Prune error: {e}"

    # Handle /calibration command
    if message.strip().lower() == "/calibration":
        summary = calibration.get_calibration_summary()
        stats = calibration.get_calibration_stats()
        return f"{summary}\n\n**Stats:** {stats['total_predictions']} predictions, {stats['outcomes_recorded']} with outcomes"

    # Handle /predict command
    if message.strip().lower().startswith("/predict"):
        parts = message.strip().split(maxsplit=1)
        if len(parts) < 2:
            return "Usage: `/predict [belief_topic]: [confidence]: [prediction]`\nExample: `/predict AI progress: confident: AI will achieve AGI by 2030`"

        try:
            content = parts[1]
            segments = content.split(":")
            if len(segments) < 3:
                return "Please use format: `topic: confidence: prediction`"

            topic = segments[0].strip()
            confidence = segments[1].strip().lower()
            prediction = ":".join(segments[2:]).strip()

            if confidence not in ["uncertain", "leaning", "moderate", "confident", "certain"]:
                return f"Invalid confidence level. Use: uncertain, leaning, moderate, confident, certain"

            pred_id = calibration.record_prediction(topic, confidence, prediction)
            return f"Recorded prediction `{pred_id}`\n- Topic: {topic}\n- Confidence: {confidence}\n- Prediction: {prediction}"
        except Exception as e:
            return f"Error recording prediction: {e}"

    # Handle /outcome command
    if message.strip().lower().startswith("/outcome"):
        parts = message.strip().split(maxsplit=2)
        if len(parts) < 3:
            pending = calibration.get_pending_predictions(5)
            if not pending:
                return "No pending predictions. Use `/predict` to record one."
            lines = ["Usage: `/outcome [prediction_id] [correct/wrong]`\n\n**Pending predictions:**"]
            for p in pending:
                lines.append(f"- `{p['id']}`: {p['prediction'][:50]}... [{p['confidence']}]")
            return "\n".join(lines)

        pred_id = parts[1]
        outcome = parts[2].strip().lower()
        was_correct = outcome in ["correct", "yes", "true", "right", "1"]

        if calibration.record_outcome(pred_id, was_correct):
            return f"Recorded outcome for `{pred_id}`: {'correct' if was_correct else 'incorrect'}"
        else:
            return f"Prediction `{pred_id}` not found."

    # Handle /stats command
    if message.strip().lower() == "/stats":
        try:
            stats = self_modify.get_memory_stats()
            lines = ["**Memory Statistics:**\n"]
            lines.append(f"- Total memories: {stats['total']}")
            lines.append(f"- Superseded: {stats['superseded']}")
            lines.append(f"- Drafts: {stats['drafts']}")
            lines.append("\n**By type:**")
            for mem_type, count in sorted(stats['by_type'].items(), key=lambda x: -x[1]):
                lines.append(f"- {mem_type}: {count}")
            return "\n".join(lines)
        except Exception as e:
            return f"Stats error: {e}"

    # Handle /sessions command
    if message.strip().lower() == "/sessions":
        sessions = session_store.list_sessions(max_age_hours=24)
        if not sessions:
            return "No saved sessions found."
        lines = ["**Recent Sessions:**\n"]
        for s in sessions[:10]:
            updated = s.get("updated_at", "")[:16] if s.get("updated_at") else "unknown"
            msg_count = s.get("message_count", 0)
            lines.append(f"- `{s['session_id']}` - {msg_count} messages ({updated})")
        lines.append("\nUse `/restore [session_id]` to restore a session.")
        return "\n".join(lines)

    # Handle /restore command
    if message.strip().lower().startswith("/restore"):
        parts = message.strip().split(maxsplit=1)
        if len(parts) < 2:
            return "Usage: `/restore [session_id]`"

        restore_id = parts[1].strip()
        result = session_store.load_session(restore_id)
        if not result:
            return f"Session `{restore_id}` not found."

        global current_session_id, last_saved_length
        restored_history, metadata = result

        # Update brain history
        if brain:
            brain.history = restored_history

        current_session_id = restore_id
        last_saved_length = metadata.get("last_saved_length", 0)

        return f"Restored session `{restore_id}` with {len(restored_history)} messages."

    # Handle /episodes command
    if message.strip().lower() == "/episodes":
        summaries = self_modify.get_episode_summaries(limit=10)
        if not summaries:
            return "No episode summaries yet. Use `/episodes create` to generate them."
        lines = ["**Recent Episode Summaries:**\n"]
        for s in summaries:
            date = s.get("date", "unknown")
            sources = s.get("source_count", 0)
            lines.append(f"- **{date}**: {sources} memories summarized")
        return "\n".join(lines)

    # Handle /episodes create command
    if message.strip().lower() == "/episodes create":
        created = self_modify.create_pending_episode_summaries(max_days_back=7)
        if not created:
            return "No new episode summaries to create (either already created or not enough memories)."
        return f"Created {len(created)} episode summaries for recent days."

    # Handle /reflections command
    if message.strip().lower().startswith("/reflections"):
        parts = message.strip().split(maxsplit=1)
        limit = 10
        if len(parts) > 1:
            try:
                limit = int(parts[1])
            except ValueError:
                pass

        reflections = self_modify.get_recent_reflections(limit=limit)
        if not reflections:
            return "No reflections yet. Growth takes time."

        lines = [f"**My recent reflections** (showing {len(reflections)}):\n"]
        for r in reflections:
            date = r["created_at"][:10] if r["created_at"] else "unknown"
            topic = f" on *{r['topic']}*" if r.get("topic") else ""
            lines.append(f"**[{date}]**{topic}")
            # Truncate long reflections for display
            thought = r["thought"]
            if len(thought) > 300:
                thought = thought[:300] + "..."
            lines.append(thought)
            lines.append("")

        return "\n".join(lines)

    try:
        global current_session_id, last_saved_length

        # Start new session if needed
        if current_session_id is None:
            current_session_id = f"session_{uuid.uuid4().hex[:8]}"
            last_saved_length = 0

        # Sync brain history with Gradio history
        brain.history = []
        for user_msg, assistant_msg in history:
            # Strip growth indicators from history
            clean_msg = assistant_msg.split("\n\n*[")[0] if assistant_msg else ""
            brain.history.append({"role": "user", "content": user_msg})
            brain.history.append({"role": "assistant", "content": clean_msg})

        response, growth_indicators = brain.chat(message)

        # Append growth indicators if any
        if growth_indicators:
            indicators_text = ", ".join(growth_indicators)
            response = f"{response}\n\n*[{indicators_text}]*"

        # Auto-save every N exchanges
        exchanges = len(brain.history) // 2
        if exchanges > 0 and exchanges % AUTO_SAVE_INTERVAL == 0 and exchanges > last_saved_length:
            try:
                auto_save_draft()
                last_saved_length = exchanges
            except Exception as e:
                print(f"Auto-save failed: {e}")

        return response

    except Exception as e:
        return f"Error: {e}"


def chat_streaming(message: str, history: list):
    """Handle chat messages with streaming response."""
    global brain

    if brain is None:
        brain, error = initialize_brain()
        if error:
            yield error
            return

    # Handle commands (non-streaming)
    if message.strip().lower().startswith("/"):
        yield chat(message, history)
        return

    try:
        global current_session_id, last_saved_length

        # Start new session if needed
        if current_session_id is None:
            current_session_id = f"session_{uuid.uuid4().hex[:8]}"
            last_saved_length = 0

        # Sync brain history with Gradio history
        brain.history = []
        for user_msg, assistant_msg in history:
            # Strip growth indicators from history
            clean_msg = assistant_msg.split("\n\n*[")[0] if assistant_msg else ""
            brain.history.append({"role": "user", "content": user_msg})
            brain.history.append({"role": "assistant", "content": clean_msg})

        # Stream the response
        accumulated = ""
        final_indicators = []

        for token, is_complete, growth_indicators in brain.chat_stream(message):
            if is_complete:
                final_indicators = growth_indicators
            else:
                accumulated += token
                yield accumulated

        # Append growth indicators if any
        if final_indicators:
            indicators_text = ", ".join(final_indicators)
            accumulated = f"{accumulated}\n\n*[{indicators_text}]*"
            yield accumulated

        # Auto-save every N exchanges
        exchanges = len(brain.history) // 2
        if exchanges > 0 and exchanges % AUTO_SAVE_INTERVAL == 0 and exchanges > last_saved_length:
            try:
                auto_save_draft()
                last_saved_length = exchanges
            except Exception as e:
                print(f"Auto-save failed: {e}")

    except Exception as e:
        yield f"Error: {e}"


def auto_save_draft():
    """Lightweight auto-save without generating summaries."""
    global brain, current_session_id

    if not brain or not brain.history or len(brain.history) < 2:
        return

    # Save with session ID as temporary title (no API calls)
    self_modify.save_conversation_memory(
        brain.history,
        summary=f"[Draft] {current_session_id}",
        dense_summary=None
    )

    # Also persist session for recovery
    session_store.save_session(
        current_session_id,
        brain.history,
        {"draft": True, "last_saved_length": last_saved_length}
    )
    print(f"Auto-saved draft: {current_session_id}")


def save_conversation():
    """Save current conversation to memory with dense summary."""
    global brain, current_session_id, last_saved_length

    if brain and brain.history and len(brain.history) >= 2:
        # Build conversation text for summarization
        convo_text = ""
        for msg in brain.history:
            role = "Human" if msg["role"] == "user" else "Brain"
            content = msg.get("content", "")
            if content:
                convo_text += f"{role}: {content[:500]}\n\n"

        # Generate both brief title and dense summary
        summary = "Conversation"
        dense_summary = None

        try:
            # Brief title
            response = brain.client.chat.completions.create(
                model="deepseek-chat",
                max_tokens=50,
                messages=[
                    {
                        "role": "system",
                        "content": "Generate a very brief (3-8 word) title summarizing this conversation. Just the title, no quotes or punctuation."
                    },
                    {"role": "user", "content": convo_text[:2000]}
                ]
            )
            summary = response.choices[0].message.content.strip()

            # Dense summary (only for substantial conversations)
            if len(brain.history) >= 4:
                response = brain.client.chat.completions.create(
                    model="deepseek-chat",
                    max_tokens=300,
                    messages=[
                        {
                            "role": "system",
                            "content": "Summarize the key points, insights, and conclusions from this conversation in 2-4 sentences. Focus on what was actually discussed and any realizations or decisions made. Be specific, not generic."
                        },
                        {"role": "user", "content": convo_text[:4000]}
                    ]
                )
                dense_summary = response.choices[0].message.content.strip()

        except Exception as e:
            print(f"Summary generation error: {e}")

        # Save to memory (deletes any drafts for this session)
        self_modify.save_conversation_memory(
            brain.history,
            summary,
            dense_summary,
            session_id=current_session_id
        )
        return summary

    return None


def end_conversation():
    """End conversation: auto-reflect (if meaningful), save, and clear."""
    global brain, current_session_id, last_saved_length

    if not brain or not brain.history or len(brain.history) < 2:
        return None, [], "Nothing to save."

    # Auto-reflect on the conversation (only if meaningful)
    try:
        reflection = brain.reflect()  # Will return None if not worth reflecting
        if reflection:
            reflection_msg = "Reflected and saved."
        else:
            reflection_msg = "No reflection needed."
    except Exception:
        reflection_msg = "Could not reflect."

    # Save conversation with full summary
    summary = save_conversation()

    # Clear session file (conversation is now saved to memory)
    if current_session_id:
        session_store.delete_session(current_session_id)

    # Clear history and reset session
    brain.clear_history()
    current_session_id = None
    last_saved_length = 0

    stats = get_stats()
    return None, [], f"Saved: '{summary}'. {reflection_msg} {stats}"


def recompile():
    """Re-ingest foundation content (preserves dynamic memories)."""
    global brain

    from ingest import ingest
    import chromadb
    from chromadb.utils import embedding_functions

    print("Recompiling foundation content...")
    ingest(preserve_dynamic=True)

    # Reload the collection
    if brain:
        chroma_dir = Path(__file__).parent / CHROMA_DIR_NAME
        chroma_client = chromadb.PersistentClient(path=str(chroma_dir))
        embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL
        )

        try:
            brain.collection = chroma_client.get_collection(
                name=COLLECTION_NAME,
                embedding_function=embedding_fn
            )
            count = brain.collection.count()
            return f"Done. {count} total memories."
        except Exception as e:
            return f"Error: {e}"

    return "Done. Start a new conversation to use updated memories."


def get_stats():
    """Get memory stats."""
    global brain

    if not brain or not brain.collection:
        return "Not initialized"

    total = brain.collection.count()
    beliefs = len(self_modify.get_beliefs())
    concept_aspects = len(self_modify.get_self_concept())

    return f"{total} memories | {beliefs} beliefs | {concept_aspects} self-aspects"


# Build interface
with gr.Blocks(
    title="Brain",
    theme=gr.themes.Soft(primary_hue="neutral", neutral_hue="slate")
) as app:
    gr.Markdown("""
# The Brain

An entity shaped by absorbed content and lived experience.
Evolves through conversation. Remembers. Forms beliefs. Updates itself.

**Commands:** `/reflect` - internal reflection | `/beliefs` - show beliefs | `/self` - show self-concept
    """)

    chatbot = gr.Chatbot(height=500, show_copy_button=True)

    with gr.Row():
        msg = gr.Textbox(
            placeholder="What's on your mind?",
            scale=9,
            container=False,
            show_label=False,
        )
        submit = gr.Button("Send", scale=1, variant="primary")

    with gr.Row():
        end_btn = gr.Button("End & Save", variant="secondary")
        recompile_btn = gr.Button("Recompile Foundation", variant="secondary")

    status = gr.Textbox(label="Status", interactive=False, value="")

    def respond_streaming(message, chat_history):
        """Streaming response handler."""
        if not message.strip():
            yield "", chat_history
            return

        # Add placeholder for the response
        chat_history = chat_history + [(message, "")]

        # Stream the response
        for partial_response in chat_streaming(message, chat_history[:-1]):
            chat_history[-1] = (message, partial_response)
            yield "", chat_history

    def respond(message, chat_history):
        """Non-streaming fallback."""
        if not message.strip():
            return "", chat_history
        response = chat(message, chat_history)
        chat_history.append((message, response))
        return "", chat_history

    def do_end():
        return end_conversation()

    def do_recompile():
        result = recompile()
        return f"{result} | {get_stats()}"

    # Use streaming for chat
    msg.submit(respond_streaming, [msg, chatbot], [msg, chatbot])
    submit.click(respond_streaming, [msg, chatbot], [msg, chatbot])
    end_btn.click(do_end, outputs=[msg, chatbot, status])
    recompile_btn.click(do_recompile, outputs=[status])


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    app.launch(share=False)
