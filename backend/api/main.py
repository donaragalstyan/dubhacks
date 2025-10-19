from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any
import json
import base64
import os
from .uploadRecording import lambda_handler as upload_recording_handler
from .analyzePresentation import lambda_handler as analyze_presentation_handler

app = FastAPI(
    title="Speech Analysis API",
    description="API for analyzing speech presentations",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

@app.post("/api/upload-recording")
async def upload_recording(file: UploadFile = File(...)) -> Dict[str, Any]:
    try:
        # Read file content
        file_content = await file.read()
        
        # Create event object similar to Lambda event
        event = {
            "body": json.dumps({
                "fileName": file.filename,
                "fileType": file.content_type,
                "fileContent": base64.b64encode(file_content).decode('utf-8')
            })
        }
        
        # Call Lambda handler
        result = upload_recording_handler(event, None)
        
        if result["statusCode"] != 200:
            raise HTTPException(status_code=result["statusCode"], detail=json.loads(result["body"]))
            
        return json.loads(result["body"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from fastapi import Body

@app.post("/api/analyze-presentation")
async def analyze_presentation(recording_url: str = Body(..., embed=True)) -> Dict[str, Any]:
    try:
        # Create event object similar to Lambda event
        event = {
            "body": json.dumps({
                "recordingUrl": recording_url
            })
        }
        
        # return {"status": "healthy", "service": "speech-analysis-api"}
        # Call Lambda handler
        result = analyze_presentation_handler(event, None)
        
        if result["statusCode"] != 200:
            raise HTTPException(status_code=result["statusCode"], detail=json.loads(result["body"]))
            
        return json.loads(result["body"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "speech-analysis-api"}