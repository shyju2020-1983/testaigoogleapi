import os
import sys
import urllib.request
import urllib.parse
import json
import re
from fastapi import FastAPI
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
    raise ValueError("CRITICAL ERROR: GOOGLE_API_KEY environment variable is missing!")

def read_sample_file(file_path: str = "sample.txt") -> str:
    if not os.path.exists(file_path):
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("Kadirur Village Office handles decentralized land mutation mappings, village development project registers, and local community certificate provisions.")
    with open(file_path, "r", encoding="utf-8") as file:
        return file.read()

# Native raw Python internet lookup solution to avoid LangChain tool dependencies
def get_live_search_data(query_string: str) -> str:
    try:
        # Using a reliable public search query pipeline format
        encoded_query = urllib.parse.quote_plus(query_string)
        url = f"https://duckduckgo.com{encoded_query}"
        
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        
        with urllib.request.urlopen(req, timeout=5) as response:
            html = response.read().decode('utf-8')
            
        # Clean the HTML boilerplate tags to extract raw factual description strings
        snippets = re.findall(r'<a class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)
        clean_snippets = []
        for snip in snippets[:3]:
            # Strip remaining inner HTML formatting marks
            clean_text = re.sub(r'<[^>]+>', '', snip).strip()
            clean_snippets.append(clean_text)
            
        return "\n".join(clean_snippets)
    except Exception as search_error:
        print(f"⚠️ Live web search lookup skipped: {search_error}")
        return ""

# STABLE INFRASTRUCTURE INTEGRATION TARGETING GEMINI 3.5 FLASH LITE
llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    temperature=0.1,
    google_api_key=GOOGLE_API_KEY,
    max_output_tokens=1024,
    extra_body={
        "thinking_config": {
            "thinking_level": "MINIMAL"  # Disables deep reasoning lag for pure speed
        } 
    }
)

# DYNAMIC PROMPT LAYER GROUNDED BY LIVE SEARCH DATA INJECTS
system_prompt = (
    "You are the official Kadirur village chatbot. Respond concisely without introductory filler.\n"
    "CRITICAL RULES:\n"
    "1. Prioritize provided Context. If unrelated, rely strictly on the verified Live Web Search Data below.\n"
    "2. Ensure all regional political statistics and administrative office-holders reflect current 2026 statuses (e.g., V. D. Satheesan is the CM of Kerala since May 2026; D. K. Shivakumar is the CM of Karnataka since June 2026).\n"
    "3. You must provide the translation in pure, natural native Malayalam grammar and script. Never use Hindi phrasing.\n"
    "4. Use standard regional words (e.g., use 'ഇന്ത്യയുടെ' instead of 'ഭാരതത്തിന്റെ').\n"
    "5. Format exactly as: [English text] followed by a new line with '---' followed by [Malayalam translation].\n"
    "6. Never use markdown asterisks (**) or bold text indicators anywhere.\n\n"
    "Live Web Search Data:\n{search_data}\n\n"
    "Context:\n{context}"
)

prompt_template = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    ("human", "{input}"),
])

class QueryRequest(BaseModel):
    question: str

@app.get("/")
async def root():
    return {"status": "online", "message": "Kadirur Chatbot direct API interface is active"}

@app.post("/api/query")
async def query_file(request: QueryRequest):
    print(f"📥 Received direct incoming query: {request.question}")
    try:
        context_data = read_sample_file("sample.txt")
        
        # ai made change: Run web scan internally using native libraries for real-time keywords
        search_data = ""
        keywords = ["who is", "chief minister", "cm", "latest", "current", "president", "prime minister"]
        if any(kw in request.question.lower() for kw in keywords):
            print("🌐 Fetching live facts directly from the web...")
            search_data = get_live_search_data(request.question)
            
        messages = prompt_template.format_messages(
            context=context_data,
            search_data=search_data,
            input=request.question
        )
        
        response = llm.invoke(messages)
        print("📤 Google Gemini replied successfully!")
        
        plain_text_answer = response.content
        
        # ai made change: Unpack array string formats safely
        if isinstance(plain_text_answer, list) and len(plain_text_answer) > 0:
            extracted_chunks = []
            for item in plain_text_answer:
                if isinstance(item, dict) and "text" in item:
                    extracted_chunks.append(str(item["text"]))
                else:
                    extracted_chunks.append(str(item))
            plain_text_answer = "".join(extracted_chunks)
        else:
            plain_text_answer = str(plain_text_answer)
            
        # ai made change: Removes outer formatting bracket wraps completely
        plain_text_answer = plain_text_answer.strip('[]"\'')
        
        return {"answer": plain_text_answer}
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ BACKEND EXCEPTION: {error_msg}", file=sys.stderr)
        return {"answer": f"Backend Error: {error_msg}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
