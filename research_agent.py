import os
import sys
import json
import threading
from dotenv import load_dotenv
import google.generativeai as genai
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, RichLog
from textual.containers import VerticalScroll

from tools import web_search, fetch_page, search_arxiv

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("[ERROR] GEMINI_API_KEY not found in .env")
    sys.exit(1)

genai.configure(api_key=api_key)

# ── Tool schemas for Gemini function calling ──────────────────────────────────

TOOL_DECLARATIONS = genai.protos.Tool(
    function_declarations=[
        genai.protos.FunctionDeclaration(
            name="web_search",
            description="Search the web for current information, news, or facts.",
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "query": genai.protos.Schema(
                        type=genai.protos.Type.STRING,
                        description="The search query string",
                    )
                },
                required=["query"],
            ),
        ),
        genai.protos.FunctionDeclaration(
            name="fetch_page",
            description="Fetch and read the full text of a webpage given its URL.",
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "url": genai.protos.Schema(
                        type=genai.protos.Type.STRING,
                        description="The URL to fetch",
                    )
                },
                required=["url"],
            ),
        ),
        genai.protos.FunctionDeclaration(
            name="search_arxiv",
            description="Search arXiv for academic/research papers on a topic.",
            parameters=genai.protos.Schema(
                type=genai.protos.Type.OBJECT,
                properties={
                    "query": genai.protos.Schema(
                        type=genai.protos.Type.STRING,
                        description="Research topic or paper keywords",
                    )
                },
                required=["query"],
            ),
        ),
    ]
)

SYSTEM_INSTRUCTION = (
    "You are a research assistant with access to web search, page fetching, "
    "and academic paper search tools. When answering a question, use your tools "
    "to gather current and accurate information before synthesising a final answer. "
    "Cite sources (URLs) in your answer where possible."
)

model = genai.GenerativeModel(
    model_name="gemini-2.5-flash-lite",
    system_instruction=SYSTEM_INSTRUCTION,
    tools=[TOOL_DECLARATIONS],
)

# ── Tool dispatcher ───────────────────────────────────────────────────────────

TOOL_MAP = {
    "web_search": web_search,
    "fetch_page": fetch_page,
    "search_arxiv": search_arxiv,
}


def dispatch_tool(name: str, args: dict) -> str:
    fn = TOOL_MAP.get(name)
    if fn is None:
        return f"[ERROR] Unknown tool: {name}"
    return fn(**args)


# ── Agent loop ────────────────────────────────────────────────────────────────

def run_agent(question: str, log_fn):
    """
    Runs the Gemini agent loop for one question.
    log_fn(text, style) is called for each event so the TUI can display it.
    """
    history = [{"role": "user", "parts": [question]}]

    while True:
        response = model.generate_content(history)
        candidate = response.candidates[0]
        content = candidate.content

        # Append model turn to history
        history.append({"role": "model", "parts": content.parts})

        # Check for tool calls
        tool_calls = [p for p in content.parts if hasattr(p, "function_call") and p.function_call.name]

        if not tool_calls:
            # No more tool calls — extract final text
            text_parts = [p.text for p in content.parts if hasattr(p, "text") and p.text]
            final = "\n".join(text_parts).strip()
            log_fn(f"\n[bold green]Answer:[/bold green]\n{final}", "")
            break

        # Execute each tool call and build function_response parts
        tool_response_parts = []
        for part in tool_calls:
            fc = part.function_call
            args = dict(fc.args)
            log_fn(f"\n[bold cyan]Tool:[/bold cyan] [yellow]{fc.name}[/yellow]({json.dumps(args, ensure_ascii=False)})", "")
            result = dispatch_tool(fc.name, args)
            log_fn(f"[dim]{result[:500]}{'…' if len(result) > 500 else ''}[/dim]", "")

            tool_response_parts.append(
                genai.protos.Part(
                    function_response=genai.protos.FunctionResponse(
                        name=fc.name,
                        response={"result": result},
                    )
                )
            )

        # Feed tool results back as a user turn
        history.append({"role": "user", "parts": tool_response_parts})


# ── Textual TUI ───────────────────────────────────────────────────────────────

class ResearchApp(App):
    CSS = """
    Screen {
        layout: vertical;
    }
    RichLog {
        border: solid $primary;
        height: 1fr;
        padding: 1 2;
    }
    Input {
        dock: bottom;
        height: 3;
        border: solid $accent;
    }
    """

    TITLE = "CSOT Week 2 — Research Agent"
    BINDINGS = [("ctrl+c", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Header()
        with VerticalScroll():
            yield RichLog(highlight=True, markup=True, wrap=True, id="log")
        yield Input(placeholder="Ask a research question… (Enter to send)", id="query")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(Input).focus()
        log = self.query_one(RichLog)
        log.write("[bold]Welcome to the CSOT Research Agent.[/bold]")
        log.write("Powered by Gemini + web search + arXiv.\n")
        log.write("[dim]Tools available: web_search  |  fetch_page  |  search_arxiv[/dim]\n")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        question = event.value.strip()
        if not question:
            return
        self.query_one(Input).value = ""
        log = self.query_one(RichLog)
        log.write(f"\n[bold magenta]You:[/bold magenta] {question}")
        log.write("[dim]Thinking…[/dim]")

        def _run():
            def _log(text, _style):
                self.call_from_thread(log.write, text)

            try:
                run_agent(question, _log)
            except Exception as e:
                self.call_from_thread(log.write, f"[red][ERROR] {e}[/red]")

        threading.Thread(target=_run, daemon=True).start()


if __name__ == "__main__":
    ResearchApp().run()
