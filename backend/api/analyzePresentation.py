import json
import boto3
import time
import requests
import re
from statistics import mean
import nltk
from nltk.tokenize import sent_tokenize
from collections import Counter

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

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
    """Return total count and per-filler counts (word boundaries).

    Uses simple whole-word matching to avoid counting substrings.
    """
    fillers = ["um", "uh", "like", "you know", "so", "actually"]
    text_lower = text.lower()
    counts = {}
    total = 0
    for f in fillers:
        # word boundary match; escape spaces in phrases
        pattern = r"\\b" + re.escape(f) + r"\\b"
        c = len(re.findall(pattern, text_lower))
        counts[f] = c
        total += c
    return {"total": total, "per_filler": counts}

def calculate_pace(text, duration_seconds):
    word_count = len(text.split())
    if duration_seconds and duration_seconds > 0:
        wpm = (word_count / duration_seconds) * 60
    else:
        # fallback estimate: assume average speaking rate 150 wpm
        # derive duration from word count
        wpm = 150.0
        duration_seconds = (word_count / wpm) * 60
    return round((word_count / duration_seconds) * 60, 1)

def analyze_tone(text):
    # Return both raw sentiment scores and an objective label.
    response = comprehend.detect_sentiment(Text=text, LanguageCode="en")
    scores = response.get("SentimentScore", {})
    # Determine objective/subjective label: if neutral dominates, call it 'objective'
    neutral = scores.get("Neutral", 0)
    positive = scores.get("Positive", 0)
    negative = scores.get("Negative", 0)
    mixed = scores.get("Mixed", 0)

    # classification avoids value judgment words when neutral is high
    if neutral >= 0.60:
        objective_label = "objective"
    elif max(positive, negative, mixed) - neutral > 0.15:
        # significantly non-neutral
        objective_label = "subjective"
    else:
        objective_label = "balanced"

    return {"raw": scores, "classification": objective_label}


def analyze_clarity(text):
    """Analyze speech clarity based on sentence structure, length, and vocabulary."""
    sentences = sent_tokenize(text)
    
    # Analyze sentence length (too long = harder to follow)
    lengths = [len(s.split()) for s in sentences]
    avg_length = mean(lengths) if lengths else 0
    
    # Look for complex sentence markers
    complex_markers = ["however", "although", "nevertheless", "furthermore", "meanwhile"]
    complex_count = sum(text.lower().count(m) for m in complex_markers)
    
    # Calculate clarity metrics
    clarity_score = 100
    if avg_length > 25:  # Penalize very long sentences
        clarity_score -= min(30, (avg_length - 25) * 2)
    if complex_count > len(sentences) / 3:  # Penalize excessive complex transitions
        clarity_score -= min(20, complex_count * 5)
        
    # Identify unclear segments
    unclear_segments = []
    for s in sentences:
        if len(s.split()) > 30 or any(m in s.lower() for m in complex_markers):
            unclear_segments.append(s.strip())
    
    return {
        "score": max(0, min(100, clarity_score)),
        "avg_sentence_length": round(avg_length, 1),
        "complex_transition_count": complex_count,
        "unclear_segments": unclear_segments[:3]  # Top 3 examples
    }

def analyze_confidence(text, tone_scores):
    """Analyze speaking confidence based on language patterns and tone."""
    # Confidence markers (positive) and uncertainty markers (negative)
    confidence_markers = ["definitely", "certainly", "clearly", "strongly", "confident", "sure"]
    uncertainty_markers = ["maybe", "perhaps", "kind of", "sort of", "i think", "i guess", "possibly"]
    
    text_lower = text.lower()
    
    # Count markers
    confident_count = sum(text_lower.count(m) for m in confidence_markers)
    uncertain_count = sum(text_lower.count(m) for m in uncertainty_markers)
    
    # Calculate base confidence score
    confidence_score = 100
    
    # Adjust for uncertainty markers
    if uncertain_count > 0:
        confidence_score -= min(40, uncertain_count * 10)
    
    # Boost for confidence markers
    if confident_count > 0:
        confidence_score += min(20, confident_count * 5)
    
    # Factor in positive/negative tone
    positive_score = tone_scores.get("Positive", 0)
    negative_score = tone_scores.get("Negative", 0)
    confidence_score += (positive_score - negative_score) * 20
    
    # Find examples of uncertain phrases
    uncertain_examples = []
    sentences = sent_tokenize(text)
    for s in sentences:
        s_lower = s.lower()
        if any(m in s_lower for m in uncertainty_markers):
            uncertain_examples.append(s.strip())
            if len(uncertain_examples) >= 3:
                break
    
    return {
        "score": max(0, min(100, confidence_score)),
        "confidence_markers": confident_count,
        "uncertainty_markers": uncertain_count,
        "uncertain_examples": uncertain_examples
    }

