import os
import json
import logging
from typing import List, Optional
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Import LangChain components
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_community.vectorstores import Chroma
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Setup FastAPI App
app = FastAPI(
    title="Web-Augmented RAG Misinformation Detector API",
    description="Backend service utilizing Tavily, ChromaDB, and Google Gemini Flash to fact-check claims.",
    version="1.0.0"
)

# Enable CORS so the Chrome Extension can make requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

# Pydantic models for request and response validation
class ClaimRequest(BaseModel):
    claim: str = Field(..., description="The statement or selected text to verify.", min_length=5)

class VerificationResponse(BaseModel):
    verdict: str = Field(..., description="The rating of the claim (TRUE, FALSE, or MISLEADING).")
    analysis: str = Field(..., description="A concise 2-3 sentence analysis of why this verdict was reached.")
    sources: List[str] = Field(default=[], description="A list of source URLs supporting the analysis.")

@app.get("/")
def read_root():
    return {"status": "healthy", "service": "Misinformation Detector RAG API"}

@app.post("/verify", response_model=VerificationResponse)
async def verify_claim(request: ClaimRequest):
    claim = request.claim.strip()
    logger.info(f"Received claim verification request: '{claim}'")

    # 1. Validate API keys before running the pipeline
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    tavily_key = os.getenv("TAVILY_API_KEY")

    if not gemini_key:
        logger.error("Missing Gemini API Key in environment.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gemini API Key is missing. Please configure GEMINI_API_KEY in backend/.env"
        )
    
    if not tavily_key:
        logger.error("Missing Tavily API Key in environment.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tavily API Key is missing. Please configure TAVILY_API_KEY in backend/.env"
        )

    # Set keys in environment for LangChain modules
    os.environ["GOOGLE_API_KEY"] = gemini_key
    os.environ["TAVILY_API_KEY"] = tavily_key

    # Initialize variables for the RAG pipeline
    search_results = []
    retrieved_docs = []

    # --- STEP 1: Web Search ---
    logger.info("Executing Web Search via Tavily API...")
    try:
        # Fetch top 4 results with their raw content
        web_search = TavilySearchResults(
            max_results=4,
            include_raw_content=True
        )
        search_results = web_search.invoke(claim)
        logger.info(f"Tavily returned {len(search_results)} search results.")
    except Exception as e:
        logger.error(f"Error executing Tavily search: {str(e)}")
        # Provide a descriptive user-friendly message rather than crashing
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to query Tavily Search API. Check your TAVILY_API_KEY or connection. Error: {str(e)}"
        )

    # If Tavily returned absolutely no results, we can handle it gracefully
    if not search_results:
        logger.warning("No search results returned from Tavily.")
        # We can construct a direct question to the LLM noting that no web references were found,
        # or return a clean warning. Let's proceed, but create a placeholder context.
        context = "No relevant web search results could be retrieved for this claim."
        sources_list = []
    else:
        # --- STEP 2: Chunking ---
        logger.info("Splitting retrieved text into chunks...")
        docs = []
        sources_list = []
        
        for result in search_results:
            # We want raw content first for detail, fallback to content or snippet if raw content is missing
            content = result.get("raw_content") or result.get("content") or result.get("snippet")
            url = result.get("url", "")
            
            if url and url not in sources_list:
                sources_list.append(url)
                
            if content:
                # Store the source URL in the metadata
                docs.append(Document(page_content=content, metadata={"source": url}))
            else:
                logger.warning(f"Empty content for source URL: {url}")

        if not docs:
            context = "No content was extractable from the search results."
        else:
            try:
                # Use RecursiveCharacterTextSplitter with chunk_size=500 and chunk_overlap=50
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=500,
                    chunk_overlap=50
                )
                chunks = text_splitter.split_documents(docs)
                logger.info(f"Created {len(chunks)} chunks from search results.")

                # --- STEP 3: Ephemeral Vector Store ---
                logger.info("Initializing ephemeral Chroma vector store...")
                # Initialize Google embeddings
                embeddings = GoogleGenerativeAIEmbeddings(model="models/text-embedding-004")
                
                # Create an in-memory ephemeral Chroma instance
                vector_store = Chroma.from_documents(
                    documents=chunks,
                    embedding=embeddings
                )

                # --- STEP 4: Retrieval ---
                logger.info("Retrieving top 3 relevant chunks...")
                retriever = vector_store.as_retriever(search_kwargs={"k": 3})
                retrieved_docs = retriever.invoke(claim)
                logger.info(f"Retrieved {len(retrieved_docs)} chunks from vector store.")

                # Format retrieved chunks as a neat context block for the LLM
                context_parts = []
                for idx, doc in enumerate(retrieved_docs):
                    source = doc.metadata.get("source", "Unknown URL")
                    context_parts.append(f"Source [{idx + 1}]: {source}\nContent: {doc.page_content}")
                context = "\n\n---\n\n".join(context_parts)
                
            except Exception as e:
                logger.error(f"Error during chunking/vector-store/retrieval: {str(e)}")
                # If embeddings or Chroma fail, fallback to using raw snippets directly
                logger.warning("Falling back to raw Tavily snippets due to processing error.")
                context_parts = []
                for idx, res in enumerate(search_results[:4]):
                    context_parts.append(f"Source [{idx + 1}]: {res.get('url')}\nContent: {res.get('content') or res.get('snippet')}")
                context = "\n\n---\n\n".join(context_parts)

    # --- STEP 5: LLM Fact-Checking & Evaluation ---
    logger.info("Evaluating claim with ChatGoogleGenerativeAI (gemini-3.5-flash)...")
    try:
        # Prompt as specified in instructions
        prompt = ChatPromptTemplate.from_messages([
            ("system", (
                "You are an expert fact-checker. Evaluate the user's CLAIM strictly using the provided CONTEXT. "
                "Classify the claim into exactly one of three categories: TRUE, FALSE, or MISLEADING. "
                "Provide a concise 2-3 sentence explanation. "
                "Return your response in JSON format with three keys: "
                "'verdict' (must be exactly 'TRUE', 'FALSE', or 'MISLEADING'), "
                "'analysis' (concise 2-3 sentence explanation), and "
                "'sources' (a list of URLs from the context that support your verdict)."
            )),
            ("human", "CLAIM: {claim}\n\nCONTEXT:\n{context}")
        ])

        # Initialize LLM with structured JSON output configuration
        llm = ChatGoogleGenerativeAI(
            model="gemini-3.5-flash",
            temperature=0.0,
            model_kwargs={"response_mime_type": "application/json"}
        )

        # Formulate prompt and execute
        chain = prompt | llm
        response = chain.invoke({"claim": claim, "context": context})
        
        # Parse the structured JSON response
        raw_content = response.content
        if isinstance(raw_content, list):
            parts = []
            for part in raw_content:
                if isinstance(part, str):
                    parts.append(part)
                elif isinstance(part, dict) and "text" in part:
                    parts.append(str(part["text"]))
                elif hasattr(part, "text"):
                    parts.append(str(part.text))
                else:
                    parts.append(str(part))
            raw_content = "".join(parts)
            
        if not isinstance(raw_content, str):
            raw_content = str(raw_content)
        
        raw_content = raw_content.strip()
        logger.info(f"Raw LLM response: {raw_content}")

        # Clean markdown fences if any (though response_mime_type should return pure JSON)
        if raw_content.startswith("```json"):
            raw_content = raw_content[7:]
        if raw_content.endswith("```"):
            raw_content = raw_content[:-3]
        
        if not isinstance(raw_content, str):
            raw_content = str(raw_content)
            
        raw_content = raw_content.strip()

        parsed_response = json.loads(raw_content)
        if isinstance(parsed_response, list) and len(parsed_response) > 0:
            parsed_response = parsed_response[0]
        elif not isinstance(parsed_response, dict):
            parsed_response = {}

        # Enforce exact key matches and type consistency
        verdict = str(parsed_response.get("verdict", "MISLEADING")).upper()
        if verdict not in ["TRUE", "FALSE", "MISLEADING"]:
            # Standardize output
            if "TRUE" in verdict:
                verdict = "TRUE"
            elif "FALSE" in verdict:
                verdict = "FALSE"
            else:
                verdict = "MISLEADING"

        analysis = parsed_response.get("analysis", "No explanation was generated.")
        sources = parsed_response.get("sources", [])
        if not isinstance(sources, list):
            sources = [str(sources)] if sources else []
            
        # Ensure we have at least some sources if LLM returned empty list but we scraped some
        if not sources and sources_list:
            sources = sources_list[:3]

        return VerificationResponse(
            verdict=verdict,
            analysis=analysis,
            sources=sources
        )

    except json.JSONDecodeError as je:
        logger.error(f"JSON Decode Error from LLM response: {str(je)}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LLM output did not return valid JSON fact-checking structure. Please try again."
        )
    except Exception as e:
        logger.error(f"Error evaluating claim via Gemini: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while evaluating the claim with Gemini: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    # Allow running the app directly via 'python main.py'
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
