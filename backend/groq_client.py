import os
import logging
import asyncio
from typing import Optional
import aiohttp

# Initialize logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Groq API endpoint and key
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "llama3-70b-8192"  # Using Llama 3 70B model, but can be changed

# Validate API key format (basic check)
if GROQ_API_KEY and (len(GROQ_API_KEY) < 20 or not GROQ_API_KEY.startswith("gsk_")):
    logger.warning("GROQ_API_KEY appears to be invalid (wrong format or too short)")
    # Don't log the actual key for security reasons

# Maximum tokens for context window
MAX_TOKENS = 8000  # Reserve some tokens for the response

# Dictionary to store recently processed document content
# Structure: {
#   channel_id: {
#      "channel_docs": {"text": document_text, "filename": filename, "timestamp": timestamp},
#      "user_docs": {
#          user_id: {"text": document_text, "filename": filename, "timestamp": timestamp}
#      }
#   }
# }
document_cache = {}

# Maximum age of cached documents in hours
CACHE_EXPIRY_HOURS = 24

async def summarize_text(text: str) -> Optional[str]:
    """
    Summarize text using Groq's LLM API.
    
    Args:
        text (str): Text content to summarize
        
    Returns:
        Optional[str]: Summarized text or None if summarization fails
    """
    if not GROQ_API_KEY:
        logger.error("GROQ_API_KEY environment variable not set")
        return "Error: Groq API key not provided. Please configure the GROQ_API_KEY environment variable."
    
    # Truncate text if too long to fit in context window
    if len(text) > MAX_TOKENS * 4:  # Rough estimate: 4 chars per token
        logger.warning(f"Text too long ({len(text)} chars). Truncating...")
        text = text[:MAX_TOKENS * 4]
        text += "\n\n[Note: Document was truncated due to length constraints]"
    
    # Prepare the prompt for the LLM
    system_prompt = """
    You are an expert document summarizer. Your task is to create a comprehensive summary of the document provided. 
    Follow these guidelines:
    
    1. Extract and highlight the key points, main arguments, and conclusions
    2. Maintain the original document's structure in your summary (sections, chapters, etc.)
    3. Preserve important details, figures, data points, and quotations
    4. Be concise yet thorough
    5. Format the summary with clear headings, bullet points, and paragraphs for readability
    6. The summary should be about 20-30% of the original document's length
    
    Aim to create a summary that could serve as a standalone representation of the document for someone who hasn't read the original.
    """
    
    user_prompt = f"Please summarize the following document: \n\n{text}"
    
    # Prepare the API request
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GROQ_API_KEY}"
    }
    
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.3,  # Lower temperature for more focused and deterministic output
        "max_tokens": 4000,  # Maximum tokens for the summary response
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(GROQ_API_URL, headers=headers, json=payload) as response:
                if response.status != 200:
                    try:
                        error_data = await response.json()
                        error_message = error_data.get('error', {}).get('message', 'Unknown error')
                        error_type = error_data.get('error', {}).get('type', 'unknown')
                        logger.error(f"Groq API error: {response.status} - Type: {error_type} - Message: {error_message}")
                        return f"Error: Failed to get summary from Groq API: {error_message}"
                    except:
                        error_text = await response.text()
                        logger.error(f"Groq API error: {response.status} - {error_text}")
                        return f"Error: Failed to get summary from Groq API (Status code: {response.status})"
                
                # Process successful response
                result = await response.json()
                
                if "choices" in result and len(result["choices"]) > 0:
                    summary = result["choices"][0]["message"]["content"]
                    return summary
                else:
                    logger.error("No choices found in Groq API response")
                    return "Error: Invalid response format from Groq API"
    
    except aiohttp.ClientError as e:
        logger.error(f"Error connecting to Groq API: {str(e)}")
        return f"Error: Connection to Groq API failed: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error during summarization: {str(e)}", exc_info=True)
        return f"Error: Failed to generate summary: {str(e)}"


async def answer_question(text: str, question: str) -> Optional[str]:
    """
    Answer a question about the provided text using Groq's LLM API.
    
    Args:
        text (str): The document text to reference
        question (str): The question to answer
        
    Returns:
        Optional[str]: The answer or None if answering fails
    """
    if not GROQ_API_KEY:
        logger.error("GROQ_API_KEY environment variable not set")
        return "Error: Groq API key not provided. Please configure the GROQ_API_KEY environment variable."
    
    # Truncate text if too long to fit in context window
    if len(text) > MAX_TOKENS * 4:  # Rough estimate: 4 chars per token
        logger.warning(f"Text too long ({len(text)} chars). Truncating...")
        text = text[:MAX_TOKENS * 4]
        text += "\n\n[Note: Document was truncated due to length constraints]"
    
    # Prepare the prompt for the LLM
    system_prompt = """
    You are an expert document analyst and question answerer. Your task is to answer questions about the document provided.
    Follow these guidelines:
    
    1. Answer the question as thoroughly as possible based ONLY on the information in the document
    2. If the answer is not in the document, clearly state that you cannot find the information
    3. Include relevant quotes or data from the document to support your answer
    4. Format your answer clearly with paragraphs and bullet points when appropriate
    5. Be accurate and objective - don't make up information not present in the document
    
    Focus on providing a precise, accurate, and comprehensive answer to the question asked.
    """
    
    user_prompt = f"Document:\n\n{text}\n\nQuestion: {question}\n\nPlease provide a thorough answer to this question based on the document."
    
    # Prepare the API request
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GROQ_API_KEY}"
    }
    
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.2,  # Lower temperature for more accurate answers
        "max_tokens": 3000,  # Maximum tokens for the answer
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(GROQ_API_URL, headers=headers, json=payload) as response:
                if response.status != 200:
                    try:
                        error_data = await response.json()
                        error_message = error_data.get('error', {}).get('message', 'Unknown error')
                        error_type = error_data.get('error', {}).get('type', 'unknown')
                        logger.error(f"Groq API error: {response.status} - Type: {error_type} - Message: {error_message}")
                        return f"Error: Failed to get answer from Groq API: {error_message}"
                    except:
                        error_text = await response.text()
                        logger.error(f"Groq API error: {response.status} - {error_text}")
                        return f"Error: Failed to get answer from Groq API (Status code: {response.status})"
                
                # Process successful response
                result = await response.json()
                
                if "choices" in result and len(result["choices"]) > 0:
                    answer = result["choices"][0]["message"]["content"]
                    return answer
                else:
                    logger.error("No choices found in Groq API response")
                    return "Error: Invalid response format from Groq API"
    
    except aiohttp.ClientError as e:
        logger.error(f"Error connecting to Groq API: {str(e)}")
        return f"Error: Connection to Groq API failed: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error during question answering: {str(e)}", exc_info=True)
        return f"Error: Failed to generate answer: {str(e)}"


