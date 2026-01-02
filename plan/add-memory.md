# Integration Plan: Graph‑Based Memory (MyCelium) into Home AI Project

## Current project status (dev branch)

The `home-ai-soa` repository's `dev` branch provides a **local‑only AI
assistant** with specialized finance analysis, a web dashboard and a
simple long‑term memory service.

-   **MemLayer:** The current memory service (`memlayer`) stores
    conversation snippets and facts in a **ChromaDB vector store** using
    a MiniLM embedding model. It persists structured profile facts and
    reminders in per‑user JSON files and provides API endpoints for
    writing/searching memories and managing
    reminders[\[1\]](https://github.com/harryneopotter/home-ai-soa/blob/f5bf8f4daf48b0540573f7122193e210638086c7/home-ai/memlayer/app/memory_engine.py#L46-L113)[\[2\]](https://github.com/harryneopotter/home-ai-soa/blob/f5bf8f4daf48b0540573f7122193e210638086c7/home-ai/memlayer/app/main.py#L75-L119).
    Memories are stored only if they pass a simple salience heuristic
    (min 5 words, presence of numbers or certain keywords,
    etc.)[\[3\]](https://github.com/harryneopotter/home-ai-soa/blob/f5bf8f4daf48b0540573f7122193e210638086c7/home-ai/memlayer/app/memory_engine.py#L68-L112).
-   **Orchestrator:** The `SOA1Agent` retrieves the top‑k memories via
    `MemoryClient.search_memory` and formats them into a context block
    for the
    LLM[\[4\]](https://github.com/harryneopotter/home-ai-soa/blob/f5bf8f4daf48b0540573f7122193e210638086c7/home-ai/soa1/agent.py#L201-L230).
    After answering a query, it writes a summary (question/answer +
    timestamps) back to
    memory[\[5\]](https://github.com/harryneopotter/home-ai-soa/blob/f5bf8f4daf48b0540573f7122193e210638086c7/home-ai/soa1/agent.py#L248-L267).
    The orchestrator currently uses only vector search; there is **no
    graph‑based memory** or long‑term conversation history beyond the
    last 20 messages (handled in the chat API via the `chat_history`
    parameter). The roadmap notes that "add conversation memory to
    MemLayer for cross‑session context" is still
    pending[\[6\]](https://github.com/harryneopotter/home-ai-soa/blob/f5bf8f4daf48b0540573f7122193e210638086c7/RemAssist/NEXT_TASKS.md#L29-L34).
-   **Finance pipeline:** The finance agent MVP and dashboard are
    complete. Chat history persistence, cross‑document comparison,
    merchant normalization and model call validation are in
    place[\[7\]](https://github.com/harryneopotter/home-ai-soa/blob/f5bf8f4daf48b0540573f7122193e210638086c7/RemAssist/NEXT_TASKS.md#L9-L23).
    Security hardening, rate limiting and other tasks remain in the
    backlog[\[8\]](https://github.com/harryneopotter/home-ai-soa/blob/f5bf8f4daf48b0540573f7122193e210638086c7/RemAssist/NEXT_TASKS.md#L53-L57).

Thus, while the system now has robust transaction analysis and a simple
vector memory, it lacks **graph‑based memory features**, concept
clustering or sophisticated context retrieval. The dev branch currently
relies on heuristics to decide what to remember and stores facts in flat
JSON/Chroma
structures[\[3\]](https://github.com/harryneopotter/home-ai-soa/blob/f5bf8f4daf48b0540573f7122193e210638086c7/home-ai/memlayer/app/memory_engine.py#L68-L112)[\[9\]](https://github.com/harryneopotter/home-ai-soa/blob/f5bf8f4daf48b0540573f7122193e210638086c7/home-ai/memlayer/app/memory_engine.py#L138-L191).
The **LightRAG** concept and advanced memory plans are not yet
implemented.

## Summary of MyCelium memory features

The MyCelium repository implements a **knowledge‑graph‑powered memory**
designed to give an AI agent persistent, structured long‑term recall.
Key capabilities include:

-   **GraphMemory:** Entities and relations extracted from user
    interactions are stored as nodes and edges in a NetworkX graph;
    embeddings are stored in ChromaDB collections. The `GraphMemory`
    class provides methods to add/update entities and relations, search
    notes, cluster concepts, find \"connectors\" (bridge nodes) and
    retrieve a relevant subgraph via vector search plus breadth‑first
    traversal[\[10\]](https://raw.githubusercontent.com/out-of-cheese-error/mycelium/main/backend/app/memory_store.py#:~:text=def%20add_entity,str%2C%20description%3A%20str)[\[11\]](https://raw.githubusercontent.com/out-of-cheese-error/mycelium/main/backend/app/memory_store.py#:~:text=def%20retrieve_context,query_embedding%5D%2C%20n_results%3Dk).
-   **Automatic extraction:** An LLM prompt instructs the model to
    identify entities and relations from each interaction (long‑term
    useful facts). The extracted JSON is used to update the knowledge
    graph[\[12\]](https://raw.githubusercontent.com/out-of-cheese-error/mycelium/main/backend/app/agent.py#:~:text=extraction_prompt%20%3D%20f,to%20build%20a%20knowledge%20graph)[\[13\]](https://raw.githubusercontent.com/out-of-cheese-error/mycelium/main/backend/app/agent.py#:~:text=,loads%28json_str).
-   **Notes and concepts:** MyCelium has a note system with semantic
    search, concept clustering to group related nodes, detection of
    \"hot topics\" and connectors, graph visualization and the ability
    to ingest content from multiple sources (Wikipedia, Project
    Gutenberg, web
    pages)[\[14\]](https://raw.githubusercontent.com/out-of-cheese-error/mycelium/main/README.md#:~:text=).

These features provide structured memory and rich retrieval capabilities
that go beyond simple vector similarity.

## Design constraints for Home AI memory integration

Our project prioritizes **offline operation, privacy and modularity**.
Any integration must respect:

1.  **Offline only:** All model inference and data storage must occur
    locally. No cloud APIs or external web scraping are allowed.
    Ingestion must be restricted to user‑provided files or local data
    sources.
2.  **Safety/guardrails:** Memory extraction and retrieval must be
    moderated. Outputs must be validated against a schema, and sensitive
    or inappropriate content should be filtered. The assistant should
    not store or surface highly personal or sensitive information
    without explicit user consent.
3.  **Modular architecture:** The memory service must remain a separate
    microservice (similar to `memlayer`), accessible via a stable API so
    that multiple pods (finance, legal, medical) can share it without
    interfering with each other.
4.  **User consent:** Long‑term memory and analysis should happen only
    after the user consents. Persistent storage of documents or
    extracted knowledge must be transparent and revocable.
5.  **Extendability:** The design should support future features such as
    LightRAG retrieval with citations and graph‑based reasoning while
    keeping the finance MVP stable.

## Integration plan

This plan outlines how to incorporate MyCelium's graph‑based memory
features into the Home AI project while meeting the above constraints.

### 1. Fork and modularize GraphMemory

-   **Isolate GraphMemory:** Extract the `GraphMemory` class (including
    its reliance on NetworkX and ChromaDB) from MyCelium into a
    **separate Python package** under `home-ai/memory-graph/` (or a
    dedicated repo). Remove references to web ingestion and UI
    components.
-   **Create a microservice:** Build a new FastAPI service (e.g.,
    `MemGraph`) similar to `memlayer/app/main.py`. Expose endpoints for:
-   `POST /graph/entities` -- add/update entity and embedding.
-   `POST /graph/relations` -- add/update relation.
-   `POST /graph/ingest` -- process a user interaction (text) via an
    extraction step and update the graph. See §2 below for extraction.
-   `POST /graph/search` -- given a query, return a context block and
    metadata (retrieved nodes/edges) using vector search +
    BFS[\[11\]](https://raw.githubusercontent.com/out-of-cheese-error/mycelium/main/backend/app/memory_store.py#:~:text=def%20retrieve_context,query_embedding%5D%2C%20n_results%3Dk).
-   Additional endpoints for notes, reminders and concept clustering may
    be added later.
-   **Namespace support:** The service must take a `user_id` and
    optional `pod_id` to ensure each user/pod has its own subgraph. This
    prevents cross‑pod memory contamination and supports multi‑tenant
    use.

### 2. Localize entity extraction

-   **Reuse existing prompt:** Adapt MyCelium's entity‑extraction prompt
    (the JSON schema describing `entities` and
    `relations`)[\[12\]](https://raw.githubusercontent.com/out-of-cheese-error/mycelium/main/backend/app/agent.py#:~:text=extraction_prompt%20%3D%20f,to%20build%20a%20knowledge%20graph).
    Remove any references to web sources or remote ingestion. Emphasize
    long‑term, factual information and require the model to ignore
    chit‑chat.
-   **Local LLM:** Use the existing local model (`NemoAgent:latest` via
    Ollama). Add a helper method in the orchestrator or memory client to
    call the model with the extraction prompt and the user's message.
    The response must be validated with Pydantic to ensure the JSON
    structure is correct before updating the graph (guardrail). If
    validation fails, log and skip.
-   **Consent gate:** Only run extraction and update the graph if the
    user has granted long‑term memory permission. Provide a per‑session
    or per‑pod setting to enable/disable graph‑based storage.

### 3. Integrate with current MemLayer and orchestrator

-   **Dual memory:** Keep the existing vector memory (`memlayer`) for
    simple salience‑based recall. Add GraphMemory as **optional**
    secondary memory. Extend `MemoryClient` to call the graph service's
    search endpoint after performing the current vector search. Merge
    the results or prioritize graph context when available.
-   **Context formatting:** Modify `SOA1Agent._format_memory_context()`
    to handle graph contexts. For example, include a section like
    `[KNOWLEDGE GRAPH CONTEXT]` with a list of retrieved entities and
    their relations followed by notes. Provide citations or node
    identifiers so the user can explore via the UI.
-   **Memory write:** After each agent interaction, generate both the
    summary text (as today) and run the extraction prompt to update the
    graph. Persist both the vector summary and the graph nodes/edges in
    parallel. Wrap this in a try/except so that failure to update the
    graph does not break the
    agent[\[5\]](https://github.com/harryneopotter/home-ai-soa/blob/f5bf8f4daf48b0540573f7122193e210638086c7/home-ai/soa1/agent.py#L248-L267).

### 4. Guardrails and safety

-   **Schema validation:** Use Pydantic models to validate the output of
    the extraction prompt (e.g., ensure that each entity has a
    name/type/description and each relation references existing
    entities). Reject responses that deviate from the schema or contain
    offensive content.
-   **Sensitive information filtering:** Enhance the `is_salient`
    heuristic and add a `is_sensitive` function. Do not store
    information that contains social security numbers, bank account
    numbers, precise location, or medical diagnoses without explicit
    user confirmation. Provide a redaction mechanism that replaces such
    data with placeholders before storage.
-   **User controls:** Expose API endpoints or UI settings to allow the
    user to:
-   View and delete graph memories and notes.
-   Export or clear their memory data.
-   Disable/enable graph storage per pod.

### 5. Offline‑only ingestion and references

-   **Remove cloud dependencies:** Do not include MyCelium's built‑in
    ingestion for Wikipedia or web pages. Instead, rely on the
    **existing document ingestion pipeline** in `finance-agent` and
    future pods to supply content. If cross‑document ingestion is
    needed, run extraction locally on parsed text (e.g., from PDFs) and
    update the graph accordingly.
-   **Static benchmarks:** Where MyCelium used public benchmarks (e.g.,
    national spending averages), include these as **static JSON files**
    within the repository so they are available offline. Document the
    source and date for transparency.

### 6. UI and observability

-   **Graph visualization:** Extend the web dashboard to show basic
    views of the knowledge graph. For example, a `Graph` tab that lists
    top entities, recent relations and concept clusters. Use the graph
    metadata returned from `/graph/search` to draw a simple network
    (e.g., with D3.js) without exposing raw data externally.
-   **Monitoring:** Extend the existing `/monitoring` endpoint to report
    statistics about the graph service: number of nodes, edges, failed
    extractions, memory usage and last extraction run. Include audit
    logs for memory operations with timestamps and user IDs.

### 7. Implementation roadmap (phased)

1.  **Prototype GraphMemory service (1--2 sprints):** Fork `GraphMemory`
    and create a microservice with endpoints and tests. Integrate local
    LLM extraction and Pydantic validation. Provide CLI or test scripts
    to ingest sample conversations and retrieve contexts.
2.  **Orchestrator integration (1 sprint):** Extend `MemoryClient` and
    `SOA1Agent` to support graph search/write. Provide a feature flag to
    enable/disable graph memory. Update the system prompt to include
    `[KNOWLEDGE GRAPH CONTEXT]` when present.
3.  **UI and controls (1 sprint):** Build basic UI elements for graph
    exploration and user controls (view/delete/export memory). Add
    monitoring metrics.
4.  **Policy enforcement and user consent (1 sprint):** Implement
    guardrail checks, redaction logic and per‑pod consent settings.
    Document policies and update privacy notice.
5.  **LightRAG extension (future):** After the graph memory integration
    is stable, extend retrieval to implement LightRAG: use concept
    clusters and connectors to select a minimal set of nodes and include
    citations. Support retrieval of subgraphs across multiple documents
    and pods.

## Benefits of integrating graph‑based memory

-   **Richer context:** GraphMemory provides structured relationships
    between entities, enabling the assistant to reason over personal
    facts (e.g., linking a bank transaction to a merchant and category).
    This can improve accuracy and reduce hallucinations compared to flat
    vector memories.
-   **Better retrieval:** The BFS + vector approach can surface relevant
    past interactions and connect them to current
    queries[\[11\]](https://raw.githubusercontent.com/out-of-cheese-error/mycelium/main/backend/app/memory_store.py#:~:text=def%20retrieve_context,query_embedding%5D%2C%20n_results%3Dk),
    improving recall across sessions and documents.
-   **Concept clustering:** Automatic clustering of related entities
    supports summarization and "hot topic" detection, which can help the
    assistant prioritise information and generate high‑level summaries.
-   **Modular foundation for LightRAG:** By adopting GraphMemory now, we
    lay the groundwork for a full graph‑enhanced RAG implementation with
    citations and cross‑document reasoning.

## Conclusion

The current Home AI project has matured significantly in finance
analysis and basic memory but still relies on a simple vector store for
context. The **MyCelium memory architecture** offers a powerful and
extensible graph‑based approach that can enhance long‑term memory and
retrieval. By forking and localizing GraphMemory, adding local entity
extraction, implementing guardrails and ensuring offline operation, we
can integrate these features without compromising privacy or modularity.
The phased roadmap above balances immediate improvements (richer memory
and retrieval) with the longer‑term vision of LightRAG and multi‑pod
knowledge management.

[\[1\]](https://github.com/harryneopotter/home-ai-soa/blob/f5bf8f4daf48b0540573f7122193e210638086c7/home-ai/memlayer/app/memory_engine.py#L46-L113)
[\[3\]](https://github.com/harryneopotter/home-ai-soa/blob/f5bf8f4daf48b0540573f7122193e210638086c7/home-ai/memlayer/app/memory_engine.py#L68-L112)
[\[9\]](https://github.com/harryneopotter/home-ai-soa/blob/f5bf8f4daf48b0540573f7122193e210638086c7/home-ai/memlayer/app/memory_engine.py#L138-L191)
memory_engine.py

<https://github.com/harryneopotter/home-ai-soa/blob/f5bf8f4daf48b0540573f7122193e210638086c7/home-ai/memlayer/app/memory_engine.py>

[\[2\]](https://github.com/harryneopotter/home-ai-soa/blob/f5bf8f4daf48b0540573f7122193e210638086c7/home-ai/memlayer/app/main.py#L75-L119)
main.py

<https://github.com/harryneopotter/home-ai-soa/blob/f5bf8f4daf48b0540573f7122193e210638086c7/home-ai/memlayer/app/main.py>

[\[4\]](https://github.com/harryneopotter/home-ai-soa/blob/f5bf8f4daf48b0540573f7122193e210638086c7/home-ai/soa1/agent.py#L201-L230)
[\[5\]](https://github.com/harryneopotter/home-ai-soa/blob/f5bf8f4daf48b0540573f7122193e210638086c7/home-ai/soa1/agent.py#L248-L267)
agent.py

<https://github.com/harryneopotter/home-ai-soa/blob/f5bf8f4daf48b0540573f7122193e210638086c7/home-ai/soa1/agent.py>

[\[6\]](https://github.com/harryneopotter/home-ai-soa/blob/f5bf8f4daf48b0540573f7122193e210638086c7/RemAssist/NEXT_TASKS.md#L29-L34)
[\[7\]](https://github.com/harryneopotter/home-ai-soa/blob/f5bf8f4daf48b0540573f7122193e210638086c7/RemAssist/NEXT_TASKS.md#L9-L23)
[\[8\]](https://github.com/harryneopotter/home-ai-soa/blob/f5bf8f4daf48b0540573f7122193e210638086c7/RemAssist/NEXT_TASKS.md#L53-L57)
NEXT_TASKS.md

<https://github.com/harryneopotter/home-ai-soa/blob/f5bf8f4daf48b0540573f7122193e210638086c7/RemAssist/NEXT_TASKS.md>

[\[10\]](https://raw.githubusercontent.com/out-of-cheese-error/mycelium/main/backend/app/memory_store.py#:~:text=def%20add_entity,str%2C%20description%3A%20str)
[\[11\]](https://raw.githubusercontent.com/out-of-cheese-error/mycelium/main/backend/app/memory_store.py#:~:text=def%20retrieve_context,query_embedding%5D%2C%20n_results%3Dk)
raw.githubusercontent.com

<https://raw.githubusercontent.com/out-of-cheese-error/mycelium/main/backend/app/memory_store.py>

[\[12\]](https://raw.githubusercontent.com/out-of-cheese-error/mycelium/main/backend/app/agent.py#:~:text=extraction_prompt%20%3D%20f,to%20build%20a%20knowledge%20graph)
[\[13\]](https://raw.githubusercontent.com/out-of-cheese-error/mycelium/main/backend/app/agent.py#:~:text=,loads%28json_str)
raw.githubusercontent.com

<https://raw.githubusercontent.com/out-of-cheese-error/mycelium/main/backend/app/agent.py>

[\[14\]](https://raw.githubusercontent.com/out-of-cheese-error/mycelium/main/README.md#:~:text=)
raw.githubusercontent.com

<https://raw.githubusercontent.com/out-of-cheese-error/mycelium/main/README.md>
