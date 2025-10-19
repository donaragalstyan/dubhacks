# streamlit_app.py
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
                            if tone:
                                st.metric("Overall Tone", tone.title())
                                if tone == "POSITIVE":
                                    st.success("🌟 Your tone is confident and engaging!")
                                elif tone == "NEGATIVE":
                                    st.warning("💡 Consider using more positive language.")
                                elif tone == "NEUTRAL":
                                    st.info("📝 Your tone is balanced and professional.")
                            
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
            upload_response = requests.post("http://localhost:8000/api/upload-recording", files=files)
            if upload_response.status_code == 200:
                upload_data = upload_response.json()
                recording_url = upload_data.get("recordingUrl")
                
                # Then, analyze the exercise
                with st.spinner(f"Analyzing your {focus_area} exercise..."):
                    analysis_payload = {
                        "recording_url": recording_url,
                        "focus_area": focus_area
                    }
                    analysis_response = requests.post(
                        "http://localhost:8000/api/analyze-exercise",
                        json=analysis_payload
                    )
                    
                    if analysis_response.status_code == 200:
                        data = analysis_response.json()
                        feedback = data.get("feedback", {})
                        
                        st.success("Exercise analysis complete!")
                        
                        # Display focused feedback based on exercise type
                        st.header("🎯 Exercise Feedback")
                        
                        if focus_area == "pace":
                            pace = feedback.get("pace_wpm")
                            if pace:
                                st.metric("Your Speaking Pace", f"{pace:.1f} WPM")
                                if 120 <= pace <= 150:
                                    st.success("🌟 Perfect pace! Keep it up!")
                                elif pace < 120:
                                    st.warning("💡 Try speaking a bit faster. Aim for 120-150 WPM.")
                                else:
                                    st.warning("💡 Try slowing down a bit. Aim for 120-150 WPM.")
                        
                        elif focus_area == "fillers":
                            filler_count = feedback.get("filler_words", {}).get("total", 0)
                            st.metric("Filler Words Used", filler_count)
                            if filler_count == 0:
                                st.success("🌟 Excellent! No filler words detected.")
                            else:
                                st.warning(f"Found {filler_count} filler words. Keep practicing!")
                                filler_details = feedback.get("filler_words", {}).get("per_filler", {})
                                for word, count in filler_details.items():
                                    if count > 0:
                                        st.write(f"- '{word}': {count} times")
                        
                        elif focus_area == "clarity":
                            clarity_score = feedback.get("clarity", {}).get("score", 0)
                            st.metric("Clarity Score", f"{clarity_score}/100")
                            if clarity_score >= 90:
                                st.success("🌟 Excellent clarity!")
                            elif clarity_score >= 70:
                                st.info("💡 Good clarity. Keep practicing!")
                            else:
                                st.warning("💡 Focus on speaking more clearly.")
                        
                        elif focus_area == "confidence":
                            confidence_score = feedback.get("confidence", {}).get("score", 0)
                            st.metric("Confidence Score", f"{confidence_score}/100")
                            if confidence_score >= 90:
                                st.success("🌟 Very confident delivery!")
                            else:
                                st.info("💡 Try speaking with more authority.")
                        
                        elif focus_area == "tone":
                            tone_data = feedback.get("tone", {})
                            if tone_data:
                                dominant_tone = max(tone_data.get("raw", {}).items(), key=lambda x: x[1])[0]
                                st.metric("Primary Tone", dominant_tone.title())
                                st.write("Emotional Distribution:")
                                for emotion, score in tone_data.get("raw", {}).items():
                                    st.progress(score, text=f"{emotion}: {score*100:.1f}%")
                        
                        # Show exercise-specific suggestions
                        if feedback.get("suggested_exercises"):
                            st.subheader("🎯 Suggested Improvements")
                            for exercise in feedback["suggested_exercises"]:
                                st.info(f"💡 {exercise.get('suggestion', '')}")
                        
                        # Show transcript
                        st.subheader("📝 Exercise Transcript")
                        transcript = feedback.get("transcript")
                        if transcript:
                            st.text_area("What you said", transcript, height=100)
                        else:
                            st.warning("No transcript available")
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
