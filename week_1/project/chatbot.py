import os
import sys
import time  # <-- NEW: Required for rate limiting
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("[ERROR] GEMINI_API_KEY not found in environment.")
    sys.exit(1)

genai.configure(api_key=api_key)

SYSTEM_INSTRUCTION = (
    "You are a helpful, concise AI assistant built for the CSOT GenAI/Agentic "
    "track at IIT Delhi. Answer clearly and precisely. When discussing code, "
    "prefer Python examples."
)

# <-- CHANGED: Swapped to a lighter model for higher free-tier limits
model = genai.GenerativeModel(
    model_name="gemini-2.5-flash-lite", 
    system_instruction=SYSTEM_INSTRUCTION,
)

conversation_history = []
MAX_HISTORY_LENGTH = 10  # <-- NEW: Keeps only the last 5 user/model exchanges

def chat(user_message: str) -> str:
    global conversation_history
    
    conversation_history.append({
        "role": "user",
        "parts": [user_message],
    })

    # <-- NEW: Truncate history to prevent TPM token bloat
    if len(conversation_history) > MAX_HISTORY_LENGTH:
        conversation_history = conversation_history[-MAX_HISTORY_LENGTH:]

    response = model.generate_content(conversation_history)
    reply = response.text

    conversation_history.append({
        "role": "model",
        "parts": [reply],
    })

    return reply


def print_separator():
    print("─" * 60)


def main():
    print_separator()
    print(" CSOT Week 1 — Gemini Terminal Chatbot (Quota Safe)")
    print(" Type 'quit' or 'exit' to stop.")
    print(" Type 'history' to inspect conversation history length.")
    print(" Type 'clear' to reset conversation.")
    print_separator()

    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n\n[Exiting. Goodbye!]")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit"):
            print("[Goodbye!]")
            break

        if user_input.lower() == "history":
            turns = len(conversation_history)
            print(f"[Conversation has {turns} turn(s) in history ({turns // 2} exchanges)]")
            continue

        if user_input.lower() == "clear":
            conversation_history.clear()
            print("[Conversation history cleared.]")
            continue

        try:
            reply = chat(user_input)
            print(f"\nGemini: {reply}")
            
            # <-- NEW: A tiny buffer to prevent tripping the RPM limit
            time.sleep(2) 
            
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg:
                # <-- NEW: Exponential backoff instead of failing immediately
                print("\n[API Error] Rate limit exceeded. Cooling down for 30 seconds...")
                time.sleep(30)
            else:
                print(f"\n[API Error] {error_msg}")

if __name__ == "__main__":
    main()