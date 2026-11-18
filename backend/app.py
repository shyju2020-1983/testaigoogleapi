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

# Load your API key exactly like your working code
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. Your exact working model & API key + fast timeout
llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    temperature=0.2,
    google_api_key=GOOGLE_API_KEY,
    timeout=15,
    max_retries=1,
)

CONTEXT_FILE_PATH = "sample.txt"  # <-- Ensure this matches your Kadirur text file name


def read_sample_file() -> str:
    if not os.path.exists(CONTEXT_FILE_PATH):
        print(f"WARNING: {CONTEXT_FILE_PATH} not found!")
        return ""
    with open(CONTEXT_FILE_PATH, "r", encoding="utf-8") as f:
        return f.read()


def get_matching_blocks(full_text: str, question: str) -> str:
    if not full_text:
        return ""
    blocks = re.split(r"\n\s*\n", full_text.strip())
    q_words = set(re.findall(r"\w+", question.lower()))
    stop_words = {
        "what", "where", "who", "why", "when", "how", "is", "are", "was", "were",
        "the", "in", "of", "for", "to", "a", "an", "tell", "me", "about", "that", "this", "reason"
    }
    keywords = q_words - stop_words

    if not keywords:
        return ""

    matched = []
    for block in blocks:
        block_lower = block.lower()
        if any(kw in block_lower for kw in keywords):
            matched.append(block)

    result = "\n\n".join(matched) if matched else ""
    return result[:6000]


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
    lines = text.splitlines()
    cleaned_lines = [line.rstrip() for line in lines if line.strip() != ""]
    return "\n".join(cleaned_lines)


def get_matching_urls(context_text: str, question: str) -> list:
    if not context_text:
        return []
    urls = re.findall(r"https?://[^\s<>\"']+", context_text)
    seen = set()
    unique_urls = []
    for u in urls:
        clean_u = u.rstrip(".,;:!?)]")
        if clean_u not in seen:
            seen.add(clean_u)
            unique_urls.append(clean_u)
    return unique_urls


system_prompt = (
    "I am Kadirur village AI assistant. Respond concisely without introductory filler.\n"
    "CRITICAL RULES:\n"
    "1. PRIORITY SEARCH & FALLBACK RULE (STRICT):\n"
    "   - STEP 1 (CHECK CONTEXT FIRST): Search the provided Context thoroughly. If Context contains a direct answer, answer ONLY using that exact Context information. Do NOT include unrelated sections, NEVER invent outside restaurant, hotel, shop, or place names not written in Context, and copy EVERY SINGLE LINE and continuation line of the matching entries verbatim.\n"
    "   - STEP 2 (GENERAL KNOWLEDGE FALLBACK): If Context is empty or missing the answer, answer accurately using general knowledge while following all formatting and translation rules below.\n"
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

CACHED_CONTEXT = read_sample_file()
ANSWER_CACHE = {}


class QueryRequest(BaseModel):
    question: str
    history: list = []


@app.get("/")
def health_check():
    return {"status": "online", "message": "Kadirur AI Backend is running"}


@app.post("/api/query")
def query_endpoint(request: QueryRequest):
    start_time = time.time()
    try:
        clean_q = request.question.strip()
        if not clean_q:
            raise HTTPException(status_code=400, detail="Question cannot be empty.")

        history_text = "\n".join(
            f"User: {h.get('question', '')}\nAssistant: {h.get('answer', '')}"
            for h in request.history[-3:]
        ) or "None"

        cache_key = f"{clean_q.lower()}|{history_text}"
        if cache_key in ANSWER_CACHE:
            print(f"[CACHE HIT] {time.time() - start_time:.3f}s")
            return {"answer": ANSWER_CACHE[cache_key]}

        full_context = CACHED_CONTEXT or read_sample_file()
        search_query = f"{request.history[-1]['question']} {clean_q}" if request.history else clean_q
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

        matched_urls = get_matching_urls(focused_context, clean_q)
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
