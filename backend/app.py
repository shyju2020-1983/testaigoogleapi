import os
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

# STABLE INFRASTRUCTURE INTEGRATION TARGETING GEMINI 3.5 FLASH LITE
llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    temperature=0.1,  # 👈 Dropped to 0.1 for high accuracy and factual grounding
    google_api_key=GOOGLE_API_KEY,
    max_output_tokens=1024,  # 👈 Limits excessive output generation to save time
    extra_body={
        "thinking_config": {
            "thinking_level": "MINIMAL"  # 👈 Disables deep reasoning lag for pure speed
        }
    }
)

# Streamlined and structured system prompt to force direct answers without filler
system_prompt = (
    "You are the official Kadirur Village Chatbot assistant.\n"
    "CRITICAL RULES FOR ACCURACY & SPEED:\n"
    "1. Base answers on the Context below if relevant. Otherwise, use general knowledge.\n"
    "2. Be concise. Provide direct facts immediately. Skip all introductory filler and polite conversational preambles.\n"
    "3. Format exactly as: [English text] followed by a new line with '---' followed by [Malayalam translation].\n"
    "4. NEVER use markdown asterisks (**) or bold text indicators anywhere.\n\n"
    "Context:\n{context}"
)
Use code with caution.

What Changed & Why:

• Lowered Temperature (0.3 to 0.1): Dropping the temperature makes the model deterministic. It prevents it from wandering into creative wording, which boosts both structural accuracy and generation speed.
• thinking_level: "MINIMAL": This bypasses the multi-step reasoning pathway inside Gemini 3.5, pulling the response time down to its fastest possible threshold.
• Prompt Compression: Trimmed conversational fluff from your instructions. Shorter prompts take fewer milliseconds to process.
• Direct Instruction (Skip all introductory filler): Models often generate text like "Based on the context provided, here is the information...". Eliminating these extra words significantly slashes your Time-to-First-Token (TTFT).
Are you currently using standard execution (llm.invoke()) or are you streaming the tokens to your UI using llm.stream()? Switching your frontend and backend to streaming will make this feel instant to your users. Let me know if you want the code to implement that!


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
        
        messages = prompt_template.format_messages(
            context=context_data, 
            input=request.question
        )
        
        response = llm.invoke(messages)
        print("📤 Google Gemini replied successfully!")
        
        plain_text_answer = response.content
        if isinstance(plain_text_answer, list) and len(plain_text_answer) > 0:
            if isinstance(plain_text_answer, dict) and "text" in plain_text_answer:
                plain_text_answer = plain_text_answer["text"]
        
        return {"answer": str(plain_text_answer)}
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ BACKEND EXCEPTION: {error_msg}", file=sys.stderr)
        return {"answer": f"Backend Error: {error_msg}"}

if __name__ == "__main__":
    import uvicorn
    # Host '0.0.0.0' binds Uvicorn to all interfaces, allowing direct calls via Port 8000
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)