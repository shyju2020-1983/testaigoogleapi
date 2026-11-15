import os
import re
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai
from google.genai import types
from dotenv import load_dotenv

app = FastAPI()

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

client = genai.Client(api_key=GOOGLE_API_KEY)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAMPLE_FILE_PATH = os.path.join(BASE_DIR, "sample.txt")

def read_sample_file(file_path: str = SAMPLE_FILE_PATH) -> str:
    if not os.path.exists(file_path):
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("Kadirur Village Office handles decentralized land mutation mappings, village development project registers, and local community certificate provisions.")
    with open(file_path, "r", encoding="utf-8") as file:
        return file.read()

def get_matching_blocks(context: str, question: str, max_blocks: int = 5) -> str:
    blocks = [b.strip() for b in re.split(r'\n\s*\n', context.strip()) if b.strip()]
    q_words = set(re.findall(r'\w+', question.lower()))
    stop_words = {
        'what', 'is', 'the', 'in', 'of', 'about', 'tell', 'me', 'give',
        'list', 'all', 'for', 'and', 'to', 'a', 'an', 'kadirur', 'details'
    }
    keywords = q_words - stop_words or q_words

    scored_blocks = []
    for block in blocks:
        b_words = set(re.findall(r'\w+', block.lower()))
        score = len(keywords & b_words)
        if score > 0:
            scored_blocks.append((score, block))

    scored_blocks.sort(key=lambda x: x[0], reverse=True)
    top_blocks = [b for _, b in scored_blocks[:max_blocks]]

    return "\n\n".join(top_blocks) if top_blocks else ""

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

        # Skip markdown '##' section titles from sample.txt or clean them
        if stripped.startswith('##'):
            cleaned_lines.append(stripped.lstrip('#').strip() + ":")
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

SYSTEM_PROMPT = (
    "You are the official Kadirur village chatbot. Respond concisely without introductory filler.\n"
    "CRITICAL RULES:\n"
    "1. Prioritize provided Context. Copy EVERY SINGLE LINE and EVERY CONTINUATION LINE of the matching entry from Context completely without cutting off or summarizing. If unrelated, use general knowledge.\n"
    "2. FACTUAL RULE: The current Chief Minister of Kerala is V. D. Satheesan (who took office on May 18, 2026). Never state that Pinarayi Vijayan is the current Chief Minister.\n"
    "3. You must provide the translation in pure, natural native Malayalam grammar and script. Never use Hindi phrasing or word choices written in Malayalam letters.\n"
    "4. Use standard regional words (e.g., use 'ഇന്ത്യയുടെ' instead of 'ഭാരതത്തിന്റെ').\n"
    "5. LIST & CONTINUATION FORMAT RULE (STRICT):\n"
    "   - Preserve the exact line-by-line bullet structure: put '• ' ONLY on lines that start with '• ' in the Context.\n"
    "   - Copy all continuation lines below a bulleted line on separate lines WITHOUT adding a bullet.\n"
    "   - Keep internal commas and dashes intact.\n"
    "   - Do NOT put a bullet point on section headers ending with ':'.\n"
    "6. Format exactly as: [English response] followed by a new line with '---' followed by [Malayalam translation].\n"
    "7. Never use markdown asterisks (**) or bold text indicators anywhere.\n"
    "8. Copy every http:// or https:// URL verbatim on its own indented line without a bullet."
)

def translate_to_malayalam_only(english_text: str) -> str:
    """Dedicated fallback translator when the main bilingual call returns empty on long sections."""
    resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=(
            "Translate the following English text into pure, natural native Malayalam script. "
            "Keep the exact line breaks, bullet points ('• '), and URLs unchanged. "
            "Do not use markdown asterisks (**). Output ONLY the Malayalam translation:\n\n"
            f"{english_text}"
        ),
        config=types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=8192,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
            safety_settings=[
                types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
                types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
                types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
            ],
        ),
    )
    return (resp.text or "").strip()

class QueryRequest(BaseModel):
    question: str

@app.post("/api/query")
async def query_endpoint(request: QueryRequest):
    try:
        full_context = read_sample_file()
        focused_context = get_matching_blocks(full_context, request.question)
        context_for_llm = focused_context if focused_context else full_context[:6000]

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                f"Context:\n{context_for_llm}",
                f"User Question: {request.question}"
            ],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.1,
                max_output_tokens=8192,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
                safety_settings=[
                    types.SafetySetting(category="HARM_CATEGORY_HARASSMENT", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_HATE_SPEECH", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_SEXUALLY_EXPLICIT", threshold="BLOCK_NONE"),
                    types.SafetySetting(category="HARM_CATEGORY_DANGEROUS_CONTENT", threshold="BLOCK_NONE"),
                ],
            ),
        )

        answer_text = (response.text or "").strip()

        # If main bilingual call returned empty on a long section (like History of Kadirur),
        # format the exact English text from sample.txt AND translate it cleanly into Malayalam
        if not answer_text and focused_context:
            eng_formatted = format_as_vertical_list(focused_context)
            mal_raw = translate_to_malayalam_only(eng_formatted)
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
                mal_raw = translate_to_malayalam_only(eng_formatted)
                answer_text = f"{eng_formatted}\n---\n{format_as_vertical_list(mal_raw)}" if mal_raw else eng_formatted

        matched_urls = get_matching_urls(context_for_llm, request.question)
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
        print("API Query Error:", repr(e))
        return {"answer": f"Backend Error: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
