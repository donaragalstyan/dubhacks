# streamlit_app.py
import streamlit as st
import requests

st.set_page_config(page_title="Stage Buddy", layout="centered")

st.title("Magic Mirror")

# --- Upload Presentation ---
st.header("Step 1: Upload Presentation")
presentation_file = st.file_uploader("Choose your presentation audio", type=["mp3", "wav", "m4a"])

if presentation_file:
    if st.button("Submit Presentation"):
        with st.spinner("Analyzing..."):
            files = {"file": (presentation_file.name, presentation_file, "audio/mpeg")}
            response = requests.post("http://localhost:8000/upload_presentation", files=files)
            if response.status_code == 200:
                data = response.json()
                st.success("Feedback received!")
                st.subheader("Feedback:")
                st.write(data.get("feedback"))
                st.subheader("Suggested Exercise:")
                st.write(data.get("exercise"))
            else:
                st.error("Failed to get feedback from backend.")

# --- Upload Exercise ---
st.header("Step 2: Upload Exercise Recording")
exercise_file = st.file_uploader("Choose your exercise audio", type=["mp3", "wav", "m4a"], key="exercise")

if exercise_file:
    if st.button("Submit Exercise"):
        with st.spinner("Evaluating..."):
            files = {"file": (exercise_file.name, exercise_file, "audio/mpeg")}
            response = requests.post("http://localhost:8000/upload_exercise", files=files)
            if response.status_code == 200:
                data = response.json()
                st.success("Exercise feedback received!")
                st.subheader("Feedback:")
                st.write(data.get("feedback"))
            else:
                st.error("Failed to get feedback from backend.")

# --- Optional: Audio Playback ---
if presentation_file:
    st.audio(presentation_file)
if exercise_file:
    st.audio(exercise_file)
