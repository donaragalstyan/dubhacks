import json
import time
import boto3
from typing import List, Dict, Any

# Reuse analysis helpers from analyzePresentation
from .analyzePresentation import (
    parse_s3_url,
    download_transcript,
    count_filler_words,
    calculate_pace,
    analyze_tone,
    analyze_clarity,
    analyze_confidence,
    find_filler_examples,
)

# AWS clients (region should match your S3/transcribe resources)
transcribe = boto3.client("transcribe", region_name="us-east-2")


def check_constraints(transcript: str, metrics: Dict[str, Any], constraints: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluate constraints against calculated metrics.

    Supported constraints (all optional):
    - target_duration_seconds (float), tolerance_seconds (float)
    - max_fillers (int)
    - required_phrases (list[str]) - all must appear
    - forbidden_phrases (list[str]) - none should appear
    - pace_range (dict with min and max wpm)
    - min_confidence_score (0-100)
    """
    violations = []
    respected = True

    # Duration
    if "target_duration_seconds" in constraints:
        target = float(constraints["target_duration_seconds"])
        tol = float(constraints.get("tolerance_seconds", 3))
        dur = metrics.get("estimated_duration_seconds") or 0
        if abs(dur - target) > tol:
            respected = False
            violations.append({"field": "duration", "expected": f"{target}±{tol}s", "actual": dur, "suggestion": "Adjust speech length to match the target duration."})

    # Max fillers
    if "max_fillers" in constraints:
        maxf = int(constraints["max_fillers"])
        total_fillers = metrics.get("filler_words", {}).get("total", 0)
        if total_fillers > maxf:
            respected = False
            violations.append({"field": "fillers", "expected": f"<= {maxf}", "actual": total_fillers, "suggestion": "Practice reducing filler words; see examples in feedback."})

    # Required phrases
    req = constraints.get("required_phrases") or []
    missing = []
    lower = transcript.lower()
    for phrase in req:
        if phrase.lower() not in lower:
            missing.append(phrase)
    if missing:
        respected = False
        violations.append({"field": "required_phrases", "missing": missing, "suggestion": "Include the required phrases in the response."})

    # Forbidden phrases
    forbid = constraints.get("forbidden_phrases") or []
    present = []
    for phrase in forbid:
        if phrase.lower() in lower:
            present.append(phrase)
    if present:
        respected = False
        violations.append({"field": "forbidden_phrases", "present": present, "suggestion": "Avoid using forbidden phrases."})

    # Pace
    if "pace_range" in constraints:
        pr = constraints["pace_range"]
        wpm = metrics.get("pace_wpm")
        if wpm is not None:
            minw = pr.get("min", 100)
            maxw = pr.get("max", 160)
            if wpm < minw or wpm > maxw:
                respected = False
                violations.append({"field": "pace", "expected": f"{minw}-{maxw} wpm", "actual": wpm, "suggestion": "Adjust pace to fall within the required range."})

    # Confidence
    if "min_confidence_score" in constraints:
        minc = float(constraints["min_confidence_score"])
        conf = metrics.get("confidence", {}).get("score", 0)
        if conf < minc:
            respected = False
            violations.append({"field": "confidence", "expected": f">= {minc}", "actual": conf, "suggestion": "Reduce uncertainty markers and use stronger statements."})

    return {"respected": respected, "violations": violations}


def lambda_handler(event, context):
    try:
        # Get the body, handling both string and dict cases
        body = event.get("body", {})
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except json.JSONDecodeError:
                return {
                    "statusCode": 400,
                    "body": json.dumps({"message": "Invalid JSON in request body"})
                }
        
        # Extract recording URL and constraints with proper error handling
        if not isinstance(body, dict):
            return {
                "statusCode": 400,
                "body": json.dumps({"message": "Request body must be an object"})
            }
            
        recording_url = body.get("recordingUrl")
        constraints = body.get("constraints", {})

        if not recording_url:
            return {"statusCode": 400, "body": json.dumps({"message": "recordingUrl missing"})}

        # Extract bucket/key and start Transcribe job
        try:
            bucket_name, object_key = parse_s3_url(recording_url)
        except Exception as e:
            return {"statusCode": 400, "body": json.dumps({"message": "Invalid S3 URL format", "error": str(e)})}

        s3_uri = f"s3://{bucket_name}/{object_key}"
        job_name = f"exercise-transcription-{int(time.time())}"
        transcribe.start_transcription_job(
            TranscriptionJobName=job_name,
            Media={"MediaFileUri": s3_uri},
            MediaFormat=object_key.split('.')[-1],
            LanguageCode="en-US"
        )

        # Wait for job
        while True:
            status = transcribe.get_transcription_job(TranscriptionJobName=job_name)
            job_status = status["TranscriptionJob"]["TranscriptionJobStatus"]
            if job_status in ["COMPLETED", "FAILED"]:
                break
            time.sleep(2)

        if job_status == "FAILED":
            return {"statusCode": 500, "body": json.dumps({"message": "Transcription failed"})}

        transcript_url = status["TranscriptionJob"]["Transcript"]["TranscriptFileUri"]
        transcript_text = download_transcript(transcript_url)

        # Reuse the same analysis pipeline
        filler_info = count_filler_words(transcript_text)
        # Estimate duration if not provided
        duration_seconds = body.get("durationSeconds") or body.get("duration") or None
        try:
            duration_seconds = float(duration_seconds) if duration_seconds else None
        except Exception:
            duration_seconds = None

        word_count = len(transcript_text.split())
        if not duration_seconds or duration_seconds <= 0:
            estimated_wpm = 150.0
            duration_seconds = (word_count / estimated_wpm) * 60

        pace = calculate_pace(transcript_text, duration_seconds)
        tone_info = analyze_tone(transcript_text)
        clarity_info = analyze_clarity(transcript_text)

    # Normalize tone_info to always be a dict
        if isinstance(tone_info, str):
            tone_info = {"classification": tone_info, "raw": {}}

        confidence_info = analyze_confidence(transcript_text, tone_info.get("raw", {}))

        metrics = {
            "tone": tone_info,
            "pace_wpm": pace,
            "word_count": word_count,
            "estimated_duration_seconds": round(duration_seconds, 1) if duration_seconds else None,
            "filler_words": filler_info,
            "clarity": clarity_info,
            "confidence": confidence_info,
        }

        # Check constraints
        constraint_result = check_constraints(transcript_text, metrics, constraints)

        # Suggestions: map violations to action items
        suggestions = []
        for v in constraint_result["violations"]:
            suggestions.append(v.get("suggestion"))

        feedback = {"metrics": metrics, "constraint_result": constraint_result, "suggestions": suggestions}

        return {"statusCode": 200, "body": json.dumps({"recordingUrl": recording_url, "feedback": feedback})}

    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"message": "Analysis failed", "error": str(e)})}


if __name__ == "__main__":
    # Example event for local testing
    event = {
        "body": json.dumps({
            "recordingUrl": "https://student-app-recordings-2025.s3.us-east-2.amazonaws.com/presentations/test.wav",
            "constraints": {
                "target_duration_seconds": 20,
                "tolerance_seconds": 5,
                "max_fillers": 3,
                "required_phrases": ["tacos", "health"],
                "forbidden_phrases": ["um"],
                "pace_range": {"min": 100, "max": 160},
                "min_confidence_score": 50
            }
        })
    }
    result = lambda_handler(event, None)
    print(json.dumps(result, indent=4))
