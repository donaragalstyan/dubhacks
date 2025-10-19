from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any
import json
import boto3
import uuid
import base64
from datetime import datetime
from .uploadRecording import lambda_handler as upload_recording_handler
from .analyzePresentation import lambda_handler as analyze_presentation_handler
from .analyzeExercise import lambda_handler as analyze_exercise_handler

app = FastAPI(
    title="Speech Analysis API",
    description="API for analyzing speech presentations",
    version="1.0.0"
)

# Initialize S3 client
s3 = boto3.client('s3', region_name='us-east-2')
BUCKET_NAME = "student-app-recordings-2025"  # Your S3 bucket name

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
        # Generate a unique file key for S3
        file_extension = file.filename.split('.')[-1] if '.' in file.filename else ''
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        unique_id = str(uuid.uuid4())[:8]
        file_key = f"recordings/{timestamp}-{unique_id}.{file_extension}"

        # Generate pre-signed URL for direct upload
        presigned_url = s3.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': BUCKET_NAME,
                'Key': file_key,
                'ContentType': file.content_type
            },
            ExpiresIn=3600  # URL expires in 1 hour
        )

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
            error_detail = json.loads(result["body"]) if isinstance(result.get("body"), str) else result.get("body", {})
            raise HTTPException(status_code=result["statusCode"], detail=error_detail)
            
        response_body = json.loads(result["body"]) if isinstance(result.get("body"), str) else result.get("body", {})
        return response_body
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from fastapi import Body

def format_tone_analysis(tone_data):
    """Format tone analysis into readable text."""
    classification = tone_data['classification']
    raw_scores = tone_data['raw']
    
    # Convert scores to percentages
    scores = {k: f"{v*100:.1f}%" for k, v in raw_scores.items()}
    dominant_tone = max(raw_scores.items(), key=lambda x: x[1])[0]
    
    return {
        "summary": f"Your tone is primarily {dominant_tone.lower()} ({scores[dominant_tone]})",
        "details": {
            "classification": classification.capitalize(),
            "scores": scores
        }
    }

def format_pace_analysis(pace_wpm):
    """Format pace analysis into readable text."""
    if pace_wpm < 100:
        assessment = "slower than typical"
        suggestion = "Try increasing your pace slightly while maintaining clarity."
    elif pace_wpm > 160:
        assessment = "faster than typical"
        suggestion = "Consider slowing down slightly for better comprehension."
    else:
        assessment = "within the ideal range"
        suggestion = "Keep maintaining this comfortable pace."
    
    return {
        "summary": f"You spoke at {pace_wpm:.1f} words per minute, which is {assessment}",
        "suggestion": suggestion
    }

def format_filler_analysis(filler_data):
    """Format filler word analysis into readable text."""
    total = filler_data['total']
    if total == 0:
        return {
            "summary": "No filler words detected - excellent work!",
            "details": None
        }
    
    # Filter out fillers with zero count
    used_fillers = {word: count for word, count in filler_data['per_filler'].items() if count > 0}
    filler_list = [f"'{word}' ({count} times)" for word, count in used_fillers.items()]
    
    return {
        "summary": f"Used {total} filler word{'s' if total > 1 else ''} in total",
        "details": {
            "breakdown": filler_list,
            "suggestion": "Practice pausing instead of using filler words."
        }
    }

def format_clarity_analysis(clarity_data):
    """Format clarity analysis into readable text."""
    score = clarity_data['details']['score']
    avg_sentence_length = clarity_data['details']['avg_sentence_length']
    complex_transitions = clarity_data['details']['complex_transition_count']
    
    if score >= 90:
        assessment = "excellent"
    elif score >= 70:
        assessment = "good"
    else:
        assessment = "needs improvement"
    
    return {
        "summary": f"Speech clarity is {assessment} ({score}/100)",
        "details": {
            "average_sentence_length": f"{avg_sentence_length:.1f} words",
            "complex_transitions": complex_transitions
        }
    }

@app.post("/api/analyze-presentation")
async def analyze_presentation(recording_url: str = Body(..., embed=True)) -> Dict[str, Any]:
    try:
        # Create event object similar to Lambda event
        print(recording_url)
        event = {
            "body": json.dumps({
                "recordingUrl": recording_url
            })
        }
        
        result = analyze_presentation_handler(event, None)
        
        if result["statusCode"] != 200:
            raise HTTPException(status_code=result["statusCode"], detail=json.loads(result["body"]))
        
        # Return exactly the same format as before
        return json.loads(result["body"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from pydantic import BaseModel

class ExerciseRequest(BaseModel):
    recording_url: str
    focus_area: str
    constraints: Dict[str, Any] = {}

@app.post("/api/analyze-exercise")
async def analyze_exercise(request: ExerciseRequest) -> Dict[str, Any]:
    try:
        # Pass data directly without JSON encoding
        event = {
            "body": {
                "recordingUrl": request.recording_url,
                "constraints": request.constraints
            }
        }
        print(f"Event data: {event}")  # Debug log
        
        # Call Lambda handler
        result = analyze_exercise_handler(event, None)
        
        if result["statusCode"] != 200:
            raise HTTPException(status_code=result["statusCode"], detail=json.loads(result["body"]))
        
        return json.loads(result["body"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "speech-analysis-api"}
