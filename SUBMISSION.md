# CSOT Week 2 — Research Agent (Gemini + Textual TUI)

A terminal research agent that chains web search, page fetching, and academic paper lookup to answer complex questions autonomously — a self-contained "Perplexity in your terminal."

## Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Create your .env file
cp .env.example .env

# 3. Add API keys to .env
#    GEMINI_API_KEY  — https://aistudio.google.com/app/apikey
#    SERPER_API_KEY  — https://serper.dev (free tier available)

# 4. Run
python research_agent.py
```

## Implementation

The agent is built around Gemini's native function-calling interface. Rather than parsing tool calls from raw text, I declared three tool schemas (`web_search`, `fetch_page`, `search_arxiv`) using `genai.protos.FunctionDeclaration` and passed them directly to `GenerativeModel`. Gemini then decides when and how to call each tool, and the agent loop feeds the results back as a `"user"` turn with `FunctionResponse` parts before asking for the next step.

The three tools are:

- **`web_search`** — posts to the Serper API and returns the top organic results plus any answer-box snippet as a compact string.
- **`fetch_page`** — fetches a URL with `requests`, strips `<script>` and `<style>` blocks, removes all remaining HTML tags with regex, collapses whitespace, and truncates to 4 000 characters so it fits in a context window without waste.
- **`search_arxiv`** — hits the arXiv Atom API and regex-parses titles, IDs, and summaries out of the XML. No third-party XML library needed; the structure is regular enough for a handful of `re.findall` calls.

The TUI is built with Textual. A `RichLog` widget streams every event in real time — tool calls with their arguments, truncated raw results, and the final answer. A docked `Input` at the bottom accepts the next question. Agent execution runs in a `daemon` thread so the UI never freezes, with results posted back via `call_from_thread`.

## Design Choices

I chose Gemini over the scaffold's OpenRouter/DeepSeek setup because Gemini's Python SDK exposes `protos` objects that make tool schemas explicit and strongly typed — there is no ambiguity about whether a part is a text response or a function call. The `gemini-2.5-flash-lite` model is fast and cheap enough for iterative tool loops without noticeable lag.

For HTML cleaning I deliberately avoided `trafilatura` and `markdownify` to keep dependencies minimal. The regex approach is good enough for extracting readable text from most pages; a production system would warrant a proper parser, but for a research prototype it avoids pulling in heavy optional C extensions.

The arXiv integration calls the REST API directly instead of using an MCP server. This removes the need to run a separate process and keeps the agent self-contained in a single Python file.

## Surprises

The trickiest part was feeding tool results back correctly. Gemini requires a separate `"user"` history turn containing `FunctionResponse` parts — one per tool call — immediately after the model turn that requested them. Getting the order and structure wrong (e.g. wrapping results in a `"model"` turn) caused the model to ignore the results silently and hallucinate answers instead.

Threading with Textual also required care: calling `log.write()` directly from a worker thread crashes the event loop. The `call_from_thread` bridge is mandatory.

## Improvements

- **Streaming output** — yield partial tokens as they arrive so the user sees the answer building rather than a blank screen until it's complete.
- **Persistent sessions** — save and reload conversation history so research can continue across runs.
- **MCP integration** — swap the hand-rolled arXiv client for an AlphaXiv MCP server to get richer paper metadata and citation graphs.
- **Result caching** — deduplicate repeated tool calls within a session to avoid redundant API requests.
