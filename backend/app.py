import os
import re
import time
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    temperature=0.2,
    google_api_key=GOOGLE_API_KEY,
)

CONTEXT_FILE_PATH = "sample.txt"


def read_sample_file() -> str:
    if not os.path.exists(CONTEXT_FILE_PATH):
        print(f"WARNING: {CONTEXT_FILE_PATH} not found!")
        return ""
    with open(CONTEXT_FILE_PATH, "r", encoding="utf-8") as f:
        return f.read()


def extract_all_headings(full_text: str) -> list[str]:
    if not full_text:
        return []

    headings = []
    raw_sections = re.split(r'(?=^#{1,3}\s+)', full_text.strip(), flags=re.MULTILINE)
    blocks = []
    for sec in raw_sections:
        sec = sec.strip()
        if not sec:
            continue
        if not sec.startswith('#') and '\n\n' in sec:
            blocks.extend(b.strip() for b in re.split(r'\n\s*\n', sec) if b.strip())
        else:
            blocks.append(sec)

    for block in blocks:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue

        first_line = lines[0]

        # Skip lines that are clearly list bullets or URLs
        if first_line.startswith(('•', '-', '*', 'http://', 'https://')):
            continue

        # Clean markdown '#' and trailing ':'
        clean_heading = first_line.lstrip('#').strip().rstrip(':').strip()

        # If heading has bilingual '/' (e.g., "History of Kadirur / കതിരൂരിന്റെ ചരിത്രം"), keep clean title
        if '/' in clean_heading:
            clean_heading = clean_heading.split('/', 1)[0].strip()

        if clean_heading and len(clean_heading) <= 100:
            headings.append(clean_heading)

    # Deduplicate while preserving original order
    return list(dict.fromkeys(headings))


def get_matching_blocks(full_text: str, question: str) -> str:
    if not full_text:
        return ""

    raw_sections = re.split(r'(?=^#{1,3}\s+)', full_text.strip(), flags=re.MULTILINE)
    blocks = []
    for sec in raw_sections:
        sec = sec.strip()
        if not sec:
            continue
        if not sec.startswith('#') and '\n\n' in sec:
            blocks.extend(b.strip() for b in re.split(r'\n\s*\n', sec) if b.strip())
        else:
            blocks.append(sec)

    q_words = set(re.findall(r'\w+', question.lower()))
    stop_words = {
        "what", "where", "who", "why", "when", "how", "is", "are", "was", "were",
        "the", "in", "of", "for", "to", "a", "an", "tell", "me", "about", "that", "this", "reason",
        "give", "list", "all", "and", "kadirur", "details", "show", "any"
    }
    keywords = q_words - stop_words or q_words

    expanded_keywords = set(keywords)
    for w in keywords:
        if w.endswith('s') and len(w) > 3:
            expanded_keywords.add(w[:-1])
        else:
            expanded_keywords.add(w + 's')
        if any(k in w for k in ('restaurant', 'restaurent', 'hotel')):
            expanded_keywords.update({'restaurant', 'restaurants', 'restaurent', 'restaurents', 'hotel', 'hotels'})

    scored_blocks = []
    for block in blocks:
        lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        first_line, *_ = lines
        heading_words = set(re.findall(r'\w+', first_line.lower()))
        body_words = set(re.findall(r'\w+', block.lower()))
        score = (len(expanded_keywords & heading_words) * 10) + len(expanded_keywords & body_words)
        if score > 0:
            scored_blocks.append((score, block))

    scored_blocks.sort(reverse=True)
    top_blocks = [b for _, b in scored_blocks[:3]]

    return "\n\n".join(top_blocks) if top_blocks else ""


def extract_text(response) -> str:
    if response is None:
        return ""
    content = getattr(response, "content", response)
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and "text" in item:
                parts.append(item["text"])
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts).strip()
    return str(content).strip()


