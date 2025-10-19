import json
import boto3
import time
import requests

# Initialize AWS clients
s3 = boto3.client("s3", region_name="us-east-2")  # bucket region
transcribe = boto3.client("transcribe", region_name="us-east-2")  # Transcribe in us-east-1
comprehend = boto3.client("comprehend", region_name="us-east-2")  # Tone analysis

# Helper functions
def generate_presigned_url(bucket_name, object_key, expiry=3600):
    """Generate presigned URL for S3 object"""
    return s3.generate_presigned_url(
        ClientMethod="get_object",
        Params={"Bucket": bucket_name, "Key": object_key},
        ExpiresIn=expiry
    )

def download_transcript(transcript_url):
    response = requests.get(transcript_url)
    data = response.json()
    return data["results"]["transcripts"][0]["transcript"]

def count_filler_words(text):
    fillers = ["um", "uh", "like", "you know", "so", "actually"]
    text_lower = text.lower()
    return sum(text_lower.count(word) for word in fillers)

def calculate_pace(text, duration_seconds):
    word_count = len(text.split())
    return round((word_count / duration_seconds) * 60, 1)

def analyze_tone(text):
    response = comprehend.detect_sentiment(Text=text, LanguageCode="en")
    return response["Sentiment"]

# Main Lambda handler
def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body", "{}"))
        recording_url = body.get("recordingUrl")
        if not recording_url:
            return {"statusCode": 400, "body": json.dumps({"message": "recordingUrl missing"})}

        # Extract bucket and key from S3 URL
        s3_parts = recording_url.replace("https://", "").split(".s3.amazonaws.com/")
        bucket_name = s3_parts[0]
        object_key = s3_parts[1]

        # Generate presigned URL (for Transcribe to access your bucket cross-region)
        presigned_url = generate_presigned_url(bucket_name, object_key)

        # Start Transcribe job
        job_name = f"transcription-{int(time.time())}"
        transcribe.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={"MediaFileUri": presigned_url},
            MediaFormat=object_key.split(".")[-1],  # mp3, wav, m4a
            LanguageCode="en-US"
        )

        # Wait for transcription to complete
        while True:
            status = transcribe.get_transcription_job(TranscriptionJobName=job_name)
            job_status = status["TranscriptionJob"]["TranscriptionJobStatus"]
            if job_status in ["COMPLETED", "FAILED"]:
                break
            time.sleep(2)

        if job_status == "FAILED":
            return {"statusCode": 500, "body": json.dumps({"message": "Transcription failed"})}

        # Download transcript
        transcript_url = status["TranscriptionJob"]["Transcript"]["TranscriptFileUri"]
        transcript_text = download_transcript(transcript_url)

        # Analyze transcript
        filler_count = count_filler_words(transcript_text)
        duration_seconds = 30  # default; could calculate from audio
        pace = calculate_pace(transcript_text, duration_seconds)
        tone = analyze_tone(transcript_text)

        # Suggested exercises
        exercises = []
        if filler_count > 3:
            exercises.append("Practice reducing filler words like 'um' and 'uh'.")
        if pace > 180:
            exercises.append("Practice slowing down your speech.")
        if tone.lower() == "negative":
            exercises.append("Try practicing positive phrasing and tone.")

        feedback = {
            "tone": tone,
            "pace_wpm": pace,
            "filler_words": filler_count,
            "suggested_exercises": exercises,
            "transcript": transcript_text
        }

        return {"statusCode": 200, "body": json.dumps({"recordingUrl": recording_url, "feedback": feedback})}

    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"message": "Analysis failed", "error": str(e)})}

if __name__ == "__main__":
    event = {
        "body": json.dumps({
            "recordingUrl": "https://student-app-recordings-2025.s3.amazonaws.com/presentations/audio.m4a"
        })
    }
    result = lambda_handler(event, None)
    print(json.dumps(result, indent=4))
