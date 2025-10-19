import json
import time
import boto3
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add parent directory to Python path to allow absolute imports
api_dir = Path(__file__).resolve().parent
if str(api_dir) not in sys.path:
    sys.path.append(str(api_dir))

# Reuse analysis helpers from analyzePresentation
from analyzePresentation import (
    parse_s3_url,
    download_transcript,
    count_filler_words,
    calculate_pace,
    analyze_tone,
    analyze_clarity,
    analyze_confidence,
    find_filler_examples,
)

# AWS clients
transcribe = boto3.client("transcribe", region_name="us-east-2")
s3 = boto3.client("s3", region_name="us-east-2")

def analyze_pace_exercise(transcript: str, duration_seconds: float, constraints: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze pace-focused exercise."""
    pace = calculate_pace(transcript, duration_seconds)
    pace_range = constraints.get("pace_range", {"min": 120, "max": 150})
    min_pace = pace_range.get("min", 120)
    max_pace = pace_range.get("max", 150)
    
    status = "on_target" if min_pace <= pace <= max_pace else "needs_work"
    feedback = []
    
    if pace < min_pace:
        feedback.append(f"Your pace is a bit slow at {pace} words per minute. Try to speak slightly faster while maintaining clarity.")
        feedback.append("Practice with a timer and try to cover more content in the same time.")
    elif pace > max_pace:
        feedback.append(f"Your pace is a bit fast at {pace} words per minute. Try to slow down for better clarity.")
        feedback.append("Take deliberate pauses between sentences and emphasize key points.")
    else:
        feedback.append(f"Great job! Your pace of {pace} words per minute is within the target range.")
        feedback.append("Keep maintaining this comfortable speaking rate.")
    
    return {
        "pace_wpm": pace,
        "target_range": f"{min_pace}-{max_pace} wpm",
        "status": status,
        "feedback": feedback
    }

def analyze_fillers_exercise(transcript: str, constraints: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze filler words exercise."""
    filler_info = count_filler_words(transcript)
    max_fillers = constraints.get("max_fillers", 3)
    total_fillers = filler_info["total"]
    
    status = "on_target" if total_fillers <= max_fillers else "needs_work"
    feedback = []
    
    if total_fillers == 0:
        feedback.append("Excellent! You didn't use any filler words.")
        feedback.append("Keep up this clean speaking style in your presentations.")
    else:
        feedback.append(f"Found {total_fillers} filler words in your speech.")
        if total_fillers > max_fillers:
            feedback.append(f"Try to reduce filler words to {max_fillers} or fewer.")
            examples = find_filler_examples(transcript, filler_info["per_filler"])
            if examples:
                feedback.append("Here are some examples where you used filler words:")
                for ex in examples[:2]:  # Show just a couple examples
                    feedback.append(f"- Instead of '{ex['example']}', try pausing briefly.")
    
    return {
        "filler_count": total_fillers,
        "target_max": max_fillers,
        "per_filler": filler_info["per_filler"],
        "status": status,
        "feedback": feedback
    }

def analyze_clarity_exercise(transcript: str, constraints: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze clarity exercise."""
    clarity_info = analyze_clarity(transcript)
    min_score = constraints.get("min_clarity_score", 70)
    score = clarity_info["score"]
    
    status = "on_target" if score >= min_score else "needs_work"
    feedback = []
    
    if score >= 90:
        feedback.append(f"Excellent clarity score of {score}! Your speech is very well structured.")
    elif score >= min_score:
        feedback.append(f"Good clarity score of {score}. Your message is generally clear.")
        feedback.append("Consider shorter sentences and simpler transitions to improve further.")
    else:
        feedback.append(f"Your clarity score is {score}, aiming for {min_score}+.")
        feedback.append("Try breaking down complex sentences and using clearer transitions.")
    
    return {
        "clarity_score": score,
        "target_min": min_score,
        "details": clarity_info["details"],
        "status": status,
        "feedback": feedback
    }

def analyze_confidence_exercise(transcript: str, constraints: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze confidence exercise."""
    tone_info = analyze_tone(transcript)
    confidence_info = analyze_confidence(transcript, tone_info.get("raw", {}))
    min_score = constraints.get("min_confidence_score", 70)
    score = confidence_info["score"]
    
    status = "on_target" if score >= min_score else "needs_work"
    feedback = []
    
    if score >= 90:
        feedback.append(f"Excellent confidence level of {score}! Your delivery is very assertive.")
    elif score >= min_score:
        feedback.append(f"Good confidence score of {score}. You're showing good authority.")
        feedback.append("Try using more assertive language to boost confidence further.")
    else:
        feedback.append(f"Your confidence score is {score}, aiming for {min_score}+.")
        feedback.append("Try reducing hedging words and using more definitive statements.")
        if confidence_info["details"]["hedging_count"] > 0:
            feedback.append("Replace phrases like 'kind of' and 'sort of' with more direct language.")
    
    return {
        "confidence_score": score,
        "target_min": min_score,
        "details": confidence_info["details"],
        "status": status,
        "feedback": feedback
    }

def analyze_tone_exercise(transcript: str, constraints: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze tone exercise."""
    tone_info = analyze_tone(transcript)
    target_tones = constraints.get("required_tones", ["POSITIVE"])
    tone_scores = tone_info.get("raw", {})
    primary_tone = max(tone_scores.items(), key=lambda x: x[1])[0] if tone_scores else "NEUTRAL"
    
    status = "on_target" if primary_tone in target_tones else "needs_work"
    feedback = []
    
    feedback.append(f"Your primary tone is {primary_tone.lower()}.")
    if primary_tone in target_tones:
        feedback.append("Great job hitting the target emotional tone!")
    else:
        feedback.append(f"Aim for a more {', '.join(t.lower() for t in target_tones)} tone.")
        if "POSITIVE" in target_tones and tone_scores.get("POSITIVE", 0) < 0.5:
            feedback.append("Try using more optimistic and encouraging language.")
    
    return {
        "tone_classification": primary_tone,
        "target_tones": target_tones,
        "tone_scores": tone_scores,
        "status": status,
        "feedback": feedback
    }

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
        
        # Extract and validate fields
        if not isinstance(body, dict):
            return {
                "statusCode": 400,
                "body": json.dumps({"message": "Request body must be an object"})
            }
            
        recording_url = body.get("recordingUrl")
        if not recording_url:
            return {
                "statusCode": 400,
                "body": json.dumps({"message": "recordingUrl is required"})
            }
        
        focus_area = body.get("focus_area")
        if not focus_area or focus_area not in ["pace", "fillers", "clarity", "confidence", "tone"]:
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "message": "Invalid focus area",
                    "valid_focus_areas": ["pace", "fillers", "clarity", "confidence", "tone"]
                })
            }
        
        constraints = body.get("constraints", {})

        # Start transcription
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

        # Wait for job completion
        while True:
            status = transcribe.get_transcription_job(TranscriptionJobName=job_name)
            job_status = status["TranscriptionJob"]["TranscriptionJobStatus"]
            if job_status in ["COMPLETED", "FAILED"]:
                break
            time.sleep(2)

        if job_status == "FAILED":
            return {"statusCode": 500, "body": json.dumps({"message": "Transcription failed"})}

        # Get transcript and duration from transcription job
        transcription_job = status["TranscriptionJob"]
        transcript_url = transcription_job["Transcript"]["TranscriptFileUri"]
        
        # Download transcript and get duration from audio segments
        transcript_data = download_transcript(transcript_url)
        transcript_text = transcript_data["transcript"]
        duration_seconds = transcript_data["duration"]
        
        # Calculate word count once
        word_count = len(transcript_text.split())
        
        # Validate duration and fallback if needed
        if duration_seconds <= 0:
            duration_seconds = (word_count / 130.0) * 60  # Estimate using average 130 WPM

        # If AWS duration is not available, try duration from request
        if duration_seconds <= 0:
            try:
                duration_seconds = float(body.get("durationSeconds") or body.get("duration", 0))
            except (TypeError, ValueError):
                duration_seconds = 0
        
        # If still no valid duration, estimate from word count
        # Using standard speaking rate of 130 WPM for estimation
        if duration_seconds <= 0:
            duration_seconds = (word_count / 130.0) * 60

        # Analyze based on focus area
        analysis_result = {}
        if focus_area == "pace":
            analysis_result = analyze_pace_exercise(transcript_text, duration_seconds, constraints)
        elif focus_area == "fillers":
            analysis_result = analyze_fillers_exercise(transcript_text, constraints)
        elif focus_area == "clarity":
            analysis_result = analyze_clarity_exercise(transcript_text, constraints)
        elif focus_area == "confidence":
            analysis_result = analyze_confidence_exercise(transcript_text, constraints)
        elif focus_area == "tone":
            analysis_result = analyze_tone_exercise(transcript_text, constraints)
        else:
            return {"statusCode": 400, "body": json.dumps({"message": "Invalid focus area"})}

        # Prepare response
        feedback = {
            "focus_area": focus_area,
            "transcript": transcript_text,
            "word_count": word_count,  # Using the word_count calculated earlier
            "duration_seconds": round(duration_seconds, 1),
            "analysis": analysis_result
        }

        return {
            "statusCode": 200,
            "body": json.dumps({"recordingUrl": recording_url, "feedback": feedback})
        }

    except Exception as e:
        return {"statusCode": 500, "body": json.dumps({"message": "Analysis failed", "error": str(e)})}

if __name__ == "__main__":
    # Test event for local testing
    test_event = {
        "body": json.dumps({
            "recordingUrl": "s3://student-app-recordings-2025/presentations/test.wav",
            "focus_area": "pace",
            "constraints": {
                "pace_range": {"min": 120, "max": 150}
            }
        })
    }
    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=4))