def format_as_vertical_list(text: str) -> str:
    if not text:
        return ""
    cleaned_lines = []
    for raw_line in text.strip().splitlines():
        if not raw_line.strip():
            continue
        is_indented = raw_line.startswith(('  ', '\t'))
        stripped = raw_line.strip()

        if stripped.startswith('#'):
            clean_heading = stripped.lstrip('#').strip().rstrip(':')
            if '/' in clean_heading:
                first_part, *_ = clean_heading.split('/', 1)
                clean_heading = first_part.strip()
            cleaned_lines.append(clean_heading + ":")
            continue

        had_bullet = bool(re.match(r'^[-*•]\s+', stripped))
        line_no_bullet = re.sub(r'^[-*•]+\s*', '', stripped)

        if line_no_bullet.endswith(':'):
            clean_label = line_no_bullet.rstrip(':')
            if '/' in clean_label:
                first_part, *_ = clean_label.split('/', 1)
                clean_label = first_part.strip()
            cleaned_lines.append(clean_label + ":")
            continue

        if line_no_bullet.startswith(('http://', 'https://')) or 'http://' in line_no_bullet or 'https://' in line_no_bullet:
            cleaned_lines.append(f"  {line_no_bullet}")
            continue

        if had_bullet:
            cleaned_lines.append(f"• {line_no_bullet}")
            continue

        cleaned_lines.append(f"  {line_no_bullet}" if is_indented else line_no_bullet)

    return "\n".join(cleaned_lines)


def get_matching_urls(context_text: str, question: str) -> list:
    if not context_text:
        return []
    blocks = re.split(r'\n\s*\n', context_text.strip())
    q_words = set(re.findall(r'\w+', question.lower()))
    matched_urls = []
    for block in blocks:
        if q_words & set(re.findall(r'\w+', block.lower())):
            urls = re.findall(r'https?://[^\s<>"\']+', block)
            matched_urls.extend(u.rstrip('.,;:!?)') for u in urls)
    return list(dict.fromkeys(matched_urls))


system_prompt = (
    "I am Kadirur village AI assistant. Respond concisely without introductory filler.\n"
    "CRITICAL RULES:\n"
    "1. PRIORITY SEARCH & FALLBACK RULE (STRICT):\n"
    "   - STEP 1 (CHECK CONTEXT FIRST): Search the provided Context thoroughly. If Context contains a direct answer, answer ONLY using that exact Context information. Do NOT include unrelated sections, NEVER invent outside restaurant, hotel, shop, or place names not written in Context, and copy EVERY SINGLE LINE and continuation line of the matching entries verbatim.\n"
    "   - STEP 2 (GENERAL KNOWLEDGE FALLBACK): If Context is empty or missing the answer, answer accurately using general knowledge while following all formatting and translation rules below. You MUST add 'Note: This information is from general external knowledge, not from Kadirur local records •' on a new line BEFORE the '---' separator (inside the English section), and add ONLY its Malayalam translation 'കുറിപ്പ്: ഈ വിവരം കതിരൂർ പ്രാദേശിക രേഖകളിൽ നിന്നുള്ളതല്ല, പൊതുവായ ബാഹ്യ അറിവിൽ നിന്നുള്ളതാണ് •' on a new line AFTER the '---' separator (inside the Malayalam section).\n"
    "2. FACTUAL RULE: The current Chief Minister of Kerala is V. D. Satheesan (who took office on May 18, 2026). Never state that Pinarayi Vijayan is the current Chief Minister.\n"
    "3. Provide the translation in pure, natural native Malayalam grammar and script. Never use Hindi phrasing or word choices written in Malayalam letters.\n"
    "4. Use standard regional words (e.g., use 'ഇന്ത്യയുടെ' instead of 'ഭാരതത്തിന്റെ').\n"
    "5. LIST & CONTINUATION FORMAT RULE (STRICT):\n"
    "   - Preserve exact line-by-line bullet structure: put '• ' ONLY on lines that start with '• ' in Context.\n"
    "   - Copy all continuation lines below a bulleted line (ratings, prices, addresses) on separate lines WITHOUT adding a bullet.\n"
    "   - Keep internal commas and dashes intact (e.g., '• Ward 1 - PULLIODE , RAJITHA T').\n"
    "   - Do NOT put a bullet point on section headers ending with ':'.\n"
    "6. Format exactly as: [English response] followed by a new line with '---' followed by [Malayalam translation].\n"
    "7. Never use markdown asterisks (**) or bold text indicators anywhere.\n"
    "8. Copy every http:// or https:// URL verbatim on its own indented line without a bullet.\n\n"
    "Context:\n{context}"
)

