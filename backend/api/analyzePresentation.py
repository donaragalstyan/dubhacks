import json
import boto3
import time
import requests

# Initialize AWS clients
s3 = boto3.client("s3", region_name="us-east-2")  # bucket region
transcribe = boto3.client("transcribe", region_name="us-east-2")  # Transcribe in us-east-1
comprehend = boto3.client("comprehend", region_name="us-east-2")  # Tone analysis

# Helper functions
def download_transcript(transcript_url):
    response = requests.get(transcript_url)
    data = response.json()
    try:
        if not data.get("results") or not data["results"].get("transcripts") or not data["results"]["transcripts"]:
            raise ValueError("No transcript data found in response")
        return data["results"]["transcripts"][0]["transcript"]
    except Exception as e:
        raise ValueError(f"Failed to extract transcript from response: {str(e)}")

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


def parse_s3_url(url: str):
    """Parse common S3 URL formats and return (bucket, key).

    Supported formats:
    - https://bucket.s3.amazonaws.com/key
    - https://bucket.s3.region.amazonaws.com/key
    - https://s3.amazonaws.com/bucket/key
    - https://s3.region.amazonaws.com/bucket/key
    - s3://bucket/key
    - optionally with query string (will be stripped)
    """
    # strip query params
    url_no_q = url.split("?")[0]
    if url_no_q.startswith("s3://"):
        rest = url_no_q[len("s3://"):]
        parts = rest.split("/", 1)
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError("Invalid s3:// URL format")
        return parts[0], parts[1]

    # remove scheme
    if url_no_q.startswith("https://"):
        host_path = url_no_q[len("https://"):]
    elif url_no_q.startswith("http://"):
        host_path = url_no_q[len("http://"):]
    else:
        host_path = url_no_q

    # virtual-hosted style: bucket.s3.amazonaws.com/key or bucket.s3.region.amazonaws.com/key
    if ".s3." in host_path and ".amazonaws.com/" in host_path:
        # split into host and key
        host, key = host_path.split(".amazonaws.com/", 1)
        # host may be bucket.s3 or bucket.s3.region
        bucket = host.split(".s3")[0]
        if not bucket or not key:
            raise ValueError("Invalid virtual-hosted S3 URL")
        return bucket, key

    # path-style: s3.amazonaws.com/bucket/key or s3.region.amazonaws.com/bucket/key
    if host_path.startswith("s3.amazonaws.com/") or host_path.startswith("s3.") and ".amazonaws.com/" in host_path:
        # split after domain
        parts = host_path.split(".amazonaws.com/", 1)
        if len(parts) == 2:
            rest = parts[1]
        else:
            # fallback if startswith s3.amazonaws.com/
            rest = host_path.split("/", 1)[1] if "/" in host_path else ""
        if not rest:
            raise ValueError("Invalid path-style S3 URL")
        segs = rest.split("/", 1)
        if len(segs) != 2:
            raise ValueError("Invalid path-style S3 URL: missing object key")
        bucket, key = segs[0], segs[1]
        return bucket, key

    # fallback: maybe a simple host/key with bucket.s3.amazonaws.com/key already handled above
    # If we reach here, we couldn't parse
    raise ValueError("Unrecognized S3 URL format")

# Main Lambda handler
def lambda_handler(event, context):
    try:
        body = json.loads(event.get("body", "{}"))
        recording_url = body.get("recordingUrl")
        if not recording_url:
            return {"statusCode": 400, "body": json.dumps({"message": "recordingUrl missing"})}

        # Extract bucket and key from S3 URL (support multiple common formats)
        try:
            bucket_name, object_key = parse_s3_url(recording_url)
        except Exception as e:
            return {"statusCode": 400, "body": json.dumps({"message": "Invalid S3 URL format. Expected formats: https://bucket.s3.amazonaws.com/key or s3://bucket/key or path-style s3.amazonaws.com/bucket/key", "error": str(e)})}

        # Create S3 URI format for Transcribe
        s3_uri = f"s3://{bucket_name}/{object_key}"

        # Start Transcribe job
        job_name = f"transcription-{int(time.time())}"
        transcribe.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={"MediaFileUri": s3_uri},
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
            "recordingUrl": "https://student-app-recordings-2025.s3.us-east-2.amazonaws.com/presentations/test.wav?AWSAccessKeyId=AKIA3HPS6GVVHCU57LXA&Signature=nzfh9KsX12rFVOFXBglHeGclid8%3D&Expires=1760852654"
        })
    }
    result = lambda_handler(event, None)
    print(json.dumps(result, indent=4))
