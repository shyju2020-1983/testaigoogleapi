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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLE_FILE_PATH = os.path.join(BASE_DIR, "sample.txt")



def read_sample_file(file_path: str = SAMPLE_FILE_PATH) -> str:
    if not os.path.exists(file_path):
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("Kadirur Village Office handles decentralized land mutation mappings, village development project registers, and local community certificate provisions.")
    with open(file_path, "r", encoding="utf-8") as file:
        return file.read()

def get_matching_blocks(context: str, question: str, max_blocks: int = 3) -> str:
    # Split by '#' / '##' headings so each heading stays attached to all its items underneath
    raw_sections = re.split(r'(?=^#{1,3}\s+)', context.strip(), flags=re.MULTILINE)
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
        'what', 'is', 'the', 'in', 'of', 'about', 'tell', 'me', 'give',
        'list', 'all', 'for', 'and', 'to', 'a', 'an', 'kadirur', 'details', 'are', 'show', 'any'
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
        first_line = lines[0]
        heading_words = set(re.findall(r'\w+', first_line.lower()))
        body_words = set(re.findall(r'\w+', block.lower()))
        score = (len(expanded_keywords & heading_words) * 10) + len(expanded_keywords & body_words)
        if score > 0:
            scored_blocks.append((score, block))

    scored_blocks.sort(key=lambda item: item[0], reverse=True)
    top_blocks = [b for _, b in scored_blocks[:max_blocks]]

    return "\n\n".join(top_blocks) if top_blocks else context[:8000]

def get_matching_urls(context: str, question: str) -> list[str]:
    blocks = re.split(r'\n\s*\n', context.strip())
    q_words = set(re.findall(r'\w+', question.lower()))
    matched_urls = []
    for block in blocks:
        if q_words & set(re.findall(r'\w+', block.lower())):
            urls = re.findall(r'https?://[^\s<>"\']+', block)
            matched_urls.extend(u.rstrip('.,;:!?)') for u in urls)
    return list(dict.fromkeys(matched_urls))

def extract_text(response) -> str:
    if isinstance(response.content, list):
        return "".join(
            b.get("text", "") if isinstance(b, dict) else str(getattr(b, "text", b))
            for b in response.content
        ).strip()
    return str(response.content or "").strip()

def format_as_vertical_list(text: str) -> str:
    cleaned_lines = []

    for raw_line in text.strip().splitlines():
        if not raw_line.strip():
            continue

        is_indented = raw_line.startswith(('  ', '\t'))
        stripped = raw_line.strip()

        if stripped.startswith('#'):
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
    temperature=0.2,
    google_api_key=GOOGLE_API_KEY
)


system_prompt = (
    "You are the official Kadirur village chatbot. Respond concisely without introductory filler.\n"
    "CRITICAL RULES:\n"
    "1. SCOPE & CONTEXT RULE:\n"
    "   - If the user asks about Kadirur village, local wards, local officials, or local places/services, answer ONLY using the matching section from the provided Context. Do NOT include unrelated sections from Context, and NEVER invent or add any outside restaurant, hotel, shop, or place names not written in Context. Copy EVERY SINGLE LINE and continuation line of the matching entries verbatim.\n"
    "   - If the user asks a general knowledge question (such as the Prime Minister of India, capital cities, or general facts) that is NOT covered in the Context, answer accurately using your general knowledge while still following all formatting and translation rules below.\n"
    "2. FACTUAL RULE: The current Chief Minister of Kerala is V. D. Satheesan (who took office on May 18, 2026). Never state that Pinarayi Vijayan is the current Chief Minister.\n"
    "3. You must provide the translation in pure, natural native Malayalam grammar and script. Never use Hindi phrasing or word choices written in Malayalam letters.\n"
    "4. Use standard regional words (e.g., use 'ഇന്ത്യയുടെ' instead of 'ഭാരതത്തിന്റെ').\n"
    "5. LIST & CONTINUATION FORMAT RULE (STRICT):\n"
    "   - Preserve the exact line-by-line bullet structure: put '• ' ONLY on lines that start with '• ' in the Context.\n"
    "   - Copy all continuation lines below a bulleted line (such as ratings, prices, or road addresses) on separate lines WITHOUT adding a bullet.\n"
    "   - Keep internal commas and dashes intact (e.g., '• Ward 1 - PULLIODE , RAJITHA T').\n"
    "   - Do NOT put a bullet point on section headers ending with ':'.\n"
    "6. Format exactly as: [English response] followed by a new line with '---' followed by [Malayalam translation].\n"
    "7. Never use markdown asterisks (**) or bold text indicators anywhere.\n"
    "8. Copy every http:// or https:// URL verbatim on its own indented line without a bullet.\n\n"
    "Context:\n{context}"
)

prompt_template = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    ("human", "{question}")
])

chain = prompt_template | llm

mal_prompt = ChatPromptTemplate.from_messages([
    ("system", "Translate the given English text into pure, natural native Malayalam script. Keep exact line breaks, bullet points ('• '), and URLs unchanged. Do not use markdown asterisks (**). Output ONLY the Malayalam translation."),
    ("human", "{text}")
])

mal_chain = mal_prompt | llm

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

        answer_text = extract_text(response)

        # Fallback if Gemini returns empty on a long section (such as History of Kadirur)
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

        matched_urls = get_matching_urls(focused_context, request.question)
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