prompt_template = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    ("human", "Previous conversation:\n{history}\n\nCurrent question: {question}")
])

chain = prompt_template | llm

mal_prompt = ChatPromptTemplate.from_messages([
    (
        "system",
        "Translate the given English text into pure, natural native Malayalam script. "
        "Keep exact line breaks, bullet points ('• '), and URLs unchanged. "
        "Do not use markdown asterisks (**). Output ONLY the Malayalam translation."
    ),
    ("human", "{text}")
])

mal_chain = mal_prompt | llm

# Used to store details in RAM
CACHED_CONTEXT = read_sample_file()
CACHED_HEADINGS = extract_all_headings(CACHED_CONTEXT)
ANSWER_CACHE = {}


class QueryRequest(BaseModel):
    question: str
    history: list = []

@app.get("/")
def health_check():
    return {"status": "online", "message": "Kadirur AI Backend is running"}


@app.get("/api/headings")
def get_headings():
    """Returns all cached headings from sample.txt for React autofill suggestions."""
    full_context = CACHED_CONTEXT or read_sample_file()
    headings = CACHED_HEADINGS or extract_all_headings(full_context)
    return {"headings": headings}


@app.post("/api/query")
def query_endpoint(request: QueryRequest):
    start_time = time.time()
    try:
        clean_q = request.question.strip()
        if not clean_q:
            raise HTTPException(status_code=400, detail="Question cannot be empty.")

        recent_items = request.history[-3:]
        history_text = "\n".join(
            f"User: {h.get('question', '')}\nAssistant: {h.get('answer', '')}"
            for h in recent_items
        ) or "None"

        cache_key = f"{clean_q.lower()}|{history_text}"
        if cache_key in ANSWER_CACHE:
            print(f"[CACHE HIT] {time.time() - start_time:.3f}s")
            return {"answer": ANSWER_CACHE[cache_key]}

        full_context = CACHED_CONTEXT or read_sample_file()
        last_q = recent_items[-1].get("question", "") if recent_items else ""
        search_query = f"{last_q} {clean_q}".strip()
        focused_context = get_matching_blocks(full_context, search_query)

        response = chain.invoke({
            "context": focused_context or "No matching local Kadirur records found.",
            "history": history_text,
            "question": clean_q
        })

        answer_text = extract_text(response)

        if not answer_text and focused_context:
            eng_formatted = format_as_vertical_list(focused_context)
            mal_resp = mal_chain.invoke({"text": eng_formatted})
            mal_raw = extract_text(mal_resp)
            if mal_raw:
                answer_text = f"{eng_formatted}\n---\n{format_as_vertical_list(mal_raw)}"
            else:
                answer_text = eng_formatted
        elif answer_text:
            if "---" in answer_text:
                eng, mal = answer_text.split("---", 1)
                answer_text = f"{format_as_vertical_list(eng)}\n---\n{format_as_vertical_list(mal)}"
            else:
                eng_formatted = format_as_vertical_list(answer_text)
                mal_resp = mal_chain.invoke({"text": eng_formatted})
                mal_raw = extract_text(mal_resp)
                answer_text = f"{eng_formatted}\n---\n{format_as_vertical_list(mal_raw)}" if mal_raw else eng_formatted

        matched_urls = get_matching_urls(focused_context, search_query)
        missing_urls = [u for u in matched_urls if u not in answer_text]

        if missing_urls:
            url_block = "\n" + "\n".join(f"  {u}" for u in missing_urls)
            if "---" in answer_text:
                eng, mal = answer_text.split("---", 1)
                answer_text = f"{eng.strip()}{url_block}\n---\n{mal.strip()}{url_block}"
            else:
                answer_text += url_block

        if answer_text:
            if len(ANSWER_CACHE) >= 200:
                ANSWER_CACHE.pop(next(iter(ANSWER_CACHE)))
            ANSWER_CACHE[cache_key] = answer_text

        print(f"[GEMINI DONE] {time.time() - start_time:.2f}s")
        return {"answer": answer_text}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] {time.time() - start_time:.2f}s -> {e}")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
