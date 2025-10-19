import streamlit as st
import requests
import json

st.set_page_config(page_title="Stage Buddy", layout="centered")

st.title("Magic Mirror")

# Create tabs for different functionalities
presentation_tab, exercise_tab = st.tabs(["🎯 Presentation Analysis", "💪 Exercise Practice"])

with presentation_tab:
    # --- Upload Presentation ---
    st.header("Upload Presentation")
    presentation_file = st.file_uploader("Choose your presentation audio", type=["mp3", "wav", "m4a"], key="presentation_upload")

with exercise_tab:
    # --- Upload Exercise ---
    st.header("Practice Exercise")
    # Select focus area
    focus_area = st.selectbox(
        "What would you like to focus on?",
        ["pace", "fillers", "clarity", "confidence", "tone"],
        format_func=lambda x: {
            "pace": "🏃‍♂️ Speaking Pace",
            "fillers": "🗣️ Filler Words",
            "clarity": "📝 Speech Clarity",
            "confidence": "💪 Confidence",
            "tone": "🎭 Tone"
        }[x]
    )
    
    # Help text based on selected focus
    focus_help = {
        "pace": "Practice maintaining a steady speaking rate between 120-150 words per minute.",
        "fillers": "Work on reducing filler words like 'um', 'uh', 'like', and 'you know'.",
        "clarity": "Focus on clear pronunciation and well-structured sentences.",
        "confidence": "Practice speaking with authority and conviction.",
        "tone": "Work on maintaining appropriate emotional tone for your content."
    }
    st.info(focus_help[focus_area])
    
    # File upload for exercise
    exercise_file = st.file_uploader("Choose your exercise audio", type=["mp3", "wav", "m4a"], key="exercise_upload")

if presentation_file:
    if st.button("Submit Presentation"):
        with st.spinner("Uploading..."):
            # First, upload the file
            files = {"file": (presentation_file.name, presentation_file, "audio/mpeg")}
            upload_response = requests.post("http://localhost:8000/api/upload-recording", files=files)
            if upload_response.status_code == 200:
                upload_data = upload_response.json()
                recording_url = upload_data.get("recordingUrl")
                
                # Then, analyze the recording
                with st.spinner("Analyzing..."):
                    analysis_payload = {"recording_url": recording_url}
                    analysis_response = requests.post(
                        "http://localhost:8000/api/analyze-presentation",
                        json=analysis_payload
                    )
                    
                    if analysis_response.status_code == 200:
                        response_data = analysis_response.json()
                        if isinstance(response_data.get('body'), str):
                            data = json.loads(response_data['body'])
                        else:
                            data = response_data
                            
                        feedback = data.get("feedback", {})
                        
                        st.success("Analysis complete!")
                        
                        st.header("📊 Analysis Results")
                        
                        # Create columns for the metrics
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.subheader("🎭 Tone Analysis")
                            tone = feedback.get('tone')
                            if isinstance(tone, str):
                                st.metric("Overall Tone", tone.upper())
                                if tone.upper() == "POSITIVE":
                                    st.success("🌟 Your tone is confident and engaging!")
                                elif tone.upper() == "NEGATIVE":
                                    st.warning("💡 Consider using more positive language.")
                                elif tone.upper() == "NEUTRAL":
                                    st.info("� Your tone is balanced and professional.")
                                else:
                                    st.info(f"Your tone is {tone}")
                            else:
                                st.warning("Tone analysis not available")
                            
                            st.markdown("---")
                            st.subheader("⏱️ Speech Metrics")
                            pace = feedback.get('pace_wpm')
                            if pace:
                                st.metric("Speaking Pace", f"{pace:.1f} WPM")
                                if 120 <= pace <= 150:
                                    st.success("✨ Great pace! You're in the ideal range.")
                                elif pace < 120:
                                    st.warning("💡 Consider speaking a bit faster for better engagement.")
                                else:
                                    st.warning("💡 Try slowing down slightly for better clarity.")
                        
                        with col2:
                            st.subheader("🗣️ Filler Words")
                            filler_count = feedback.get('filler_words')
                            if isinstance(filler_count, int):
                                st.metric("Total Filler Words", filler_count)
                                if filler_count == 0:
                                    st.success("🌟 Excellent! No filler words detected.")
                                else:
                                    st.warning(f"💡 Detected {filler_count} filler words in your speech.")
                                    st.info("Common filler words to watch for: 'um', 'uh', 'like', 'you know'")
                        
                        # Exercises Section
                        st.header("🎯 Improvement Suggestions")
                        exercises = feedback.get('suggested_exercises', [])
                        if exercises:
                            for exercise in exercises:
                                if isinstance(exercise, str):
                                    st.info(f"💡 {exercise}")
                                else:
                                    st.info(f"💡 {exercise.get('suggestion', '')}")
                        
                        # Transcript Section
                        st.header("📝 Transcript")
                        transcript = feedback.get('transcript')
                        if transcript:
                            st.text_area("Speech Content", transcript, height=150)
                        else:
                            st.warning("No transcript available")
                    else:
                        st.error(f"Analysis failed: {analysis_response.text}")
            else:
                st.error(f"Upload failed: {upload_response.text}")

