import requests
import os
from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from fastapi.exceptions import RequestValidationError
from app.operations import add, subtract, multiply, divide
import logging
import uvicorn

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app setup
app = FastAPI()

# Setup templates directory (adjust according to your project structure)
templates = Jinja2Templates(directory="templates")

# API Configuration
API_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
API_KEY = os.getenv("API_KEY")  # Ensure your .env file contains API_KEY

# Pydantic model for request data
class OperationRequest(BaseModel):
    a: float = Field(..., description="The first number")
    b: float = Field(..., description="The second number")

class LLMRequest(BaseModel):
    query: str = Field(..., description="User query for LLM")

class LLMResponse(BaseModel):
    operation: str = Field(..., description="Suggested operation")
    explanation: str = Field(..., description="Explanation from LLM")

# Custom Exception Handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.error(f"HTTPException on {request.url.path}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    error_messages = "; ".join([f"{err['loc'][-1]}: {err['msg']}" for err in exc.errors()])
    logger.error(f"ValidationError on {request.url.path}: {error_messages}")
    return JSONResponse(
        status_code=400,
        content={"error": error_messages},
    )

# LLM route to suggest an operation based on user query
@app.post("/llm", response_model=LLMResponse, responses={400: {"description": "Error occurred"}})
async def llm_route(llm_request: LLMRequest):
    """
    Use LLM to suggest an operation.
    """
    query = llm_request.query
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "gpt-4",
        "messages": [
            {"role": "system", "content": "You are a helpful assistant that suggests mathematical operations."},
            {"role": "user", "content": query},
        ],
    }

    try:
        response = requests.post(API_ENDPOINT, headers=headers, json=payload)
        response.raise_for_status()  # Raise an error for bad HTTP status codes
        result = response.json()

        # Parse the LLM response
        suggestion = result["choices"][0]["message"]["content"]
        
        # Determine the operation
        if "add" in suggestion.lower():
            operation = "add"
        elif "subtract" in suggestion.lower():
            operation = "subtract"
        elif "multiply" in suggestion.lower():
            operation = "multiply"
        elif "divide" in suggestion.lower():
            operation = "divide"
        else:
            raise ValueError("Unable to determine operation from LLM response.")

        return LLMResponse(operation=operation, explanation=suggestion)
    except requests.RequestException as e:
        logger.error(f"LLM API Request Error: {str(e)}")
        raise HTTPException(status_code=400, detail="Error communicating with LLM API.")
    except Exception as e:
        logger.error(f"LLM Parsing Error: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Error processing LLM response: {str(e)}")

# Example route to demonstrate using LLM with operations
@app.post("/llm/execute")
async def llm_execute(operation: OperationRequest, llm_suggestion: LLMResponse = Depends(llm_route)):
    """
    Execute the operation suggested by the LLM.
    """
    if llm_suggestion.operation == "add":
        result = add(operation.a, operation.b)
    elif llm_suggestion.operation == "subtract":
        result = subtract(operation.a, operation.b)
    elif llm_suggestion.operation == "multiply":
        result = multiply(operation.a, operation.b)
    elif llm_suggestion.operation == "divide":
        result = divide(operation.a, operation.b)
    else:
        raise HTTPException(status_code=400, detail="Unsupported operation suggested by LLM.")
    
    return {"result": result, "explanation": llm_suggestion.explanation}

# Route to render the index template
@app.get("/")
async def read_root(request: Request):
    """
    Render the index.html template.
    """
    return templates.TemplateResponse("index.html", {"request": request})

# Run the app with uvicorn
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
