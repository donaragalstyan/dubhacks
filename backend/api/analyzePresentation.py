import json
import boto3
import time
import requests
import re
from typing import Dict, Any, List, Tuple

# Initialize AWS clients
s3 = boto3.client("s3", region_name="us-east-2")  # bucket region
transcribe = boto3.client("transcribe", region_name="us-east-2")  # Transcribe in us-east-1
comprehend = boto3.client("comprehend", region_name="us-east-2")  # Tone analysis

def parse_s3_url(url: str) -> Tuple[str, str]:
    """Extract bucket and key from S3 URL."""
    if not url.startswith('s3://') and not url.startswith('https://'):
        raise ValueError("Invalid S3 URL format")
    
    if url.startswith('s3://'):
        parts = url[5:].split('/', 1)
    else:
        # Handle https://bucket.s3.region.amazonaws.com/key format
        domain = url.split('/')[2]
        bucket = domain.split('.')[0]
        key = '/'.join(url.split('/')[3:])
        return bucket, key
    
    if len(parts) != 2:
        raise ValueError("Invalid S3 URL format")
    return parts[0], parts[1]

def count_filler_words(text: str) -> Dict[str, Any]:
    """Count filler words in text."""
    filler_patterns = {
        'um': r'\b(um+|uhm+)\b',
        'uh': r'\b(uh+)\b',
        'like': r'\b(like)\b',
        'you know': r'\b(you\s+know)\b',
        'actually': r'\b(actually)\b',
        'basically': r'\b(basically)\b',
        'well': r'\b(well)\b',
        'right': r'\b(right)\b',
        'sort of': r'\b(sort\s+of)\b',
        'kind of': r'\b(kind\s+of)\b'
    }
    
    counts = {}
    total = 0
    for word, pattern in filler_patterns.items():
        count = len(re.findall(pattern, text.lower()))
        if count > 0:
            counts[word] = count
            total += count
    
    return {
        'total': total,
        'per_filler': counts
    }

def calculate_pace(text: str, duration_seconds: float) -> float:
    """Calculate words per minute."""
    word_count = len(text.split())
    minutes = duration_seconds / 60
    return round(word_count / minutes, 1) if minutes > 0 else 0

def analyze_tone(text: str) -> Dict[str, Any]:
    """Analyze emotional tone using AWS Comprehend."""
    try:
        response = comprehend.detect_sentiment(Text=text, LanguageCode='en')
        return {
            'classification': response['Sentiment'],
            'raw': {
                'POSITIVE': response['SentimentScore']['Positive'],
                'NEGATIVE': response['SentimentScore']['Negative'],
                'NEUTRAL': response['SentimentScore']['Neutral'],
                'MIXED': response['SentimentScore']['Mixed']
            }
        }
    except Exception as e:
        return {'classification': 'UNKNOWN', 'raw': {}, 'error': str(e)}

def analyze_clarity(text: str) -> Dict[str, Any]:
    """Analyze speech clarity based on sentence structure and word usage."""
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    # Average sentence length
    avg_length = sum(len(s.split()) for s in sentences) / len(sentences) if sentences else 0
    
    # Complex transitions (could be expanded)
    complex_transitions = ['furthermore', 'nevertheless', 'consequently', 'therefore', 'moreover']
    complex_count = sum(1 for t in complex_transitions if t in text.lower())
    
    # Calculate clarity score (0-100)
    length_score = 100 - abs(15 - avg_length) * 2  # Optimal length ~15 words
    transition_penalty = complex_count * 5
    base_score = max(0, min(100, length_score - transition_penalty))
    
    return {
        'score': round(base_score, 1),
        'details': {
            'avg_sentence_length': round(avg_length, 1),
            'complex_transition_count': complex_count,
            'score': round(base_score, 1)
        }
    }

def analyze_confidence(text: str, tone_scores: Dict[str, float]) -> Dict[str, Any]:
    """Analyze speaking confidence based on language patterns and tone."""
    hedging_words = ['maybe', 'perhaps', 'kind of', 'sort of', 'i think', 'might', 'possibly']
    assertive_words = ['definitely', 'certainly', 'absolutely', 'clearly', 'strongly']
    
    hedging_count = sum(text.lower().count(word) for word in hedging_words)
    assertive_count = sum(text.lower().count(word) for word in assertive_words)
    
    # Base score from word usage
    word_score = 70  # Start at neutral
    word_score -= hedging_count * 5
    word_score += assertive_count * 5
    
    # Factor in positive/negative tone
    tone_modifier = (tone_scores.get('POSITIVE', 0) - tone_scores.get('NEGATIVE', 0)) * 20
    
    final_score = max(0, min(100, word_score + tone_modifier))
    
    return {
        'score': round(final_score, 1),
        'details': {
            'hedging_count': hedging_count,
            'assertive_count': assertive_count,
            'base_score': word_score,
            'tone_modifier': round(tone_modifier, 1)
        }
    }

def find_filler_examples(text: str, filler_counts: Dict[str, int]) -> List[Dict[str, str]]:
    """Find example sentences containing filler words."""
    examples = []
    sentences = re.split(r'[.!?]+', text)
    sentences = [s.strip() for s in sentences if s.strip()]
    
    for filler in filler_counts.keys():
        pattern = re.compile(r'\b' + re.escape(filler) + r'\b', re.IGNORECASE)
        for sentence in sentences:
            if pattern.search(sentence):
                examples.append({
                    'filler': filler,
                    'example': sentence
                })
                break  # One example per filler word
    
    return examples

# Helper functions
def download_transcript(transcript_url):
    """Download and parse AWS Transcribe results.
    
    Returns:
        dict: Contains transcript text and duration from the audio file
    """
    response = requests.get(transcript_url)
    data = response.json()
    try:
        if not data.get("results") or not data["results"].get("transcripts") or not data["results"]["transcripts"]:
            raise ValueError("No transcript data found in response")
        
        transcript = data["results"]["transcripts"][0]["transcript"]
        
        # Get duration from the last audio segment's end time
        audio_segments = data["results"].get("audio_segments", [])
        if audio_segments:
            duration = float(audio_segments[-1]["end_time"])
        else:
            # Fallback to items if segments not available
            items = data["results"].get("items", [])
            if items:
                # Find last item with end_time (excluding punctuation)
                for item in reversed(items):
                    if "end_time" in item:
                        duration = float(item["end_time"])
                        break
            else:
                duration = 0
        
        return {
            "transcript": transcript,
            "duration": duration
        }
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

        # Download transcript and get duration
        transcription_job = status["TranscriptionJob"]
        transcript_url = transcription_job["Transcript"]["TranscriptFileUri"]
        
        # Get transcript data including duration
        transcript_data = download_transcript(transcript_url)
        transcript_text = transcript_data["transcript"]
        duration_seconds = transcript_data["duration"]
        
        # Fallback if no duration available
        # if duration_seconds <= 0:
        #     word_count = len(transcript_text.split())
        #     duration_seconds = (word_count / 130.0) * 60  # Estimate using average 130 WPM
        #     pass

        # Analyze transcript
        filler_count = count_filler_words(transcript_text)
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
            "recordingUrl": "https://student-app-recordings-2025.s3.us-east-2.amazonaws.com/presentations/audio.m4a?AWSAccessKeyId=AKIA3HPS6GVVHCU57LXA&Signature=ZH2aezFDcwulut0QJpsnQf2sAJM%3D&Expires=1760858242"
        })
    }
    result = lambda_handler(event, None)
    print(json.dumps(result, indent=4))
