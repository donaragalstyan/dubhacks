# streamlit_app.py
import streamlit as st
import requests
import json

st.set_page_config(page_title="Stage Buddy", layout="centered")

st.title("Magic Mirror")

# --- Upload Presentation ---
st.header("Step 1: Upload Presentation")
presentation_file = st.file_uploader("Choose your presentation audio", type=["mp3", "wav", "m4a"])

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
                        data = analysis_response.json()
                        feedback = data.get("feedback", {})
                        
                        st.success("Analysis complete!")
                        
                        st.subheader("Analysis Results:")
                        st.write(f"🎭 Tone: {feedback.get('tone', 'N/A')}")
                        st.write(f"⏱️ Speaking Pace: {feedback.get('pace_wpm', 'N/A')} words per minute")
                        st.write(f"🗣️ Filler Words Used: {feedback.get('filler_words', 'N/A')}")
                        
                        st.subheader("Suggested Exercises:")
                        exercises = feedback.get('suggested_exercises', [])
                        for exercise in exercises:
                            st.write(f"• {exercise}")
                        
                        st.subheader("Transcript:")
                        st.write(feedback.get('transcript', 'No transcript available'))
                    else:
                        st.error(f"Analysis failed: {analysis_response.text}")
            else:
                st.error(f"Upload failed: {upload_response.text}")

# --- Audio Playback ---
if presentation_file:
    st.subheader("Review Your Recording:")
    st.audio(presentation_file)

# Add a health check indicator
try:
    health_response = requests.get("http://localhost:8000/api/health")
    if health_response.status_code == 200:
        st.sidebar.success("Backend API: Connected")
    else:
        st.sidebar.error("Backend API: Disconnected")
except requests.exceptions.ConnectionError:
    st.sidebar.error("Backend API: Disconnected")
