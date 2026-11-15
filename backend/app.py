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
    split_pattern = re.compile(r',\s*(?:and|&)\s+|,\s*|\s+and\s+(?=[A-Z0-9\u0D00-\u0D7F])')

    for raw_line in text.strip().splitlines():
        if not raw_line.strip():
            continue

        is_sub_detail = raw_line.startswith(('  ', '\t'))
        line = raw_line.strip()

        # 1. Category headers ending with ':' (e.g., "Tailors in Kadirur:") -> NO bullet point
        if line.endswith(':') and not is_sub_detail:
            line = re.sub(r'^[-*•\d.)]+\s*', '', line)
            cleaned_lines.append(line)
            continue

        # 2. URLs -> NO bullet point, indented under the entry
        if line.startswith(('http://', 'https://')) or 'http://' in line or 'https://' in line:
            line = re.sub(r'^[-*•]+\s*', '', line)
            cleaned_lines.append(f"  {line}")
            continue

        # 3. Indented sub-details (e.g., "  Location: Kadirur") -> NO bullet point
        if is_sub_detail:
            line = re.sub(r'^[-*•]+\s*', '', line)
            cleaned_lines.append(f"  {line}")
            continue

        # 4. Field labels (e.g., "Location: ...", "Phone: ...") -> NO bullet point
        if re.match(r'^(Location|Address|Phone|Contact|Timing|Timings|Directions|Link|സ്ഥലം|വിലാസം|ഫോൺ|സമയം)\s*:', line, re.IGNORECASE):
            line = re.sub(r'^[-*•]+\s*', '', line)
            cleaned_lines.append(f"  {line}")
            continue

        # 5. Actual entry/shop/place names -> ADD bullet point ('• ')
        line = re.sub(r'^[-*•\d.)]+\s*', '', line)
        parts = [p.strip() for p in split_pattern.split(line) if p.strip()]
        for part in parts:
            part = re.sub(r'^and\s+', '', part, flags=re.IGNORECASE).rstrip('.').strip()
            if part:
                cleaned_lines.append(f"• {part}")

    return "\n".join(cleaned_lines)

# STABLE INFRASTRUCTURE INTEGRATION TARGETING GEMINI 3.5 FLASH LITE
llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    temperature=0.3,
    # Below code for local running
    # google_api_key=MY_SECRET_KEY
    google_api_key=GOOGLE_API_KEY
)

system_prompt = (
    "You are the official Kadirur village chatbot. Respond concisely without introductory filler.\n"
    "CRITICAL RULES:\n"
    "1. Prioritize provided Context. Copy all fields from the matching entry in Context, including any URLs. If unrelated, use general knowledge.\n"
    "2. FACTUAL RULE: The current Chief Minister of Kerala is V. D. Satheesan (who took office on May 18, 2026). Never state that Pinarayi Vijayan is the current Chief Minister.\n"
    "3. You must provide the translation in pure, natural native Malayalam grammar and script. Never use Hindi phrasing or word choices written in Malayalam letters.\n"
    "4. Use standard regional words (e.g., use 'ഇന്ത്യയുടെ' instead of 'ഭാരതത്തിന്റെ').\n"
    "5. LIST & HEADING FORMAT RULE (STRICT): If you include a category title ending with a colon (e.g., 'Tailors in Kadirur:'), write it WITHOUT a bullet point. Put a bullet point ('• ') ONLY on each individual shop, place, person, or entry name from the Context. Any sub-details belonging to that entry (such as location, phone number, timings, or URLs) MUST be on separate lines indented with 2 spaces ('  ') WITHOUT a bullet point. NEVER write comma-separated lists or paragraphs.\n"
    "6. Format exactly as: [English response] followed by a new line with '---' followed by [Malayalam translation].\n"
    "7. Never use markdown asterisks (**) or bold text indicators anywhere.\n"
    "8. MANDATORY URL RULE: Every http:// or https:// URL present in the matching Context entry MUST be copied verbatim character-for-character on its own indented line (without a bullet) under the matching entry in both the English and Malayalam responses. Never skip or drop long URLs.\n\n"
    "EXAMPLE FORMAT:\n"
    "User: Tell me about tailors in Kadirur\n"
    "Response:\n"
    "Tailors in Kadirur:\n"
    "• H2O Kadirur (Her Only)\n"
    "  Location: Kadirur\n"
    "  https://google.com\n"
    "• Classic Tailors\n"
    "  Location: 4th Mile, Kadirur\n"
    "---\n"
    "കതിരൂരിലെ തയ്യൽക്കടകൾ:\n"
    "• H2O കതിരൂർ (ഹെർ ഒൺലി)\n"
    "  സ്ഥലം: കതിരൂർ\n"
    "  https://google.com\n"
    "• ക്ലാസിക് ടെയ്‌ലേഴ്സ്\n"
    "  സ്ഥലം: നാലാം മൈൽ, കതിരൂർ\n\n"
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
        context_data = read_sample_file()

        response = chain.invoke({
            "context": context_data,
            "question": request.question
        })

        answer_text = (
            "".join(b.get("text", "") for b in response.content if isinstance(b, dict))
            if isinstance(response.content, list)
            else str(response.content)
        )

        # Format category headers without bullets, entries with bullets, and sub-details indented
        if "---" in answer_text:
            eng, mal = answer_text.split("---", 1)
            answer_text = f"{format_as_vertical_list(eng)}\n---\n{format_as_vertical_list(mal)}"
        else:
            answer_text = format_as_vertical_list(answer_text)

        # Dynamically attach any URL from the matching section in sample.txt if Gemini left it out
        matched_urls = get_matching_urls(context_data, request.question)
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
