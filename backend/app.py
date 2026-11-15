import os
import re
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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLE_FILE_PATH = os.path.join(BASE_DIR, "sample.txt")

def read_sample_file(file_path: str = SAMPLE_FILE_PATH) -> str:
    if not os.path.exists(file_path):
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("Kadirur Village Office handles decentralized land mutation mappings, village development project registers, and local community certificate provisions.")
    with open(file_path, "r", encoding="utf-8") as file:
        return file.read()

def find_exact_section(context: str, question: str) -> str:
    """Finds the best matching '##' section from sample.txt with 100% exact lines."""
    if re.search(r'^##\s+', context, flags=re.MULTILINE):
        blocks = [b.strip() for b in re.split(r'(?=^##\s+)', context.strip(), flags=re.MULTILINE) if b.strip()]
    else:
        blocks = [b.strip() for b in re.split(r'\n\s*\n', context.strip()) if b.strip()]

    q_words = set(re.findall(r'\w+', question.lower()))
    stop_words = {
        'what', 'is', 'the', 'in', 'of', 'about', 'tell', 'me', 'give',
        'list', 'all', 'for', 'and', 'to', 'a', 'an', 'kadirur', 'details', 'are', 'show'
    }
    keywords = q_words - stop_words
    if not keywords:
        return ""

    # Expand plurals and common spelling variants (e.g. Restaurents / Restaurants / Hotels)
    expanded_keywords = set(keywords)
    for w in keywords:
        if w.endswith('s') and len(w) > 3:
            expanded_keywords.add(w[:-1])
        else:
            expanded_keywords.add(w + 's')
        if any(k in w for k in ('restaurant', 'restaurent', 'hotel', 'food', 'eat')):
            expanded_keywords.update({'restaurant', 'restaurants', 'restaurent', 'restaurents', 'hotel', 'hotels'})

    best_score = 0
    best_block = ""
    for block in blocks:
        lines = block.splitlines()
        heading_words = set(re.findall(r'\w+', lines[0].lower())) if lines else set()
        body_words = set(re.findall(r'\w+', block.lower()))

        # Weight heading matches higher so "## Restaurents and hotels in Kadirur" always wins
        score = (len(expanded_keywords & heading_words) * 5) + len(expanded_keywords & body_words)
        if score > best_score:
            best_score = score
            best_block = block

    return best_block if best_score > 0 else ""

def extract_text_from_response(response) -> str:
    if isinstance(response.content, list):
        parts = []
        for b in response.content:
            if isinstance(b, dict) and "text" in b:
                parts.append(b["text"])
            elif hasattr(b, "text"):
                parts.append(str(b.text))
            elif isinstance(b, str):
                parts.append(b)
        return "".join(parts).strip()
    return str(response.content or "").strip()

def format_as_vertical_list(text: str) -> str:
    cleaned_lines = []

    for raw_line in text.strip().splitlines():
        if not raw_line.strip():
            continue

        is_indented = raw_line.startswith(('  ', '\t'))
        stripped = raw_line.strip()

        # Convert "## Heading" into clean "Heading:" without bullet
        if stripped.startswith('##'):
            cleaned_lines.append(stripped.lstrip('#').strip().rstrip(':') + ":")
            continue

        had_bullet = bool(re.match(r'^[-*•]\s+', stripped))
        line_no_bullet = re.sub(r'^[-*•]+\s*', '', stripped)

        if line_no_bullet.endswith(':'):
            cleaned_lines.append(line_no_bullet)
            continue

        if line_no_bullet.startswith(('http://', 'https://')) or 'http://' in line_no_bullet or 'https://' in line_no_bullet:
            cleaned_lines.append(f"  {line_no_bullet}")
            continue

        if had_bullet:
            cleaned_lines.append(f"• {line_no_bullet}")
            continue

        cleaned_lines.append(f"  {line_no_bullet}" if is_indented else line_no_bullet)

    return "\n".join(cleaned_lines)

llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    temperature=0.1,
    google_api_key=GOOGLE_API_KEY
)

# Dedicated Malayalam translator for exact sample.txt sections
mal_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "Translate the given English text into pure, natural native Malayalam grammar and script. "
        "Never use Hindi phrasing or word choices written in Malayalam letters. "
        "Use standard regional words (e.g., 'ഇന്ത്യയുടെ' instead of 'ഭാരതത്തിന്റെ'). "
        "Preserve the EXACT line breaks, bullet points ('• '), indentation, and http/https URLs verbatim. "
        "Never add new items, never remove lines, and never use markdown asterisks (**). "
        "Output ONLY the Malayalam translation."
    ),
    ("human", "{text}")
])
mal_chain = mal_prompt | llm

# General knowledge chain ONLY for questions not found in sample.txt (e.g., CM/PM)
general_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "You are the official Kadirur village chatbot. Respond concisely without introductory filler.\n"
        "1. If the user asks about a local shop, hotel, restaurant, tailor, office, ward, or place in Kadirur that is not in the file, reply strictly: 'No details found in the Kadirur directory for this query.' followed by '---' and its Malayalam translation. NEVER invent local place names.\n"
        "2. FACTUAL RULE: The current Chief Minister of Kerala is V. D. Satheesan (who took office on May 18, 2026). Never state that Pinarayi Vijayan is the current Chief Minister.\n"
        "3. Format as: [English bulleted list] followed by '\\n---\\n' followed by [Malayalam translation]. Never use ** bold markers."
    ),
    ("human", "{question}")
])
general_chain = general_prompt | llm

class QueryRequest(BaseModel):
    question: str

@app.post("/api/query")
async def query_endpoint(request: QueryRequest):
    try:
        full_context = read_sample_file()
        matched_section = find_exact_section(full_context, request.question)

        # CASE 1: Matched a section in sample.txt -> Output exact file content + Malayalam translation
        if matched_section:
            eng_formatted = format_as_vertical_list(matched_section)
            mal_raw = ""
            try:
                mal_resp = mal_chain.invoke({"text": eng_formatted})
                mal_raw = extract_text_from_response(mal_resp)
            except Exception as e:
                print("Malayalam translation error:", repr(e))

            if mal_raw:
                answer_text = f"{eng_formatted}\n---\n{format_as_vertical_list(mal_raw)}"
            else:
                answer_text = eng_formatted

            return {"answer": answer_text}

        # CASE 2: General question not in sample.txt (e.g., Prime Minister / Chief Minister)
        gen_resp = general_chain.invoke({"question": request.question})
        answer_text = extract_text_from_response(gen_resp)

        if "---" in answer_text:
            eng, mal = answer_text.split("---", 1)
            answer_text = f"{format_as_vertical_list(eng)}\n---\n{format_as_vertical_list(mal)}"
        else:
            answer_text = format_as_vertical_list(answer_text)

        return {"answer": answer_text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