# --- Audio Playback for Presentation ---
if presentation_file:
    st.subheader("Review Your Recording:")
    st.audio(presentation_file)

# --- Exercise Analysis and Audio Playback ---
if exercise_file:
    if st.button("Start Exercise Analysis", key="exercise_button"):
        with st.spinner("Uploading exercise recording..."):
            # First, upload the file
            files = {"file": (exercise_file.name, exercise_file, "audio/mpeg")}
            st.write("Uploading file...")  # Debug log
            upload_response = requests.post("http://localhost:8000/api/upload-recording", files=files)
            st.write(f"Upload response status: {upload_response.status_code}")  # Debug log
            
            if upload_response.status_code == 200:
                upload_data = upload_response.json()
                st.write(f"Upload response data: {upload_data}")  # Debug log
                recording_url = upload_data.get("recordingUrl")
                st.write(f"Recording URL: {recording_url}")  # Debug log
                
                # Then, analyze the exercise
                with st.spinner(f"Analyzing your {focus_area} exercise..."):
                    # Define constraints based on focus area
                    constraints = {}
                    if focus_area == "pace":
                        constraints = {
                            "pace_range": {"min": 120, "max": 150}
                        }
                    elif focus_area == "fillers":
                        constraints = {
                            "max_fillers": 3
                        }
                    elif focus_area == "clarity":
                        constraints = {
                            "min_clarity_score": 70
                        }
                    elif focus_area == "confidence":
                        constraints = {
                            "min_confidence_score": 70
                        }
                    elif focus_area == "tone":
                        constraints = {
                            "required_tones": ["POSITIVE", "PROFESSIONAL"]
                        }

                    # Format the request payload
                    analysis_payload = {
                        "recording_url": recording_url,
                        "focus_area": focus_area,  # This comes from the selectbox above
                        "constraints": constraints
                    }
                    st.write("Prepared analysis request:")
                    st.write(f"Focus area: {focus_area}")
                    st.write(f"Full payload: {analysis_payload}")  # Debug log
                    st.write("Note: Sending request with properly formatted data...")  # Debug log
                    
                    if not recording_url:
                        st.error("No recording URL available")
                        st.stop()

                    try:
                        st.write("Sending analysis request...")  # Debug log
                        analysis_response = requests.post(
                            "http://localhost:8000/api/analyze-exercise",
                            json=analysis_payload,
                            headers={"Content-Type": "application/json"}
                        )
                        st.write(f"Analysis response status: {analysis_response.status_code}")  # Debug log
                        st.write(f"Analysis response text: {analysis_response.text}")  # Debug log
                    except Exception as e:
                        st.error(f"Analysis request failed: {str(e)}")
                        st.stop()
                    
                    if analysis_response.status_code == 200:
                        data = analysis_response.json()
                        feedback = data.get("feedback", {})
                        analysis = feedback.get("analysis", {})
                        
                        st.success("Exercise analysis complete!")
                        
                        # Main header for exercise results
                        st.header("🎯 Exercise Results")
                        
                        # Display basic metrics in columns
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.subheader("📊 Performance Metrics")
                            word_count = feedback.get("word_count", 0)
                            duration = feedback.get("duration_seconds", 0)
                            st.metric("Words Spoken", word_count)
                            st.metric("Duration", f"{duration:.1f}s")
                        
                        with col2:
                            st.subheader("� Target Status")
                            analysis = feedback.get("analysis", {})
                            status = analysis.get("status", "unknown")
                            
                            if status == "on_target":
                                st.success("✨ Target Achieved!")
                            elif status == "needs_work":
                                st.warning("� Keep Practicing")
                            
                            # Display metrics based on focus area
                            if focus_area == "pace":
                                pace = analysis.get("pace_wpm")
                                target_range = analysis.get("target_range", "120-150 WPM")
                                st.metric("Speaking Pace", f"{pace:.1f} WPM")
                                st.info(f"Target Range: {target_range}")
                            
                            elif focus_area == "fillers":
                                filler_count = analysis.get("filler_count", 0)
                                target_max = analysis.get("target_max", 3)
                                st.metric("Filler Words", filler_count)
                                st.info(f"Target: Maximum {target_max} filler words")
                                
                                # Show filler word breakdown if any found
                                per_filler = analysis.get("per_filler", {})
                                if per_filler:
                                    with st.expander("See filler word details"):
                                        for word, count in per_filler.items():
                                            st.text(f"'{word}': {count} times")
                            
                            elif focus_area == "clarity":
                                clarity_score = analysis.get("clarity_score", 0)
                                target_min = analysis.get("target_min", 70)
                                st.metric("Clarity Score", f"{clarity_score}/100")
                                st.info(f"Target: Minimum score of {target_min}")
                            
                            elif focus_area == "confidence":
                                confidence_score = analysis.get("confidence_score", 0)
                                target_min = analysis.get("target_min", 70)
                                st.metric("Confidence Score", f"{confidence_score}/100")
                                st.info(f"Target: Minimum score of {target_min}")
                            
                            elif focus_area == "tone":
                                tone = analysis.get("tone_classification", "NEUTRAL")
                                target_tones = analysis.get("target_tones", ["POSITIVE"])
                                st.metric("Primary Tone", tone.title())
                                st.info(f"Target: {', '.join(t.title() for t in target_tones)}")
                                
                                # Show tone breakdown
                                tone_scores = analysis.get("tone_scores", {})
                                if tone_scores:
                                    with st.expander("See tone breakdown"):
                                        for tone, score in tone_scores.items():
                                            st.progress(score, text=f"{tone.title()}: {score*100:.1f}%")

                        # Display feedback and suggestions
                        st.subheader("💡 Feedback")
                        feedback_messages = analysis.get("feedback", [])
                        for message in feedback_messages:
                            if "great" in message.lower() or "excellent" in message.lower():
                                st.success(message)
                            else:
                                st.info(message)
                                
                        # Show transcript
                        st.subheader("📝 Transcript")
                        transcript = feedback.get("transcript", "No transcript available")
                        st.text_area("Your Speech", transcript, height=100, disabled=True)
                    else:
                        st.error(f"Analysis failed: {analysis_response.text}")
            else:
                st.error(f"Upload failed: {upload_response.text}")
    
    st.subheader("Review Your Exercise:")
    st.audio(exercise_file)

# Add a health check indicator
try:
    health_response = requests.get("http://localhost:8000/api/health")
    if health_response.status_code == 200:
        st.sidebar.success("Backend API: Connected")
    else:
        st.sidebar.error("Backend API: Disconnected")
except requests.exceptions.ConnectionError:
    st.sidebar.error("Backend API: Disconnected")
