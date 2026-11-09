import os
import sys
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from dotenv import load_dotenv
# 1. INITIALIZE FASTAPI & CORS
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
load_dotenv()
# 2. SECURE ENVIRONMENT VARIABLE INTEGRATION
# Pulls the key dynamically from your EC2 Linux instance memory (setup via export command)
GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")

if not GOOGLE_API_KEY:
    # Fails immediately if the environment variable was not correctly applied or loaded
    raise ValueError("CRITICAL ERROR: GOOGLE_API_KEY environment variable is missing on this EC2 instance!")

# 3. HELPER FUNCTION TO READ FILE
def read_sample_file(file_path: str = "sample.txt") -> str:
    if not os.path.exists(file_path):
        with open(file_path, "w", encoding="utf-8") as f:
            f.write("Retrieval-Augmented Generation (RAG) helps LLMs access external knowledge bases without retraining.")
    
    with open(file_path, "r", encoding="utf-8") as file:
        return file.read()

# 4. CONFIGURE GEMINI MODEL
# The model now receives the secure environment variable key directly
llm = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    temperature=0.3,
    google_api_key=GOOGLE_API_KEY
)

system_prompt = (
    "You are a helpful assistant for the Kadirur village chatbot. "
    "You have access to a local knowledge base provided below in the Context section.\n\n"
    "INSTRUCTIONS:\n"
    "1. If the user's question relates to the provided Context, prioritize using that context to answer.\n"
    "2. If the user asks a general knowledge question, greetings, or something outside the context, "
    "use your own extensive general knowledge base to answer accurately.\n"
    "3. You must provide your response in both English and Malayalam.\n"
    "4. Write the English response first, followed exactly by the separator line '---', followed by the Malayalam translation.\n"
    "5. Do not use markdown asterisks (**) or bold text indicators anywhere.\n\n"
    "Context:\n{context}"
)
prompt_template = ChatPromptTemplate.from_messages([
    ("system", system_prompt),
    ("human", "{input}"),
])

# 5. ROBUST ROUTE PIPELINE
class QueryRequest(BaseModel):
    question: str

@app.post("/api/query")
async def query_file(request: QueryRequest):
    print(f"📥 Received incoming query: {request.question}")
    try:
        context_data = read_sample_file("sample.txt")
        
        messages = prompt_template.format_messages(
            context=context_data, 
            input=request.question
        )
        
        response = llm.invoke(messages)
        print("📤 Gemini replied successfully!")
        
        # Extract plain text directly from LangChain's response message content property
        plain_text_answer = response.content
        if isinstance(plain_text_answer, list) and len(plain_text_answer) > 0:
            if isinstance(plain_text_answer[0], dict) and "text" in plain_text_answer[0]:
                plain_text_answer = plain_text_answer[0]["text"]
        
        return {"answer": str(plain_text_answer)}
        
    except Exception as e:
        error_msg = str(e)
        print(f"❌ BACKEND EXCEPTION: {error_msg}", file=sys.stderr)
        return {"answer": f"Backend Error: {error_msg}"}

if __name__ == "__main__":
    import uvicorn
    # '0.0.0.0' binds Uvicorn to all interfaces, allowing public calls via your IP: 43.205.177.98
    # Port 8000 matches your API endpoint configuration
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)