def find_filler_examples(text, fillers, max_examples=3):
    """Find examples of sentences containing filler words."""
    sentences = sent_tokenize(text)
    examples = []
    for s in sentences:
        s_lower = s.lower()
        for f in fillers:
            pattern = r"\\b" + re.escape(f) + r"\\b"
            if re.search(pattern, s_lower):
                snippet = s.strip()
                if snippet and snippet not in examples:
                    examples.append(snippet)
                break
        if len(examples) >= max_examples:
            break
    return examples


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
        filler_info = count_filler_words(transcript_text)
        # Accept optional duration from request body (seconds); otherwise estimate
        duration_seconds = body.get("durationSeconds") or body.get("duration") or None
        try:
            duration_seconds = float(duration_seconds) if duration_seconds else None
        except Exception:
            duration_seconds = None

        # if no duration provided, estimate using 150 wpm average
        word_count = len(transcript_text.split())
        if not duration_seconds or duration_seconds <= 0:
            # estimate duration in seconds from word count and average WPM
            estimated_wpm = 150.0
            duration_seconds = (word_count / estimated_wpm) * 60

        pace = calculate_pace(transcript_text, duration_seconds)
        tone_info = analyze_tone(transcript_text)
        clarity_info = analyze_clarity(transcript_text)
        confidence_info = analyze_confidence(transcript_text, tone_info.get("raw", {}))

        # Build precise feedback
        fillers_list = [f for f, c in filler_info["per_filler"].items() if c > 0]
        filler_examples = find_filler_examples(transcript_text, fillers_list or ["um", "uh", "like"], max_examples=4)

        exercises = []
        # targeted suggestions
        if filler_info["total"] > 0:
            exercises.append({
                "issue": "filler_words",
                "total": filler_info["total"],
                "per_filler": filler_info["per_filler"],
                "suggestion": "Record short answers and edit out fillers; practice pausing for 1-2 seconds before replying.",
                "examples": filler_examples,
            })

        # pacing guidance
        if pace < 100:
            exercises.append({"issue": "pace", "wpm": pace, "suggestion": "Try increasing pace slightly and use deliberate phrasing to keep listener engagement."})
        elif pace > 160:
            exercises.append({"issue": "pace", "wpm": pace, "suggestion": "Practice speaking at a slower pace; add short pauses after key points and breath exercises."})
        else:
            exercises.append({"issue": "pace", "wpm": pace, "suggestion": "Pace is within typical speaking range."})

        # tone guidance uses objective classification
        exercises.append({
            "issue": "tone",
            "classification": tone_info.get("classification"),
            "raw_scores": tone_info.get("raw"),
            "suggestion": "Aim for an objective delivery: focus on clear facts, reduce emotionally charged words if you want neutrality." if tone_info.get("classification") != "objective" else "Tone is predominantly objective; keep using factual language."
        })

        # Add clarity feedback
        if clarity_info["score"] < 80:
            exercises.append({
                "issue": "clarity",
                "score": clarity_info["score"],
                "metrics": {
                    "avg_sentence_length": clarity_info["avg_sentence_length"],
                    "complex_transitions": clarity_info["complex_transition_count"]
                },
                "examples": clarity_info["unclear_segments"],
                "suggestion": "Try breaking down longer sentences into shorter, clearer statements. Aim for one main idea per sentence."
            })

        # Add confidence feedback
        if confidence_info["score"] < 80:
            exercises.append({
                "issue": "confidence",
                "score": confidence_info["score"],
                "metrics": {
                    "confidence_markers": confidence_info["confidence_markers"],
                    "uncertainty_markers": confidence_info["uncertainty_markers"]
                },
                "examples": confidence_info["uncertain_examples"],
                "suggestion": "Replace uncertain phrases ('maybe', 'kind of') with more definitive statements. Practice speaking with authority."
            })

        feedback = {
            "tone": tone_info,
            "pace_wpm": pace,
            "word_count": word_count,
            "estimated_duration_seconds": round(duration_seconds, 1) if duration_seconds else None,
            "filler_words": filler_info,
            "clarity": {
                "score": clarity_info["score"],
                "details": clarity_info
            },
            "confidence": {
                "score": confidence_info["score"],
                "details": confidence_info
            },
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
