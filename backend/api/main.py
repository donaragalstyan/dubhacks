from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import boto3
import json

app = FastAPI(title="Presentation Analyzer API")

# Lambda client
lambda_client = boto3.client("lambda", region_name="us-east-2")  # or your Lambda region

# Request model
class AnalyzeRequest(BaseModel):
    recordingUrl: str

@app.post("/analyze")
def analyze_presentation(request: AnalyzeRequest):
    try:
        # Invoke the Lambda
        response = lambda_client.invoke(
            FunctionName="analysePresentation",  # replace with your Lambda name
            InvocationType="RequestResponse",
            Payload=json.dumps({
                "body": json.dumps({"recordingUrl": request.recordingUrl})
            })
        )

        result = json.loads(response['Payload'].read())
        # Return the Lambda response directly
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
