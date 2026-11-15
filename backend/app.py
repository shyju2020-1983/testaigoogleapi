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

# Below 2 line code is for local environment execution 
if not GOOGLE_API_KEY:
    raise ValueError("CRITICAL ERROR: GOOGLE_API_KEY environment variable is missing on this EC2 instance!")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLE_FILE_PATH = os.path.join(BASE_DIR, "sample.txt")

def read_sample_file(file_path: str = SAMPLE_FILE_PATH) -> str:
    if not os.path.exists(file_path):
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("Kadirur Village Office handles decentralized land mutation mappings, village development project registers, and local community certificate provisions.")
    
    with open(file_path, "r", encoding="utf-8") as file:
        return file.read()

def get_matching_blocks(context: str, question: str) -> str:
    """Finds the exact matching section(s) in sample.txt including all multi-line continuations."""
    blocks = re.split(r'\n\s*\n', context.strip())
    q_words = set(re.findall(r'\w+', question.lower()))
    # Ignore common stop words so matching focuses on meaningful keywords
    stop_words = {'what', 'is', 'the', 'in', 'of', 'about', 'tell', 'me', 'give', 'list', 'all', 'for', 'and', 'to', 'a', 'an', 'kadirur'}
    keywords = q_words - stop_words or q_words

    matched = [b.strip() for b in blocks if keywords & set(re.findall(r'\w+', b.lower()))]
    return "\n\n".join(matched) if matched else context

def get_matching_urls(context: str, question: str) -> list[str]:
    blocks = re.split(r'\n\s*\n', context.strip())
    q_words = set(re.findall(r'\w+', question.lower()))
    matched_urls = []
    for block in blocks:
        if q_words & set(re.findall(r'\w+', block.lower())):
            urls = re.findall(r'https?://[^\s<>"\']+', block)
            matched_urls.extend(u.rstrip('.,;:!?)') for u in urls)
    return list(dict.fromkeys(matched_urls))

def format_as_vertical_list(text: str) -> str:
    cleaned_lines = []

    for raw_line in text.strip().splitlines():
        if not raw_line.strip():
            continue

        is_indented = raw_line.startswith(('  ', '\t'))
        stripped = raw_line.strip()

        # Check if this line originally had a bullet marker (•, -, *)
        had_bullet = bool(re.match(r'^[-*•]\s+', stripped))
        line_no_bullet = re.sub(r'^[-*•]+\s*', '', stripped)

        # 1. Section headers ending with ':' (e.g., "Tailors in Kadirur:") -> NO bullet point
        if line_no_bullet.endswith(':'):
            cleaned_lines.append(line_no_bullet)
            continue

        # 2. URLs -> NO bullet point, indented cleanly
        if line_no_bullet.startswith(('http://', 'https://')) or 'http://' in line_no_bullet or 'https://' in line_no_bullet:
            cleaned_lines.append(f"  {line_no_bullet}")
            continue

        # 3. Lines that had a bullet in Context/response -> Keep '• '
        if had_bullet:
            cleaned_lines.append(f"• {line_no_bullet}")
            continue

        # 4. Continuation lines without a bullet -> Keep on next line WITHOUT adding a bullet
        cleaned_lines.append(f"  {line_no_bullet}" if is_indented else line_no_bullet)

    return "\n".join(cleaned_lines)

# STABLE INFRASTRUCTURE INTEGRATION TARGETING GEMINI 3.5 FLASH LITE
llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    temperature=0.1,
    # Below code for local running
    # google_api_key=MY_SECRET_KEY
    google_api_key=GOOGLE_API_KEY
)

