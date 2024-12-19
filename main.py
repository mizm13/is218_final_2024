from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.exceptions import RequestValidationError  # <-- Add this import
from pydantic import BaseModel, Field
import requests
import os
import logging
import uvicorn

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Setup FastAPI app
app = FastAPI()

# Setup templates directory
templates = Jinja2Templates(directory="templates")

# API Configuration
API_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
API_KEY = os.getenv("API_KEY")  # Ensure your .env file contains API_KEY

# Pydantic model for operation input data
class OperationRequest(BaseModel):
    a: float = Field(..., description="The first number")
    b: float = Field(..., description="The second number")

# Pydantic model for operation response
class OperationResponse(BaseModel):
    result: float = Field(..., description="The result of the operation")

# Pydantic model for error response
class ErrorResponse(BaseModel):
    error: str = Field(..., description="Error message")

# Pydantic model for LLM request data
class LLMRequest(BaseModel):
    query: str = Field(..., description="User query for LLM")

# Pydantic model for LLM response
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

# Function to interact with the LLM API and get operation suggestion
def perform_llm_operation(query: str) -> LLMResponse:
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
        raise HTTPException(status_code=400, detail=str(e))

# Operation Routes

@app.post("/add", response_model=OperationResponse, responses={400: {"model": ErrorResponse}})
async def add_route(operation: OperationRequest):
    """
    Add two numbers.
    """
    try:
        result = operation.a + operation.b
        return OperationResponse(result=result)
    except Exception as e:
        logger.error(f"Add Operation Error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/subtract", response_model=OperationResponse, responses={400: {"model": ErrorResponse}})
async def subtract_route(operation: OperationRequest):
    """
    Subtract two numbers.
    """
    try:
        result = operation.a - operation.b
        return OperationResponse(result=result)
    except Exception as e:
        logger.error(f"Subtract Operation Error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/multiply", response_model=OperationResponse, responses={400: {"model": ErrorResponse}})
async def multiply_route(operation: OperationRequest):
    """
    Multiply two numbers.
    """
    try:
        result = operation.a * operation.b
        return OperationResponse(result=result)
    except Exception as e:
        logger.error(f"Multiply Operation Error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/divide", response_model=OperationResponse, responses={400: {"model": ErrorResponse}})
async def divide_route(operation: OperationRequest):
    """
    Divide two numbers.
    """
    try:
        if operation.b == 0:
            raise ValueError("Cannot divide by zero!")
        result = operation.a / operation.b
        return OperationResponse(result=result)
    except ValueError as e:
        logger.error(f"Divide Operation Error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Divide Operation Internal Error: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal Server Error")

# Route to perform operation using LLM suggestion
@app.post("/llm/execute", response_model=OperationResponse)
async def llm_execute(operation: OperationRequest, llm_request: LLMRequest):
    """
    Execute the operation suggested by the LLM.
    """
    llm_suggestion = perform_llm_operation(llm_request.query)

    if llm_suggestion.operation == "add":
        result = operation.a + operation.b
    elif llm_suggestion.operation == "subtract":
        result = operation.a - operation.b
    elif llm_suggestion.operation == "multiply":
        result = operation.a * operation.b
    elif llm_suggestion.operation == "divide":
        if operation.b == 0:
            raise HTTPException(status_code=400, detail="Cannot divide by zero")
        result = operation.a / operation.b
    else:
        raise HTTPException(status_code=400, detail="Unsupported operation suggested by LLM.")

    return OperationResponse(result=result)

# Route to serve the main template (form)
@app.get("/")
async def read_root(request: Request):
    """
    Serve the index.html template.
    """
    return templates.TemplateResponse("index.html", {"request": request})

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
