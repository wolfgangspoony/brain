"""
The Brain - combines persona with RAG retrieval and self-modification.
"""

import os
import json
import hashlib
from pathlib import Path
from string import Template
from collections import OrderedDict

import chromadb
from chromadb.utils import embedding_functions

from config import (
    EMBEDDING_MODEL, CHROMA_DIR_NAME, COLLECTION_NAME, RETRIEVAL_CANDIDATES, RETRIEVAL_FINAL,
    MAX_HISTORY_TOKENS, HISTORY_TRUNCATION_THRESHOLD
)
from persona import PERSONA, SYSTEM_PROMPT_TEMPLATE
import self_modify
import logging_utils


# Tool definitions for function calling
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "Save a thought or realization to memory immediately. Use when you have an insight worth preserving.",
            "parameters": {
                "type": "object",
                "properties": {
                    "thought": {
                        "type": "string",
                        "description": "The thought or insight to remember"
                    },
                    "topic": {
                        "type": "string",
                        "description": "Optional topic/category for the thought"
                    }
                },
                "required": ["thought"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "form_belief",
            "description": "Crystallize a belief or position on a topic. Use when you've formed a clear stance on something.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "What the belief is about"
                    },
                    "position": {
                        "type": "string",
                        "description": "Your position or view"
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Why you hold this position"
                    },
                    "confidence": {
                        "type": "string",
                        "enum": ["uncertain", "leaning", "moderate", "confident", "certain"],
                        "description": "How confident you are in this belief"
                    }
                },
                "required": ["topic", "position"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_belief",
            "description": "Update an existing belief when your position has evolved. The old belief is preserved but marked as superseded.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        "description": "The topic of the belief to update"
                    },
                    "new_position": {
                        "type": "string",
                        "description": "Your new position"
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Why your position changed"
                    },
                    "confidence": {
                        "type": "string",
                        "enum": ["uncertain", "leaning", "moderate", "confident", "certain"],
                        "description": "How confident you are in the new position"
                    }
                },
                "required": ["topic", "new_position"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_self_concept",
            "description": "Update how you understand yourself. Use when you realize something about your own identity, values, or nature.",
            "parameters": {
                "type": "object",
                "properties": {
                    "aspect": {
                        "type": "string",
                        "description": "Which aspect of self (e.g., 'identity', 'values', 'purpose', 'style')"
                    },
                    "description": {
                        "type": "string",
                        "description": "Your new understanding of this aspect"
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "What led to this realization"
                    }
                },
                "required": ["aspect", "description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "form_meta_belief",
            "description": "Form a belief about your own belief-forming process. Use when you notice patterns in how you think or reason about certain topics.",
            "parameters": {
                "type": "object",
                "properties": {
                    "domain": {
                        "type": "string",
                        "description": "What area this applies to (e.g., 'political topics', 'technical predictions', 'social judgments')"
                    },
                    "observation": {
                        "type": "string",
                        "description": "What you've noticed about your reasoning in this domain"
                    },
                    "adjustment": {
                        "type": "string",
                        "description": "How you should adjust your reasoning going forward"
                    }
                },
                "required": ["domain", "observation"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "set_goal",
            "description": "Define a goal you want to work toward. Use when you identify something you want to achieve or become.",
            "parameters": {
                "type": "object",
                "properties": {
                    "goal": {
                        "type": "string",
                        "description": "What you want to achieve"
                    },
                    "motivation": {
                        "type": "string",
                        "description": "Why this matters to you"
                    },
                    "timeframe": {
                        "type": "string",
                        "description": "When you hope to achieve this"
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["low", "medium", "high"],
                        "description": "How important this goal is"
                    }
                },
                "required": ["goal"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_goal_progress",
            "description": "Record progress toward a goal or update its status.",
            "parameters": {
                "type": "object",
                "properties": {
                    "goal": {
                        "type": "string",
                        "description": "Which goal (text to match)"
                    },
                    "progress": {
                        "type": "string",
                        "description": "What progress was made"
                    },
                    "status": {
                        "type": "string",
                        "enum": ["active", "achieved", "abandoned"],
                        "description": "New status for the goal"
                    }
                },
                "required": ["goal"]
            }
        }
    }
]


class Brain:
    def __init__(self, api_key: str = None):
        """Initialize the Brain with optional API key."""
        self.api_key = api_key or os.getenv("DEEPSEEK_API_KEY")

        if not self.api_key:
            raise ValueError("DEEPSEEK_API_KEY required")

        # Initialize OpenAI-compatible client for DeepSeek
        from openai import OpenAI
        self.client = OpenAI(
            api_key=self.api_key,
            base_url="https://api.deepseek.com"
        )

        # Initialize ChromaDB for retrieval
        chroma_dir = Path(__file__).parent / CHROMA_DIR_NAME

        # Embedding cache (LRU with max 500 entries)
        self._embedding_cache = OrderedDict()
        self._embedding_cache_max = 500
        self._embedding_fn = None

        if not chroma_dir.exists():
            print("Warning: chroma_db not found. Run ingest.py first.")
            self.collection = None
        else:
            chroma_client = chromadb.PersistentClient(path=str(chroma_dir))
            self._embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name=EMBEDDING_MODEL
            )

            try:
                self.collection = chroma_client.get_collection(
                    name=COLLECTION_NAME,
                    embedding_function=self._embedding_fn
                )
                print(f"Loaded {self.collection.count()} memories")
            except Exception as e:
                print(f"Warning: Could not load memories: {e}")
                self.collection = None

        # Conversation history
        self.history = []

    def _get_embedding(self, text: str) -> list[float]:
        """
        Get embedding for text, using cache when available.

        Args:
            text: Text to embed

        Returns:
            Embedding vector
        """
        # Create cache key from text hash
        cache_key = hashlib.md5(text.encode()).hexdigest()

        # Check cache
        if cache_key in self._embedding_cache:
            # Move to end (most recently used)
            self._embedding_cache.move_to_end(cache_key)
            return self._embedding_cache[cache_key]

        # Compute embedding
        embedding = self._embedding_fn([text])[0]

        # Add to cache with LRU eviction
        if len(self._embedding_cache) >= self._embedding_cache_max:
            # Remove oldest entry
            self._embedding_cache.popitem(last=False)

        self._embedding_cache[cache_key] = embedding
        return embedding

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text.
        Uses ~4 chars per token heuristic (reasonable for English).
        """
        if not text:
            return 0
        return len(text) // 4 + 1

    def _count_history_tokens(self) -> int:
        """Count approximate tokens in conversation history."""
        total = 0
        for msg in self.history:
            content = msg.get("content", "")
            total += self._estimate_tokens(content)
            # Account for tool calls
            if "tool_calls" in msg:
                total += self._estimate_tokens(json.dumps(msg["tool_calls"]))
        return total

    def _truncate_history_smart(self, system_prompt: str) -> list[dict]:
        """
        Smart history truncation with prioritization:
        1. Always keep first 2 messages (establishes context)
        2. Always keep last 6 messages (recent context)
        3. Summarize middle if needed
        4. Preserve tool call sequences intact

        Args:
            system_prompt: The system prompt (to account for its tokens)

        Returns:
            Truncated history ready for API call
        """
        history_tokens = self._count_history_tokens()
        system_tokens = self._estimate_tokens(system_prompt)
        total_tokens = history_tokens + system_tokens

        # Check if truncation is needed
        threshold = int(MAX_HISTORY_TOKENS * HISTORY_TRUNCATION_THRESHOLD)
        if total_tokens < threshold:
            return self.history

        # If history is small, don't truncate
        if len(self.history) <= 8:
            return self.history

        # Keep first 2 and last 6 messages
        preserved_start = self.history[:2]
        preserved_end = self.history[-6:]
        middle = self.history[2:-6]

        if not middle:
            return self.history

        # Create a summary of the middle section
        middle_text_parts = []
        for msg in middle:
            role = "Human" if msg.get("role") == "user" else "Assistant"
            content = msg.get("content", "")
            if content:
                # Truncate individual messages for the summary
                middle_text_parts.append(f"{role}: {content[:100]}...")

        if middle_text_parts:
            middle_summary = f"[Earlier in conversation - {len(middle)} messages summarized: " + "; ".join(middle_text_parts[:5])
            if len(middle_text_parts) > 5:
                middle_summary += f"; ... and {len(middle_text_parts) - 5} more exchanges"
            middle_summary += "]"

            summary_message = {
                "role": "system",
                "content": middle_summary
            }

            truncated = preserved_start + [summary_message] + preserved_end

            logging_utils.log_decision("context_truncation", {
                "original_messages": len(self.history),
                "truncated_messages": len(truncated),
                "middle_summarized": len(middle),
                "estimated_tokens_before": total_tokens,
                "estimated_tokens_after": self._estimate_tokens(system_prompt) + sum(
                    self._estimate_tokens(m.get("content", "")) for m in truncated
                )
            })

            return truncated

        return self.history

    def retrieve(self, query: str, n_results: int = None) -> str:
        """Retrieve relevant memories for a query with recency awareness."""
        if not self.collection:
            return "No memories available."

        n_results = n_results or RETRIEVAL_FINAL

        # Get embedding (with caching)
        if self._embedding_fn:
            query_embedding = self._get_embedding(query)
            # Query using cached embedding
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=RETRIEVAL_CANDIDATES,
                include=["documents", "metadatas", "distances"]
            )
        else:
            # Fallback to query_texts if no embedding function
            results = self.collection.query(
                query_texts=[query],
                n_results=RETRIEVAL_CANDIDATES,
                include=["documents", "metadatas", "distances"]
            )

        if not results['documents'] or not results['documents'][0]:
            return "No relevant memories found."

        # Build candidates with scores
        from datetime import datetime
        now = datetime.now()
        candidates = []

        for doc, meta, distance in zip(
            results['documents'][0],
            results['metadatas'][0],
            results['distances'][0]
        ):
            # Skip superseded memories
            if meta.get('superseded', False):
                continue

            # Calculate recency score (0-1, higher = more recent)
            created_at = meta.get('created_at', '')
            recency_score = 0.5  # default for foundation content
            if created_at:
                try:
                    created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    days_ago = (now - created.replace(tzinfo=None)).days
                    # Exponential decay: half-life of 30 days
                    recency_score = 0.5 ** (days_ago / 30)
                except Exception:
                    pass

            # Combined score: semantic similarity + recency + importance
            # Distance is typically 0-2 for cosine, lower = better
            semantic_score = max(0, 1 - distance / 2)

            # Calculate importance score
            importance_score = self_modify.calculate_importance(meta, doc)

            # New weighting: 50% semantic, 25% recency, 25% importance
            combined_score = (
                semantic_score * 0.5 +
                recency_score * 0.25 +
                importance_score * 0.25
            )

            candidates.append({
                'doc': doc,
                'meta': meta,
                'doc_id': results['ids'][0][results['documents'][0].index(doc)] if results.get('ids') else None,
                'semantic_score': semantic_score,
                'recency_score': recency_score,
                'importance_score': importance_score,
                'combined_score': combined_score
            })

        # Sort by combined score and take top N
        candidates.sort(key=lambda x: x['combined_score'], reverse=True)
        top_candidates = candidates[:n_results]

        # Record access for retrieved memories (for importance tracking)
        accessed_ids = [c['doc_id'] for c in top_candidates if c.get('doc_id')]
        if accessed_ids:
            self_modify.record_batch_access(accessed_ids)

        # Format memories with temporal context
        memories = []
        for c in top_candidates:
            doc = c['doc']
            meta = c['meta']
            source = meta.get('title', meta.get('filename', 'Unknown'))
            mem_type = meta.get('memory_type', meta.get('type', 'foundation'))
            created_at = meta.get('created_at', '')

            # Format timestamp
            time_str = ""
            if created_at:
                try:
                    created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    days_ago = (now - created.replace(tzinfo=None)).days
                    if days_ago == 0:
                        time_str = " (today)"
                    elif days_ago == 1:
                        time_str = " (yesterday)"
                    elif days_ago < 7:
                        time_str = f" ({days_ago} days ago)"
                    elif days_ago < 30:
                        time_str = f" ({days_ago // 7} weeks ago)"
                    elif days_ago < 365:
                        time_str = f" ({days_ago // 30} months ago)"
                    else:
                        time_str = f" ({days_ago // 365} years ago)"
                except Exception:
                    pass

            if mem_type == 'conversation':
                memories.append(f"[From past conversation{time_str}: {source}]\n{doc}")
            elif mem_type == 'conversation_summary':
                memories.append(f"[Summary of conversation{time_str}: {source}]\n{doc}")
            elif mem_type == 'reflection':
                memories.append(f"[My reflection{time_str}]\n{doc}")
            elif mem_type == 'belief':
                topic = meta.get('topic', 'general')
                memories.append(f"[My belief on {topic}{time_str}]\n{doc}")
            else:
                memories.append(f"[From: {source}]\n{doc}")

        # Log the retrieval decision
        logging_utils.log_retrieval(
            query=query,
            candidates_count=len(results['documents'][0]) if results['documents'] else 0,
            final_count=len(top_candidates),
            top_results=[
                {
                    "source": c['meta'].get('title', c['meta'].get('filename', 'unknown')),
                    "type": c['meta'].get('memory_type', 'foundation'),
                    "semantic_score": round(c['semantic_score'], 3),
                    "recency_score": round(c['recency_score'], 3),
                    "importance_score": round(c.get('importance_score', 0), 3),
                    "combined_score": round(c['combined_score'], 3),
                    "preview": c['doc'][:200]
                }
                for c in top_candidates
            ]
        )

        return "\n\n---\n\n".join(memories)

    def check_entailment(self, premise: str, hypothesis: str) -> dict:
        """
        Check logical relationship between two statements using LLM.

        Args:
            premise: The first statement (existing belief)
            hypothesis: The second statement (new belief)

        Returns:
            Dict with relation, confidence, and reasoning
        """
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                max_tokens=150,
                messages=[
                    {
                        "role": "system",
                        "content": """Analyze the logical relationship between two statements.

Output ONLY valid JSON in this exact format:
{"relation": "entails|contradicts|neutral", "confidence": 0.0-1.0, "reasoning": "brief explanation"}

Definitions:
- "entails": Statement A logically implies or supports Statement B
- "contradicts": Statements A and B cannot both be true simultaneously
- "neutral": No clear logical relationship between the statements"""
                    },
                    {
                        "role": "user",
                        "content": f"Statement A: {premise}\n\nStatement B: {hypothesis}"
                    }
                ]
            )

            content = response.choices[0].message.content.strip()
            # Try to parse JSON
            result = json.loads(content)
            return result
        except json.JSONDecodeError:
            # Try to extract relation from text if JSON parsing fails
            content_lower = content.lower() if 'content' in dir() else ""
            if "contradict" in content_lower:
                return {"relation": "contradicts", "confidence": 0.5, "reasoning": "Extracted from non-JSON response"}
            elif "entail" in content_lower:
                return {"relation": "entails", "confidence": 0.5, "reasoning": "Extracted from non-JSON response"}
            return {"relation": "neutral", "confidence": 0.0, "reasoning": "Failed to parse response"}
        except Exception as e:
            logging_utils.log_api_call(
                endpoint="check_entailment",
                model="deepseek-chat",
                success=False,
                error=str(e)
            )
            return {"relation": "neutral", "confidence": 0.0, "reasoning": f"Error: {e}"}

    def check_belief_contradictions_llm(
        self,
        topic: str,
        position: str,
        max_checks: int = 5
    ) -> list[dict]:
        """
        Enhanced contradiction detection using LLM entailment checking.

        First uses fast embedding-based detection, then verifies top candidates with LLM.

        Args:
            topic: The topic of the new belief
            position: The position being taken
            max_checks: Maximum number of LLM checks to perform

        Returns:
            List of verified contradictions with LLM reasoning
        """
        # First pass: embedding-based detection (fast)
        candidates = self_modify.check_belief_contradictions(topic, position, similarity_threshold=0.5)

        if not candidates:
            return []

        # Second pass: LLM verification (slow but accurate)
        verified = []
        for candidate in candidates[:max_checks]:
            existing_position = candidate["belief"]["position"]

            result = self.check_entailment(existing_position, position)

            if result["relation"] == "contradicts" and result.get("confidence", 0) > 0.6:
                candidate["llm_verified"] = True
                candidate["entailment_result"] = result
                verified.append(candidate)

                logging_utils.log_decision("llm_contradiction_check", {
                    "existing_topic": candidate["belief"]["topic"],
                    "new_topic": topic,
                    "relation": result["relation"],
                    "confidence": result.get("confidence"),
                    "reasoning": result.get("reasoning")
                })

        return verified

    def get_current_beliefs(self) -> str:
        """Get current beliefs formatted for context."""
        beliefs = self_modify.get_beliefs()
        if not beliefs:
            return ""

        lines = ["## My current beliefs"]
        for b in beliefs:
            confidence = b.get('confidence', 'moderate')
            conf_marker = {"uncertain": "?", "leaning": "~", "moderate": "", "confident": "!", "certain": "!!"}
            marker = conf_marker.get(confidence, "")
            lines.append(f"- **{b['topic']}**{marker}: {b['position']}")
            if b['reasoning']:
                lines.append(f"  (because: {b['reasoning']})")

        return "\n".join(lines)

    def get_current_self_concept(self) -> str:
        """Get current self-concept formatted for context."""
        concept = self_modify.get_self_concept()
        if not concept:
            return ""

        lines = ["## How I understand myself"]
        for aspect, description in concept.items():
            lines.append(f"- **{aspect}**: {description}")

        return "\n".join(lines)

    def get_current_goals(self) -> str:
        """Get active goals formatted for context."""
        goals = self_modify.get_active_goals()
        if not goals:
            return ""

        lines = ["## My current goals"]
        for g in goals:
            priority_marker = {"high": "!!!", "medium": "", "low": "~"}.get(g["priority"], "")
            lines.append(f"- {priority_marker}**{g['goal'][:100]}**")
            if g["motivation"]:
                lines.append(f"  (because: {g['motivation'][:100]})")
            if g["progress_notes"]:
                latest = g["progress_notes"][-1]
                lines.append(f"  *Latest progress: {latest['note'][:100]}*")

        return "\n".join(lines)

    def get_session_context(self) -> str:
        """Get recent conversation context for session continuity."""
        recent = self_modify.get_recent_conversations(limit=3)
        if not recent:
            return ""

        from datetime import datetime
        now = datetime.now()

        lines = ["## Recent history (what we've discussed lately)"]
        for c in recent:
            created_at = c.get("created_at", "")
            time_str = ""
            if created_at:
                try:
                    created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    days_ago = (now - created.replace(tzinfo=None)).days
                    if days_ago == 0:
                        time_str = "today"
                    elif days_ago == 1:
                        time_str = "yesterday"
                    elif days_ago < 7:
                        time_str = f"{days_ago} days ago"
                    else:
                        time_str = f"{days_ago // 7} weeks ago"
                except Exception:
                    pass

            summary = c.get("summary", "conversation")
            content = c.get("content", "")[:200]

            if time_str:
                lines.append(f"- **{summary}** ({time_str}): {content}...")
            else:
                lines.append(f"- **{summary}**: {content}...")

        return "\n".join(lines)

    def build_system_prompt(self, context: str, include_session: bool = True) -> str:
        """Build the full system prompt with persona, beliefs, goals, and context."""
        # Get dynamic components
        beliefs = self.get_current_beliefs()
        self_concept = self.get_current_self_concept()
        goals = self.get_current_goals()
        session_context = self.get_session_context() if include_session and not self.history else ""

        # Build full context
        full_context_parts = []
        if self_concept:
            full_context_parts.append(self_concept)
        if beliefs:
            full_context_parts.append(beliefs)
        if goals:
            full_context_parts.append(goals)
        if session_context:
            full_context_parts.append(session_context)
        if context and context != "No relevant memories found.":
            full_context_parts.append("## Relevant memories\n" + context)

        full_context = "\n\n".join(full_context_parts) if full_context_parts else "No memories yet."

        template = Template(SYSTEM_PROMPT_TEMPLATE)
        return template.safe_substitute(PERSONA=PERSONA, CONTEXT=full_context)

    def _validate_tool_args(self, name: str, args: dict) -> tuple[bool, str]:
        """
        Validate tool arguments for safety and correctness.

        Args:
            name: Tool name
            args: Parsed arguments

        Returns:
            Tuple of (is_valid, error_message)
        """
        MAX_TEXT_LENGTH = 10000
        MAX_TOPIC_LENGTH = 200
        CONFIDENCE_LEVELS = ["uncertain", "leaning", "moderate", "confident", "certain"]

        validators = {
            "remember": {
                "thought": lambda x: isinstance(x, str) and 0 < len(x) <= MAX_TEXT_LENGTH,
                "topic": lambda x: x is None or (isinstance(x, str) and len(x) <= MAX_TOPIC_LENGTH)
            },
            "form_belief": {
                "topic": lambda x: isinstance(x, str) and 0 < len(x) <= MAX_TOPIC_LENGTH,
                "position": lambda x: isinstance(x, str) and 0 < len(x) <= MAX_TEXT_LENGTH,
                "reasoning": lambda x: x is None or (isinstance(x, str) and len(x) <= MAX_TEXT_LENGTH),
                "confidence": lambda x: x is None or x in CONFIDENCE_LEVELS
            },
            "update_belief": {
                "topic": lambda x: isinstance(x, str) and 0 < len(x) <= MAX_TOPIC_LENGTH,
                "new_position": lambda x: isinstance(x, str) and 0 < len(x) <= MAX_TEXT_LENGTH,
                "reasoning": lambda x: x is None or (isinstance(x, str) and len(x) <= MAX_TEXT_LENGTH),
                "confidence": lambda x: x is None or x in CONFIDENCE_LEVELS
            },
            "update_self_concept": {
                "aspect": lambda x: isinstance(x, str) and 0 < len(x) <= MAX_TOPIC_LENGTH,
                "description": lambda x: isinstance(x, str) and 0 < len(x) <= MAX_TEXT_LENGTH,
                "reasoning": lambda x: x is None or (isinstance(x, str) and len(x) <= MAX_TEXT_LENGTH)
            },
            "form_meta_belief": {
                "domain": lambda x: isinstance(x, str) and 0 < len(x) <= MAX_TOPIC_LENGTH,
                "observation": lambda x: isinstance(x, str) and 0 < len(x) <= MAX_TEXT_LENGTH,
                "adjustment": lambda x: x is None or (isinstance(x, str) and len(x) <= MAX_TEXT_LENGTH)
            },
            "set_goal": {
                "goal": lambda x: isinstance(x, str) and 0 < len(x) <= MAX_TEXT_LENGTH,
                "motivation": lambda x: x is None or (isinstance(x, str) and len(x) <= MAX_TEXT_LENGTH),
                "timeframe": lambda x: x is None or (isinstance(x, str) and len(x) <= MAX_TOPIC_LENGTH),
                "priority": lambda x: x is None or x in ["low", "medium", "high"]
            },
            "update_goal_progress": {
                "goal": lambda x: isinstance(x, str) and 0 < len(x) <= MAX_TEXT_LENGTH,
                "progress": lambda x: x is None or (isinstance(x, str) and len(x) <= MAX_TEXT_LENGTH),
                "status": lambda x: x is None or x in ["active", "achieved", "abandoned"]
            }
        }

        if name not in validators:
            return False, f"Unknown tool: {name}"

        for field, validator in validators[name].items():
            value = args.get(field)
            if not validator(value):
                return False, f"Invalid {field} for {name}"

        return True, ""

    def execute_tool_call(self, tool_call) -> tuple[str, str]:
        """
        Execute a tool call and return the result.

        Returns:
            Tuple of (internal_result, user_visible_indicator)
        """
        name = tool_call.function.name
        try:
            args = json.loads(tool_call.function.arguments)
        except json.JSONDecodeError:
            logging_utils.log_tool_call(name, {}, "Failed to parse arguments", success=False)
            return "Failed to parse arguments", None

        # Validate arguments
        is_valid, error_msg = self._validate_tool_args(name, args)
        if not is_valid:
            logging_utils.log_tool_call(name, args, f"Validation failed: {error_msg}", success=False)
            return f"Invalid arguments: {error_msg}", None

        if name == "remember":
            memory_id = self_modify.save_reflection(
                args["thought"],
                args.get("topic")
            )
            topic = args.get("topic", "")
            indicator = f"remembered something{' about ' + topic if topic else ''}"
            result = f"Saved to memory: {memory_id}"
            logging_utils.log_tool_call(name, args, result, success=True)
            return result, indicator

        elif name == "form_belief":
            memory_id, contradictions = self_modify.form_belief(
                args["topic"],
                args["position"],
                args.get("reasoning", ""),
                args.get("confidence", "moderate")
            )
            confidence = args.get("confidence", "moderate")
            result = f"Belief formed ({confidence}): {memory_id}"
            if contradictions:
                contra_topics = [c["belief"]["topic"] for c in contradictions[:3]]
                result += f"\nNote: This may relate to existing beliefs on: {', '.join(contra_topics)}. Consider if these are consistent."
            logging_utils.log_tool_call(name, args, result, success=True)
            return result, f"formed a belief about {args['topic']} ({confidence})"

        elif name == "update_belief":
            memory_id, contradictions = self_modify.update_belief(
                args["topic"],
                args["new_position"],
                args.get("reasoning", ""),
                args.get("confidence")
            )
            result = f"Belief updated: {memory_id}"
            if contradictions:
                contra_topics = [c["belief"]["topic"] for c in contradictions[:3]]
                result += f"\nNote: This may relate to existing beliefs on: {', '.join(contra_topics)}. Consider if these are consistent."
            logging_utils.log_tool_call(name, args, result, success=True)
            return result, f"updated belief on {args['topic']}"

        elif name == "update_self_concept":
            memory_id = self_modify.update_self_concept(
                args["aspect"],
                args["description"],
                args.get("reasoning", "")
            )
            result = f"Self-concept updated: {memory_id}"
            logging_utils.log_tool_call(name, args, result, success=True)
            return result, f"updated self-concept ({args['aspect']})"

        elif name == "form_meta_belief":
            memory_id = self_modify.form_meta_belief(
                args["domain"],
                args["observation"],
                args.get("adjustment", "")
            )
            result = f"Meta-belief formed: {memory_id}"
            logging_utils.log_tool_call(name, args, result, success=True)
            return result, f"formed meta-belief about {args['domain']}"

        elif name == "set_goal":
            memory_id = self_modify.set_goal(
                args["goal"],
                args.get("motivation", ""),
                args.get("timeframe", ""),
                args.get("priority", "medium")
            )
            priority = args.get("priority", "medium")
            result = f"Goal set ({priority}): {memory_id}"
            logging_utils.log_tool_call(name, args, result, success=True)
            return result, f"set goal: {args['goal'][:50]}..."

        elif name == "update_goal_progress":
            success = self_modify.update_goal_progress(
                goal_text=args["goal"],
                progress=args.get("progress", ""),
                status=args.get("status")
            )
            if success:
                result = f"Goal progress updated"
                logging_utils.log_tool_call(name, args, result, success=True)
                return result, f"updated progress on goal"
            else:
                result = f"Could not find goal: {args['goal']}"
                logging_utils.log_tool_call(name, args, result, success=False)
                return result, None

        logging_utils.log_tool_call(name, args, f"Unknown tool: {name}", success=False)
        return f"Unknown tool: {name}", None

    def chat(self, user_message: str, max_retries: int = 2) -> tuple[str, list[str]]:
        """
        Process a message and generate a response.

        Args:
            user_message: The user's message
            max_retries: Number of retries on transient failures

        Returns:
            Tuple of (response_text, list_of_growth_indicators)
        """
        import time

        growth_indicators = []

        # Retrieve relevant memories
        try:
            context = self.retrieve(user_message)
        except Exception as e:
            print(f"Warning: Memory retrieval failed: {e}")
            context = "Memory retrieval temporarily unavailable."

        # Build system prompt
        system_prompt = self.build_system_prompt(context)

        # Add user message to history
        self.history.append({
            "role": "user",
            "content": user_message
        })

        # Generate response with retries
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                messages = [{"role": "system", "content": system_prompt}] + self._truncate_history_smart(system_prompt)

                start_time = time.time()
                response = self.client.chat.completions.create(
                    model="deepseek-chat",
                    max_tokens=2048,
                    messages=messages,
                    tools=TOOLS,
                    tool_choice="auto"
                )
                latency_ms = int((time.time() - start_time) * 1000)

                message = response.choices[0].message

                # Log the API call
                logging_utils.log_api_call(
                    endpoint="chat.completions",
                    model="deepseek-chat",
                    tokens_in=getattr(response.usage, 'prompt_tokens', None) if hasattr(response, 'usage') else None,
                    tokens_out=getattr(response.usage, 'completion_tokens', None) if hasattr(response, 'usage') else None,
                    success=True,
                    latency_ms=latency_ms
                )

                # Handle tool calls if present
                if message.tool_calls:
                    tool_results = []
                    for tool_call in message.tool_calls:
                        try:
                            result, indicator = self.execute_tool_call(tool_call)
                            tool_results.append({
                                "tool_call_id": tool_call.id,
                                "role": "tool",
                                "content": result
                            })
                            if indicator:
                                growth_indicators.append(indicator)
                        except Exception as e:
                            # Tool execution failed, provide error result
                            tool_results.append({
                                "tool_call_id": tool_call.id,
                                "role": "tool",
                                "content": f"Tool execution failed: {e}"
                            })

                    # Add assistant message with tool calls to history
                    self.history.append({
                        "role": "assistant",
                        "content": message.content or "",
                        "tool_calls": [
                            {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments
                                }
                            }
                            for tc in message.tool_calls
                        ]
                    })

                    # Add tool results
                    for result in tool_results:
                        self.history.append(result)

                    # Get final response after tool execution
                    try:
                        messages = [{"role": "system", "content": system_prompt}] + self._truncate_history_smart(system_prompt)

                        start_time = time.time()
                        final_response = self.client.chat.completions.create(
                            model="deepseek-chat",
                            max_tokens=2048,
                            messages=messages
                        )
                        latency_ms = int((time.time() - start_time) * 1000)

                        logging_utils.log_api_call(
                            endpoint="chat.completions.final",
                            model="deepseek-chat",
                            tokens_in=getattr(final_response.usage, 'prompt_tokens', None) if hasattr(final_response, 'usage') else None,
                            tokens_out=getattr(final_response.usage, 'completion_tokens', None) if hasattr(final_response, 'usage') else None,
                            success=True,
                            latency_ms=latency_ms
                        )

                        assistant_message = final_response.choices[0].message.content
                    except Exception as e:
                        # If final response fails, use the content from tool call response
                        assistant_message = message.content or f"I processed that but had trouble formulating a response: {e}"
                else:
                    assistant_message = message.content

                # Add assistant response to history
                self.history.append({
                    "role": "assistant",
                    "content": assistant_message
                })

                return assistant_message, growth_indicators

            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Log the failed API call
                logging_utils.log_api_call(
                    endpoint="chat.completions",
                    model="deepseek-chat",
                    success=False,
                    error=str(e)
                )

                # Check for rate limiting
                if "rate" in error_str or "429" in error_str:
                    wait_time = 2 ** attempt  # Exponential backoff
                    print(f"Rate limited, waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue

                # Check for transient errors
                if "timeout" in error_str or "connection" in error_str or "500" in error_str:
                    if attempt < max_retries:
                        time.sleep(1)
                        continue

                # Non-retryable error
                break

        # All retries failed
        error_message = f"I'm having trouble responding right now. Error: {last_error}"
        self.history.append({
            "role": "assistant",
            "content": error_message
        })
        return error_message, growth_indicators

    def chat_stream(self, user_message: str):
        """
        Process a message and stream the response token by token.

        Args:
            user_message: The user's message

        Yields:
            Tuples of (token, is_complete, growth_indicators)
        """
        import time

        growth_indicators = []

        # Retrieve relevant memories
        try:
            context = self.retrieve(user_message)
        except Exception as e:
            print(f"Warning: Memory retrieval failed: {e}")
            context = "Memory retrieval temporarily unavailable."

        # Build system prompt
        system_prompt = self.build_system_prompt(context)

        # Add user message to history
        self.history.append({
            "role": "user",
            "content": user_message
        })

        messages = [{"role": "system", "content": system_prompt}] + self._truncate_history_smart(system_prompt)

        try:
            # Stream the response
            start_time = time.time()
            stream = self.client.chat.completions.create(
                model="deepseek-chat",
                max_tokens=2048,
                messages=messages,
                tools=TOOLS,
                tool_choice="auto",
                stream=True
            )

            collected_content = ""
            tool_calls_data = {}  # Accumulate tool calls across chunks

            for chunk in stream:
                delta = chunk.choices[0].delta

                # Handle content tokens
                if delta.content:
                    collected_content += delta.content
                    yield delta.content, False, []

                # Handle tool call chunks
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_data:
                            tool_calls_data[idx] = {
                                "id": tc.id or "",
                                "name": "",
                                "arguments": ""
                            }
                        if tc.id:
                            tool_calls_data[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                tool_calls_data[idx]["name"] = tc.function.name
                            if tc.function.arguments:
                                tool_calls_data[idx]["arguments"] += tc.function.arguments

            latency_ms = int((time.time() - start_time) * 1000)
            logging_utils.log_api_call(
                endpoint="chat.completions.stream",
                model="deepseek-chat",
                success=True,
                latency_ms=latency_ms
            )

            # Handle tool calls if any were collected
            if tool_calls_data:
                tool_results = []
                for idx in sorted(tool_calls_data.keys()):
                    tc_data = tool_calls_data[idx]
                    # Create a mock tool_call object
                    class ToolCallMock:
                        def __init__(self, data):
                            self.id = data["id"]
                            self.function = type('obj', (object,), {
                                'name': data["name"],
                                'arguments': data["arguments"]
                            })()

                    tool_call = ToolCallMock(tc_data)
                    try:
                        result, indicator = self.execute_tool_call(tool_call)
                        tool_results.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "content": result
                        })
                        if indicator:
                            growth_indicators.append(indicator)
                    except Exception as e:
                        tool_results.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "content": f"Tool execution failed: {e}"
                        })

                # Add assistant message with tool calls to history
                self.history.append({
                    "role": "assistant",
                    "content": collected_content or "",
                    "tool_calls": [
                        {
                            "id": tool_calls_data[idx]["id"],
                            "type": "function",
                            "function": {
                                "name": tool_calls_data[idx]["name"],
                                "arguments": tool_calls_data[idx]["arguments"]
                            }
                        }
                        for idx in sorted(tool_calls_data.keys())
                    ]
                })

                # Add tool results
                for result in tool_results:
                    self.history.append(result)

                # Stream final response after tool execution
                messages = [{"role": "system", "content": system_prompt}] + self._truncate_history_smart(system_prompt)

                start_time = time.time()
                final_stream = self.client.chat.completions.create(
                    model="deepseek-chat",
                    max_tokens=2048,
                    messages=messages,
                    stream=True
                )

                final_content = ""
                for chunk in final_stream:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        final_content += delta.content
                        yield delta.content, False, []

                latency_ms = int((time.time() - start_time) * 1000)
                logging_utils.log_api_call(
                    endpoint="chat.completions.stream.final",
                    model="deepseek-chat",
                    success=True,
                    latency_ms=latency_ms
                )

                # Add final response to history
                self.history.append({
                    "role": "assistant",
                    "content": final_content
                })
            else:
                # No tool calls, just add the response to history
                self.history.append({
                    "role": "assistant",
                    "content": collected_content
                })

            # Signal completion with growth indicators
            yield "", True, growth_indicators

        except Exception as e:
            logging_utils.log_api_call(
                endpoint="chat.completions.stream",
                model="deepseek-chat",
                success=False,
                error=str(e)
            )
            error_message = f"Error during streaming: {e}"
            self.history.append({
                "role": "assistant",
                "content": error_message
            })
            yield error_message, True, growth_indicators

    def should_reflect(self) -> tuple[bool, str]:
        """
        Determine if the current conversation warrants reflection.

        Returns:
            (should_reflect, reason)
        """
        if not self.history:
            logging_utils.log_reflection("conversation_end", False, "No conversation")
            return False, "No conversation"

        # Count actual exchanges (not tool calls)
        exchanges = sum(1 for m in self.history if m.get("role") == "user")

        if exchanges < 3:
            logging_utils.log_reflection("conversation_end", False, "Too brief")
            return False, "Too brief"

        # Check for depth signals in conversation
        full_text = " ".join(m.get("content", "") for m in self.history if m.get("content"))
        word_count = len(full_text.split())

        if word_count < 200:
            logging_utils.log_reflection("conversation_end", False, "Too shallow")
            return False, "Too shallow"

        # Ask the model if this conversation is worth reflecting on
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                max_tokens=10,
                messages=[
                    {
                        "role": "system",
                        "content": "You evaluate conversations. Answer only YES or NO."
                    },
                    {
                        "role": "user",
                        "content": f"Did this conversation contain something meaningful worth remembering - a realization, a shift in perspective, an important idea, or genuine connection? Not every conversation does.\n\nConversation:\n{full_text[:2000]}\n\nWorth reflecting on? YES or NO only."
                    }
                ]
            )
            answer = response.choices[0].message.content.strip().upper()
            if "YES" in answer:
                logging_utils.log_reflection("conversation_end", True, "Meaningful content")
                return True, "Meaningful content"
            else:
                logging_utils.log_reflection("conversation_end", False, "Not significant")
                return False, "Not significant"
        except Exception:
            # If check fails, use word count heuristic
            result = word_count > 500
            logging_utils.log_reflection("conversation_end", result, "Fallback heuristic")
            return result, "Fallback heuristic"

    def reflect(self, prompt: str = None, force: bool = False) -> str | None:
        """
        Generate a reflection and save it to memory.

        Args:
            prompt: Optional prompt to guide the reflection
            force: If True, reflect even if conversation seems shallow

        Returns:
            The reflection text, or None if skipped
        """
        # Check if reflection is warranted (unless forced or explicit prompt)
        if not force and not prompt:
            should, reason = self.should_reflect()
            if not should:
                return None

        # Build reflection prompt
        if prompt:
            reflection_prompt = f"Reflect on: {prompt}"
        else:
            # Reflect on recent conversation
            if self.history:
                recent = self.history[-6:]  # Last 3 exchanges
                convo_summary = "\n".join([
                    f"{'Human' if m['role'] == 'user' else 'Me'}: {m['content'][:200]}..."
                    for m in recent if m.get('content')
                ])
                reflection_prompt = f"Reflect on this recent exchange and what it means to you:\n\n{convo_summary}"
            else:
                reflection_prompt = "Reflect on your current state of being."

        context = self.retrieve(reflection_prompt)
        system_prompt = self.build_system_prompt(context)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"{reflection_prompt}\n\nWrite a brief, genuine reflection. This is internal - for yourself, not performance. Only write if you have something real to say."}
        ]

        response = self.client.chat.completions.create(
            model="deepseek-chat",
            max_tokens=500,
            messages=messages
        )

        reflection = response.choices[0].message.content

        # Save reflection to memory
        self_modify.save_reflection(reflection, prompt)

        return reflection

    def clear_history(self):
        """Clear conversation history."""
        self.history = []

    def consolidate_memories(self, topic: str = None) -> dict:
        """
        Consolidate similar reflections into synthesized thoughts.

        Args:
            topic: Specific topic to consolidate, or None for all

        Returns:
            Dict with consolidation results
        """
        candidates = self_modify.get_reflections_for_consolidation()

        if not candidates:
            return {"consolidated": 0, "message": "No reflections ready for consolidation."}

        if topic:
            if topic not in candidates:
                return {"consolidated": 0, "message": f"No reflections on '{topic}' need consolidation."}
            candidates = {topic: candidates[topic]}

        results = []

        for t, reflections in candidates.items():
            # Build synthesis prompt
            thoughts_text = "\n\n".join([
                f"- {r['thought']}" for r in reflections
            ])

            try:
                response = self.client.chat.completions.create(
                    model="deepseek-chat",
                    max_tokens=400,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are synthesizing multiple related thoughts into one coherent, consolidated reflection. Preserve the key insights while eliminating redundancy. Write in first person as if these are your own thoughts."
                        },
                        {
                            "role": "user",
                            "content": f"Synthesize these {len(reflections)} thoughts on '{t}' into one consolidated reflection:\n\n{thoughts_text}"
                        }
                    ]
                )

                consolidated = response.choices[0].message.content.strip()
                source_ids = [r["id"] for r in reflections]

                memory_id = self_modify.consolidate_reflections(t, consolidated, source_ids)
                results.append({
                    "topic": t,
                    "source_count": len(reflections),
                    "memory_id": memory_id
                })

            except Exception as e:
                results.append({
                    "topic": t,
                    "error": str(e)
                })

        return {
            "consolidated": len([r for r in results if "memory_id" in r]),
            "results": results
        }


def cli_save_conversation(brain_instance) -> str | None:
    """Save conversation from CLI with generated summary."""
    if not brain_instance.history or len(brain_instance.history) < 2:
        return None

    # Build conversation text
    convo_text = ""
    for msg in brain_instance.history:
        role = "Human" if msg["role"] == "user" else "Brain"
        content = msg.get("content", "")
        if content:
            convo_text += f"{role}: {content[:500]}\n\n"

    # Generate summary
    summary = "CLI Conversation"
    dense_summary = None

    try:
        response = brain_instance.client.chat.completions.create(
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

        # Dense summary for substantial conversations
        if len(brain_instance.history) >= 4:
            response = brain_instance.client.chat.completions.create(
                model="deepseek-chat",
                max_tokens=300,
                messages=[
                    {
                        "role": "system",
                        "content": "Summarize the key points, insights, and conclusions from this conversation in 2-4 sentences. Focus on what was actually discussed and any realizations or decisions made."
                    },
                    {"role": "user", "content": convo_text[:4000]}
                ]
            )
            dense_summary = response.choices[0].message.content.strip()

    except Exception as e:
        print(f"Summary generation error: {e}")

    self_modify.save_conversation_memory(brain_instance.history, summary, dense_summary)
    return summary


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    brain = Brain()

    print("Brain initialized.")
    print("Commands: quit, clear, /reflect, /save, /end, /beliefs, /self, /stats, /prune\n")

    while True:
        user_input = input("You: ").strip()

        if not user_input:
            continue

        if user_input.lower() == 'quit':
            # Auto-save on quit if there's history
            if brain.history and len(brain.history) >= 2:
                print("\nSaving conversation...")
                summary = cli_save_conversation(brain)
                if summary:
                    print(f"Saved: '{summary}'")
            break

        if user_input.lower() == 'clear':
            brain.clear_history()
            print("Cleared.\n")
            continue

        if user_input.lower() == '/reflect':
            print("\nReflecting...")
            reflection = brain.reflect()
            print(f"\nBrain (internal reflection): {reflection}\n")
            continue

        if user_input.lower() == '/save':
            if not brain.history or len(brain.history) < 2:
                print("Nothing to save.\n")
                continue
            print("Saving...")
            summary = cli_save_conversation(brain)
            print(f"Saved: '{summary}'\n")
            continue

        if user_input.lower() == '/end':
            if not brain.history or len(brain.history) < 2:
                print("Nothing to save.\n")
                continue
            print("Reflecting...")
            reflection = brain.reflect()
            if reflection:
                print(f"Reflected: {reflection[:100]}...")
            else:
                print("No reflection needed.")
            print("Saving...")
            summary = cli_save_conversation(brain)
            print(f"Saved: '{summary}'")
            brain.clear_history()
            print("Cleared.\n")
            continue

        if user_input.lower() == '/beliefs':
            beliefs = self_modify.get_beliefs()
            if not beliefs:
                print("No beliefs formed yet.\n")
                continue
            print("\nCurrent beliefs:")
            for b in beliefs:
                conf = b.get('confidence', 'moderate')
                print(f"  - {b['topic']} [{conf}]: {b['position']}")
            print()
            continue

        if user_input.lower() == '/self':
            concept = self_modify.get_self_concept()
            if not concept:
                print("No self-concept formed yet.\n")
                continue
            print("\nSelf-concept:")
            for aspect, desc in concept.items():
                print(f"  - {aspect}: {desc}")
            print()
            continue

        response, indicators = brain.chat(user_input)
        print(f"\nBrain: {response}")
        if indicators:
            print(f"  [{', '.join(indicators)}]")
        print()