def store_document(channel_id: str, document_text: str, filename: str, user_id: str = None) -> None:
    """
    Store document text in the cache for later questions.
    
    Args:
        channel_id (str): Discord channel ID as the key
        document_text (str): The parsed document text
        filename (str): Original filename for reference
        user_id (str, optional): Discord user ID for per-user storage
    """
    import datetime
    
    # Ensure channel entry exists with proper structure
    if channel_id not in document_cache:
        document_cache[channel_id] = {
            "channel_docs": None,
            "user_docs": {}
        }
    
    timestamp = datetime.datetime.now()
    doc_data = {
        "text": document_text,
        "filename": filename,
        "timestamp": timestamp
    }
    
    # Always store as the channel's current document
    document_cache[channel_id]["channel_docs"] = doc_data
    
    # If user ID provided, store as that user's document
    if user_id:
        if "user_docs" not in document_cache[channel_id]:
            document_cache[channel_id]["user_docs"] = {}
        document_cache[channel_id]["user_docs"][user_id] = doc_data
        logger.info(f"Stored document '{filename}' for user {user_id} in channel {channel_id}")
    else:
        logger.info(f"Stored document '{filename}' for channel {channel_id}")
    
    # Cleanup expired documents (every 10 new docs to avoid constant checking)
    if hash(filename) % 10 == 0:
        clean_expired_documents()


def get_document(channel_id: str, user_id: str = None) -> Optional[dict]:
    """
    Retrieve document data from the cache.
    
    Args:
        channel_id (str): Discord channel ID
        user_id (str, optional): Discord user ID for per-user retrieval
        
    Returns:
        Optional[dict]: Document data or None if not found
    """
    if channel_id not in document_cache:
        return None
        
    # If user ID provided and user has documents, return their most recent one
    if user_id and "user_docs" in document_cache[channel_id] and user_id in document_cache[channel_id]["user_docs"]:
        return document_cache[channel_id]["user_docs"][user_id]
    
    # Fallback to channel's most recent document
    return document_cache[channel_id].get("channel_docs")


def clean_expired_documents() -> None:
    """
    Clean up documents that are older than the expiry time.
    """
    import datetime
    
    now = datetime.datetime.now()
    expiry_delta = datetime.timedelta(hours=CACHE_EXPIRY_HOURS)
    expired_count = 0
    
    for channel_id in list(document_cache.keys()):
        # Check channel document
        if document_cache[channel_id].get("channel_docs"):
            doc_time = document_cache[channel_id]["channel_docs"]["timestamp"]
            if now - doc_time > expiry_delta:
                document_cache[channel_id]["channel_docs"] = None
                expired_count += 1
                
        # Check user documents
        if "user_docs" in document_cache[channel_id]:
            for user_id in list(document_cache[channel_id]["user_docs"].keys()):
                doc_time = document_cache[channel_id]["user_docs"][user_id]["timestamp"]
                if now - doc_time > expiry_delta:
                    del document_cache[channel_id]["user_docs"][user_id]
                    expired_count += 1
                    
        # Remove empty channel entries
        if not document_cache[channel_id].get("channel_docs") and not document_cache[channel_id].get("user_docs"):
            del document_cache[channel_id]
    
    if expired_count > 0:
        logger.info(f"Cleaned up {expired_count} expired documents from cache")


def chunk_text(text: str, max_chunk_size: int = 8000) -> list:
    """
    Split text into chunks of appropriate size for the LLM API.
    
    Args:
        text (str): Text to split into chunks
        max_chunk_size (int): Maximum size of each chunk
        
    Returns:
        list: List of text chunks
    """
    # Simple chunking by character count - can be improved with better tokenization
    chunks = []
    
    # Split by paragraphs first to maintain coherence
    paragraphs = text.split('\n')
    current_chunk = ""
    
    for para in paragraphs:
        if len(current_chunk) + len(para) + 1 <= max_chunk_size:
            current_chunk += para + '\n'
        else:
            # If current paragraph would make chunk too large
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = para + '\n'
            else:
                # If a single paragraph is too large, we need to split it
                for i in range(0, len(para), max_chunk_size):
                    chunk = para[i:i + max_chunk_size]
                    chunks.append(chunk)
                current_chunk = ""
    
    # Don't forget the last chunk
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks
