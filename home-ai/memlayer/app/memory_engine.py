import json
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from sentence_transformers import SentenceTransformer
import chromadb


class MemoryEngine:
    """
    Lightweight, fully-local memory engine for home AI use.

    - Uses sentence-transformers (MiniLM) for embeddings
    - Uses ChromaDB persistent store for vector search
    - Uses simple JSON files for structured facts/reminders
    """

    def __init__(
        self,
        base_path: str = "/mnt/models/memlayer",
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    ) -> None:
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

        self.facts_dir = self.base_path / "facts"
        self.facts_dir.mkdir(parents=True, exist_ok=True)

        self.chroma_dir = self.base_path / "chroma"
        self.chroma_dir.mkdir(parents=True, exist_ok=True)

        # Embedding model (local)
        self.model = SentenceTransformer(model_name)

        # Chroma persistent client
        self.client = chromadb.PersistentClient(path=str(self.chroma_dir))
        # Single collection with user_id in metadata
        self.collection = self.client.get_or_create_collection(
            name="memories",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _facts_path(self, user_id: str) -> Path:
        return self.facts_dir / f"{user_id}.json"

    def _load_facts(self, user_id: str) -> Dict[str, Any]:
        path = self._facts_path(user_id)
        if not path.exists():
            return {"profile": {}, "reminders": []}
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            # Corrupt file -> reset
            return {"profile": {}, "reminders": []}

    def _save_facts(self, user_id: str, data: Dict[str, Any]) -> None:
        path = self._facts_path(user_id)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    # ------------------------------------------------------------------
    # Salience & fact extraction
    # ------------------------------------------------------------------
    def is_salient(self, text: str) -> bool:
        """
        Heuristic salience filter.
        Decide whether a user utterance is worth storing as memory.
        """
        t = text.strip()
        if not t:
            return False

        words = t.split()
        if len(words) < 5:
            return False  # too short, usually noise

        lower = t.lower()

        trivial = {"ok", "okay", "thanks", "thank you", "k", "lol", "haha"}
        if lower in trivial:
            return False

        # Strong positive signals
        patterns = [
            r"\bmy name is\b",
            r"\bi am\b",
            r"\bi'm\b",
            r"\bi live in\b",
            r"\bi live at\b",
            r"\bbirthday\b",
            r"\bdoctor\b",
            r"\bappointment\b",
            r"\bmeeting\b",
            r"\bflight\b",
            r"\bbill\b",
            r"\brent\b",
            r"\bmedicine\b",
            r"\bmedication\b",
        ]
        if any(re.search(p, lower) for p in patterns):
            return True

        # Contains a number (dates, amounts, times, etc.)
        if re.search(r"\d", t):
            return True

        # Fallback: if it's a reasonably long utterance, keep it
        return len(words) >= 12

    def extract_facts(self, text: str) -> Dict[str, Any]:
        """
        Very primitive fact extraction for now.
        We can expand this later as needed.
        """
        facts: Dict[str, Any] = {}
        lower = text.lower()

        # Name extraction
        m = re.search(r"\bmy name is ([A-Z][a-zA-Z]*(?: [A-Z][a-zA-Z]*)*)", text)
        if m:
            facts["name"] = m.group(1).strip()

        # Location extraction
        m2 = re.search(r"\bi live in ([A-Z][a-zA-Z]*(?: [A-Z][a-zA-Z]*)*)", text)
        if m2:
            facts["location"] = m2.group(1).strip()

        # We can add more patterns (job, family members, etc.) later.
        return facts

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def write_memory(
        self,
        user_id: str,
        text: str,
        extra_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Decide if text is salient. If yes:
        - Extract structured facts
        - Persist them
        - Embed and store in Chroma
        Returns a dict with info about what happened.
        """
        decision = self.is_salient(text)
        result: Dict[str, Any] = {
            "salient": decision,
            "stored_vector": False,
            "stored_facts": False,
        }

        if not decision:
            return result

        # Facts
        facts = self.extract_facts(text)
        if facts:
            data = self._load_facts(user_id)
            profile = data.get("profile", {})
            profile.update(facts)
            data["profile"] = profile
            self._save_facts(user_id, data)
            result["stored_facts"] = True

        # Vector memory
        emb = self.model.encode([text])[0]  # 1D list
        now = int(time.time())
        meta = {
            "user_id": user_id,
            "ts": now,
        }
        if extra_metadata:
            meta.update(extra_metadata)

        doc_id = str(uuid.uuid4())
        self.collection.add(
            ids=[doc_id],
            documents=[text],
            embeddings=[emb],
            metadatas=[meta],
        )
        result["stored_vector"] = True
        result["id"] = doc_id
        result["timestamp"] = now
        return result

    def search_memory(
        self,
        user_id: str,
        query: str,
        k: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Semantic search over stored memories for a given user.
        """
        if not query.strip():
            return []

        emb = self.model.encode([query])[0]
        res = self.collection.query(
            query_embeddings=[emb],
            n_results=k,
            where={"user_id": user_id},
        )

        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0] if "distances" in res else [None] * len(docs)

        out: List[Dict[str, Any]] = []
        for doc, meta, dist in zip(docs, metas, dists):
            out.append(
                {
                    "text": doc,
                    "metadata": meta,
                    "distance": dist,
                }
            )
        return out

    def get_profile(self, user_id: str) -> Dict[str, Any]:
        """
        Return structured profile facts for a user.
        """
        data = self._load_facts(user_id)
        return data.get("profile", {})

    # Simple reminder handling for future use
    def add_reminder(self, user_id: str, text: str, due_iso: str) -> Dict[str, Any]:
        """
        Store a basic reminder.
        due_iso: ISO 8601 string (e.g. '2025-01-15T20:00:00')
        """
        data = self._load_facts(user_id)
        reminders = data.get("reminders", [])

        r_id = str(uuid.uuid4())
        reminder = {
            "id": r_id,
            "text": text,
            "due": due_iso,
            "created_at": int(time.time()),
        }
        reminders.append(reminder)
        data["reminders"] = reminders
        self._save_facts(user_id, data)
        return reminder

    def list_reminders(self, user_id: str) -> List[Dict[str, Any]]:
        data = self._load_facts(user_id)
        return data.get("reminders", [])
