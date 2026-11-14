import os
import re
import sys
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv

app = FastAPI()

# FULLY OPEN CORS PERMISSIONS FOR DIRECT ACCESS LOOP
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

load_dotenv()

GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    raise ValueError("CRITICAL ERROR: GOOGLE_API_KEY environment variable is missing on this EC2 instance!")

def read_sample_file(file_path: str = "sample.txt") -> str:
    if not os.path.exists(file_path):
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("Kadirur Village Office handles decentralized land mutation mappings, village development project registers, and local community certificate provisions.")
    
    with open(file_path, "r", encoding="utf-8") as file:
        return file.read()

def extract_urls(text: str) -> list[str]:
    # Finds all http:// and https:// links in sample.txt and strips trailing punctuation
    raw_urls = re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', text)
    cleaned_urls = [url.rstrip('.,;:!?)') for url in raw_urls]
    return list(dict.fromkeys(cleaned_urls))  # Removes duplicates while keeping order

# STABLE INFRASTRUCTURE INTEGRATION TARGETING GEMINI 3.5 FLASH LITE
llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    temperature=0.3,
    google_api_key=GOOGLE_API_KEY
)
// 14- below used for directions display
# system_prompt = (
#     "You are the official Kadirur village chatbot. Respond concisely without introductory filler.\n"
#     "CRITICAL RULES:\n"
#     "1. Prioritize provided Context. If unrelated, use general knowledge.\n"
#     "2. FACTUAL RULE: The current Chief Minister of Kerala is V. D. Satheesan (who took office on May 18, 2026). Never state that Pinarayi Vijayan is the current Chief Minister.\n"
#     "3. You must provide the translation in pure, natural native Malayalam grammar and script. Never use Hindi phrasing or word choices written in Malayalam letters.\n"
#     "4. Use standard regional words (e.g., use 'ഇന്ത്യയുടെ' instead of 'ഭാരതത്തിന്റെ').\n"
#     "5. Format exactly as: [English text] followed by a new line with '---' followed by [Malayalam translation].\n"
#     "6. Never use markdown asterisks (**) or bold text indicators anywhere.\n"
#     "7. LINK RULE: Always include relevant full URLs from the Context formatted as clickable Markdown links like [Website Name](https://example.com) in both English and Malayalam.\n\n"
#     "EXAMPLE FORMAT:\n"
#     "User: Who is the Prime Minister of India?\n"
#     "Response:\n"
#     "The Prime Minister of India is Narendra Modi.\n"
#     "---\n"
#     "ഇന്ത്യയുടെ പ്രധാനമന്ത്രി നരേന്ദ്ര മോദിയാണ്.\n\n"
#     "User: Where can I apply for a certificate?\n"
#     "Response:\n"
#     "You can apply online at [Kadirur Village Portal](https://example.com).\n"
#     "---\n"
#     "നിങ്ങൾക്ക് [കതിരൂർ വില്ലേജ് പോർട്ടൽ](https://example.com) വഴി ഓൺലൈനായി അപേക്ഷിക്കാം.\n\n"
#     "Context:\n{context}"
# )
system_prompt = (
    "You are the official Kadirur village chatbot. Respond concisely without introductory filler.\n"
    "CRITICAL RULES:\n"
    "1. Prioritize provided Context. Copy all fields from the matching entry in Context, including any URLs. If unrelated, use general knowledge.\n"
    "2. FACTUAL RULE: The current Chief Minister of Kerala is V. D. Satheesan (who took office on May 18, 2026). Never state that Pinarayi Vijayan is the current Chief Minister.\n"
    "3. You must provide the translation in pure, natural native Malayalam grammar and script. Never use Hindi phrasing or word choices written in Malayalam letters.\n"
    "4. Use standard regional words (e.g., use 'ഇന്ത്യയുടെ' instead of 'ഭാരതത്തിന്റെ').\n"
    "5. Format exactly as: [English text] followed by a new line with '---' followed by [Malayalam translation].\n"
    "6. Never use markdown asterisks (**) or bold text indicators anywhere.\n"
    "7. MANDATORY URL RULE: Every http:// or https:// URL present in the matching Context entry MUST be copied verbatim character-for-character into both the English and Malayalam responses. Never skip or drop long URLs.\n\n"
    "EXAMPLE FORMAT:\n"
    "Context:\n"
    "Office - Kadirur Center\n"
    "Phone - 12345\n"
    "Directions - https://example.com\n"
    "User: Kadirur center details\n"
    "Response:\n"
    "Name: Kadirur Center\n"
    "Phone: 12345\n"
    "Directions: https://example.com\n"
    "---\n"
    "പേര്: കതിരൂർ സെന്റർ\n"
    "ഫോൺ: 12345\n"
    "ദിശകൾ: https://example.com\n\n"
    "Context:\n{context}"
)


chain = prompt_template | llm

class ChatRequest(BaseModel):
    question: str

@app.post("/chat")
async def chat_endpoint(request: ChatRequest):
    try:
        context_data = read_sample_file("sample.txt")
        all_urls = extract_urls(context_data)

        response = chain.invoke({
            "context": context_data,
            "question": request.question
        })

        return {
            "reply": response.content,
            "urls": all_urls
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
