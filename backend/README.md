# Speech Analysis API

This FastAPI application provides endpoints for uploading and analyzing speech recordings.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Set up environment variables:
Create a `.env` file with the following variables:
```
BUCKET_NAME=student-app-recordings-2025
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-2
```

## Running the API

Run the server:
```bash
python run.py
```

The API will be available at `http://localhost:8000`.

## API Endpoints

### Upload Recording
- **URL**: `/api/upload-recording`
- **Method**: POST
- **Content-Type**: multipart/form-data
- **Parameters**: 
  - `file`: The audio file to upload

### Analyze Presentation
- **URL**: `/api/analyze-presentation`
- **Method**: POST
- **Content-Type**: application/json
- **Parameters**:
  - `recording_url`: The URL of the recording to analyze

### Health Check
- **URL**: `/api/health`
- **Method**: GET

## Documentation

API documentation is available at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`