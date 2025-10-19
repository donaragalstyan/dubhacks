import json
import boto3
import time
import requests

# Initialize AWS clients
s3 = boto3.client("s3")
transcribe = boto3.client("transcribe")
comprehend = boto3.client("comprehend")  # for tone/sentiment analysis

# Helper functions
def download_transcript(transcript_url):
    response = requests.get(transcript_url)
    data = response.json()
    return data["results"]["transcripts"][0]["transcript"]

def count_filler_words(text):
    fillers = ["um", "uh", "like", "you know", "so", "actually"]
    text_lower = text.lower()
    count = sum(text_lower.count(word) for word in fillers)
    return count

def calculate_pace(text, duration_seconds):
    word_count = len(text.split())
    pace_wpm = (word_count / duration_seconds) * 60
    return round(pace_wpm, 1)

def analyze_tone(text):
    response = comprehend.detect_sentiment(Text=text, LanguageCode="en")
    return response["Sentiment"]

# Main Lambda handler
def lambda_handler(event, context):
    try:
        # Parse input
        body = json.loads(event.get("body", "{}"))
        recording_url = body.get("recordingUrl")
        if not recording_url:
            return {"statusCode": 400, "body": json.dumps({"message": "recordingUrl missing"})}

        # Extract bucket and key from S3 URL
        s3_parts = recording_url.replace("https://", "").split(".s3.amazonaws.com/")
        bucket_name = s3_parts[0].split(".")[0]
        object_key = s3_parts[1]

        # Start Amazon Transcribe job
        job_name = f"transcription-{int(time.time())}"
        transcribe.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={"MediaFileUri": recording_url},
            MediaFormat=object_key.split(".")[-1],  # mp3 or wav
            LanguageCode="en-US"
        )

        # Wait for transcription to complete
        while True:
            status = transcribe.get_transcription_job(TranscriptionJobName=job_name)
            job_status = status["TranscriptionJob"]["TranscriptionJobStatus"]
            if job_status in ["COMPLETED", "FAILED"]:
                break
            time.sleep(1)

        if job_status == "FAILED":
            return {"statusCode": 500, "body": json.dumps({"message": "Transcription failed"})}

        # Download transcript
        transcript_url = status["TranscriptionJob"]["Transcript"]["TranscriptFileUri"]
        transcript_text = download_transcript(transcript_url)

        # Analyze transcript
        filler_count = count_filler_words(transcript_text)
        duration_seconds = 30  # default duration; ideally calculate from audio metadata
        pace = calculate_pace(transcript_text, duration_seconds)
        tone = analyze_tone(transcript_text)

        # Suggest exercises
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