system_prompt = (
    "You are the official Kadirur village chatbot. Respond concisely without introductory filler.\n"
    "CRITICAL RULES:\n"
    "1. Prioritize provided Context. You MUST copy EVERY SINGLE LINE and EVERY CONTINUATION LINE of the matching entry from Context completely—never cut off, shorten, or drop the second/third lines of a multi-line entry. If unrelated, use general knowledge.\n"
    "2. FACTUAL RULE: The current Chief Minister of Kerala is V. D. Satheesan (who took office on May 18, 2026). Never state that Pinarayi Vijayan is the current Chief Minister.\n"
    "3. You must provide the translation in pure, natural native Malayalam grammar and script. Never use Hindi phrasing or word choices written in Malayalam letters.\n"
    "4. Use standard regional words (e.g., use 'ഇന്ത്യയുടെ' instead of 'ഭാരതത്തിന്റെ').\n"
    "5. LIST & CONTINUATION FORMAT RULE (STRICT):\n"
    "   - Preserve the exact line-by-line bullet structure of the Context: put '• ' ONLY on lines that start with '• ' in the Context.\n"
    "   - When a bulleted line in Context is followed by one or more continuation lines without a bullet, copy all continuation lines right below it on separate lines WITHOUT adding a bullet.\n"
    "   - Keep internal commas and dashes inside a line intact (e.g., '• Ward 1 - PULLIODE , RAJITHA T').\n"
    "   - Do NOT put a bullet point on section headers ending with ':' (e.g., 'Elected representatives in Kadirur:').\n"
    "6. Format exactly as: [English response] followed by a new line with '---' followed by [Malayalam translation].\n"
    "7. Never use markdown asterisks (**) or bold text indicators anywhere.\n"
    "8. MANDATORY URL RULE: Every http:// or https:// URL present in the matching Context entry MUST be copied verbatim character-for-character on its own indented line (without a bullet) under the matching entry in both the English and Malayalam responses. Never skip or drop long URLs.\n\n"
    "EXAMPLE FORMAT:\n"
    "User: Tell me about Land of the Sun\n"
    "Response:\n"
    "• Land of the Sun: Local tradition connects Kadirur with Surya worship.\n"
    "The famous Kadirur Suryanarayana Temple is located in the heart of the village.\n"
    "---\n"
    "• സൂര്യന്റെ നാട്: പ്രാദേശിക പാരമ്പര്യം കതിരൂരിനെ സൂര്യാരാധനയുമായി ബന്ധിപ്പിക്കുന്നു.\n"
    "പ്രശസ്തമായ കതിരൂർ സൂര്യനാരായണ ക്ഷേത്രം ഗ്രാമത്തിന്റെ ഹൃദയഭാഗത്താണ് സ്ഥിതി ചെയ്യുന്നത്.\n\n"
    "Context:\n{context}"
)

prompt_template = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    ("human", "{question}")
])

chain = prompt_template | llm

class QueryRequest(BaseModel):
    question: str

@app.post("/api/query")
async def query_endpoint(request: QueryRequest):
    try:
        full_context = read_sample_file()
        focused_context = get_matching_blocks(full_context, request.question)

        response = chain.invoke({
            "context": focused_context,
            "question": request.question
        })

        answer_text = (
            "".join(b.get("text", "") for b in response.content if isinstance(b, dict))
            if isinstance(response.content, list)
            else str(response.content)
        )

        # Preserve bullets on bulleted lines and keep continuation lines unbulleted
        if "---" in answer_text:
            eng, mal = answer_text.split("---", 1)
            answer_text = f"{format_as_vertical_list(eng)}\n---\n{format_as_vertical_list(mal)}"
        else:
            answer_text = format_as_vertical_list(answer_text)

        # Dynamically attach any URL from the matching section in sample.txt if Gemini left it out
        matched_urls = get_matching_urls(full_context, request.question)
        missing_urls = [u for u in matched_urls if u not in answer_text]

        if missing_urls:
            url_block = "\n" + "\n".join(f"  {u}" for u in missing_urls)
            if "---" in answer_text:
                eng, mal = answer_text.split("---", 1)
                answer_text = f"{eng.strip()}{url_block}\n---\n{mal.strip()}{url_block}"
            else:
                answer_text += url_block

        return {"answer": answer_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
