import streamlit as st
import requests
import json

st.set_page_config(page_title="Stage Buddy", layout="centered")

# --- GLOBAL STYLING ---
st.markdown("""
    <style>
    .block-container {
        padding-top: 2rem;
        padding-bottom: 2rem;
        max-width: 750px;
        margin: auto;
    }
    </style>
""", unsafe_allow_html=True)

st.title("✨ Magic Mirror")

# --- HEALTH CHECK ---
try:
    health_response = requests.get("http://localhost:8000/api/health", timeout=3)
    if health_response.status_code == 200:
        st.sidebar.success("Backend API: Connected")
    else:
        st.sidebar.warning("Backend API: Unstable")
except requests.exceptions.RequestException:
    st.sidebar.error("Backend API: Disconnected")

# --- TABS ---
presentation_tab, exercise_tab = st.tabs(["🎯 Presentation Analysis", "💪 Exercise Practice"])

# --------------------------------------------------------------------
# 🎯 PRESENTATION TAB
# --------------------------------------------------------------------
with presentation_tab:
    st.header("🎤 Presentation Analysis")
    st.caption("Upload your presentation recording to get AI-driven feedback on tone, pace, and filler words.")

    presentation_file = st.file_uploader("🎧 Upload Presentation Audio", type=["mp3", "wav", "m4a"])

    if presentation_file and st.button("Analyze Presentation", use_container_width=True):
        with st.spinner("Uploading your presentation..."):
            files = {"file": (presentation_file.name, presentation_file, "audio/mpeg")}
            upload_response = requests.post("http://localhost:8000/api/upload-recording", files=files)

        if upload_response.status_code == 200:
            upload_data = upload_response.json()
            recording_url = upload_data.get("recordingUrl")

            st.info("🔍 Analyzing presentation... please wait.")
            analysis_payload = {"recording_url": recording_url}
            analysis_response = requests.post(
                "http://localhost:8000/api/analyze-presentation",
                json=analysis_payload
            )

            if analysis_response.status_code == 200:
                response_data = analysis_response.json()
                if isinstance(response_data.get("body"), str):
                    data = json.loads(response_data["body"])
                else:
                    data = response_data

                feedback = data.get("feedback", {})
                st.success("✅ Presentation analysis complete!")

                # --- FEEDBACK SECTIONS ---
                st.divider()
                st.subheader("📊 Analysis Results")

                col1, col2 = st.columns(2)

                # 🎭 Tone
                with col1:
                    tone = feedback.get("tone")
                    if tone:
                        st.metric("Overall Tone", tone.upper())
                        if tone.lower() == "positive":
                            st.success("🌟 Confident and engaging!")
                        elif tone.lower() == "neutral":
                            st.info("Balanced and professional.")
                        elif tone.lower() == "negative":
                            st.warning("💡 Try using more positive language.")
                    else:
                        st.warning("Tone analysis unavailable.")

                    st.markdown("---")
                    pace = feedback.get("pace_wpm")
                    if pace:
                        st.metric("Speaking Pace", f"{pace:.1f} WPM")
                        if 120 <= pace <= 150:
                            st.success("✨ Perfect pace range (120–150 WPM).")
                        elif pace < 120:
                            st.warning("💡 Try speaking a little faster.")
                        else:
                            st.warning("💡 Try slowing down slightly for clarity.")

                # 🗣️ Fillers
                with col2:
                    fillers = feedback.get("filler_words")
                    if fillers is not None:
                        st.metric("Filler Words", fillers)
                        if fillers == 0:
                            st.success("🌟 No filler words detected!")
                        else:
                            st.warning(f"💡 {fillers} filler words found.")
                            st.info("Common fillers: 'um', 'uh', 'like', 'you know'")
                    else:
                        st.info("Filler analysis not available.")

                # 🎯 Suggestions
                st.divider()
                st.subheader("🎯 Improvement Suggestions")
                exercises = feedback.get("suggested_exercises", [])
                if exercises:
                    for ex in exercises:
                        suggestion = ex if isinstance(ex, str) else ex.get("suggestion", "")
                        st.info(f"💡 {suggestion}")
                else:
                    st.info("No improvement suggestions provided.")

                # 📝 Transcript
                st.divider()
                transcript = feedback.get("transcript")
                st.subheader("📝 Transcript")
                if transcript:
                    st.text_area("Your Presentation Text", transcript, height=150)
                else:
                    st.warning("Transcript not available.")
            else:
                st.error("❌ Presentation analysis failed.")
        else:
            st.error("❌ File upload failed.")

    if presentation_file:
        st.subheader("🎧 Review Your Recording")
        st.audio(presentation_file)

# --------------------------------------------------------------------
# 💪 EXERCISE TAB
# --------------------------------------------------------------------
with exercise_tab:
    st.header("💪 Exercise Practice")
    st.caption("Select a focus area and upload a short clip to practice specific speaking skills.")

    focus_area = st.selectbox(
        "🎯 Choose a Focus Area",
        ["pace", "fillers", "clarity", "confidence", "tone"],
        format_func=lambda x: {
            "pace": "🏃‍♂️ Speaking Pace",
            "fillers": "🗣️ Filler Words",
            "clarity": "📝 Clarity",
            "confidence": "💪 Confidence",
            "tone": "🎭 Tone"
        }[x],
    )

    focus_help = {
        "pace": "Maintain a speaking rate between 120–150 words per minute.",
        "fillers": "Reduce 'um', 'uh', and similar filler words.",
        "clarity": "Focus on clear articulation and structure.",
        "confidence": "Speak with steady tone and conviction.",
        "tone": "Maintain emotionally appropriate tone for your message."
    }
    st.info(focus_help[focus_area])

    exercise_file = st.file_uploader("🎧 Upload Exercise Audio", type=["mp3", "wav", "m4a"])

    if exercise_file and st.button("Start Exercise Analysis", use_container_width=True):
        with st.spinner("Uploading exercise recording..."):
            files = {"file": (exercise_file.name, exercise_file, "audio/mpeg")}
            upload_response = requests.post("http://localhost:8000/api/upload-recording", files=files)

        if upload_response.status_code == 200:
            upload_data = upload_response.json()
            recording_url = upload_data.get("recordingUrl")

            constraints = {}
            if focus_area == "pace":
                constraints = {"pace_range": {"min": 120, "max": 150}}
            elif focus_area == "fillers":
                constraints = {"max_fillers": 3}
            elif focus_area == "clarity":
                constraints = {"min_clarity_score": 70}
            elif focus_area == "confidence":
                constraints = {"min_confidence_score": 70}
            elif focus_area == "tone":
                constraints = {"required_tones": ["POSITIVE", "PROFESSIONAL"]}

            with st.spinner("Analyzing your exercise..."):
                analysis_payload = {
                    "recording_url": recording_url,
                    "focus_area": focus_area,
                    "constraints": constraints
                }
                analysis_response = requests.post(
                    "http://localhost:8000/api/analyze-exercise",
                    json=analysis_payload,
                    headers={"Content-Type": "application/json"}
                )

            if analysis_response.status_code == 200:
                data = analysis_response.json()
                feedback = data.get("feedback", {})

                st.success("✅ Exercise analysis complete!")
                st.divider()

                # Main metrics in columns
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("� Exercise Stats")
                    word_count = feedback.get("word_count", 0)
                    duration = feedback.get("duration_seconds", 0)
                    st.metric("Words Spoken", word_count)
                    st.metric("Duration", f"{duration:.1f}s")

                with col2:
                    st.subheader("🎯 Focus Area Results")
                    analysis = feedback.get("analysis", {})
                    status = analysis.get("status", "unknown")
                    
                    # Show achievement status
                    if status == "on_target":
                        st.success("✨ Target Achieved!")
                    elif status == "needs_work":
                        st.warning("💪 Keep Practicing")
                    
                    # Focus-specific metrics
                    if focus_area == "pace":
                        pace = analysis.get("pace_wpm")
                        target_range = analysis.get("target_range", "120-150 WPM")
                        st.metric("Your Pace", f"{pace:.1f} WPM")
                        st.info(f"Target: {target_range}")
                    
                    elif focus_area == "fillers":
                        filler_count = analysis.get("filler_count", 0)
                        target_max = analysis.get("target_max", 3)
                        st.metric("Filler Words", str(filler_count))
                        st.info(f"Target: Max {target_max}")
                        
                        # Show detailed breakdown
                        per_filler = analysis.get("per_filler", {})
                        if per_filler:
                            with st.expander("See filler word details"):
                                for word, count in per_filler.items():
                                    st.text(f"'{word}': {count} times")
                    
                    elif focus_area == "clarity":
                        clarity_score = analysis.get("clarity_score", 0)
                        target_min = analysis.get("target_min", 70)
                        st.metric("Clarity Score", f"{clarity_score:.1f}/100")
                        st.info(f"Target: Min {target_min}")
                    
                    elif focus_area == "confidence":
                        confidence_score = analysis.get("confidence_score", 0)
                        target_min = analysis.get("target_min", 70)
                        st.metric("Confidence", f"{confidence_score:.1f}/100")
                        st.info(f"Target: Min {target_min}")
                    
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

                # Feedback messages section
                st.divider()
                st.subheader("💡 Feedback & Suggestions")
                feedback_messages = analysis.get("feedback", [])
                for message in feedback_messages:
                    if "great" in message.lower() or "excellent" in message.lower():
                        st.success(message)
                    else:
                        st.info(message)

                # --- Constraint results ---
                st.divider()
                constraint_result = feedback.get("constraint_result", {})
                if constraint_result:
                    st.subheader("🎯 Exercise Results")
                    if constraint_result.get("respected", False):
                        st.success("✨ You met all exercise goals!")
                    else:
                        st.warning("Some areas need improvement:")
                        for violation in constraint_result.get("violations", []):
                            st.info(f"💡 {violation.get('suggestion', '')}")

                # --- Transcript ---
                st.divider()
                transcript = feedback.get("transcript")
                st.subheader("📝 Exercise Transcript")
                if transcript:
                    st.text_area("Your Speech", transcript, height=120)
                else:
                    st.info("No transcript available.")
            else:
                st.error(f"❌ Analysis failed: {analysis_response.text}")
        else:
            st.error(f"❌ Upload failed: {upload_response.text}")

    if exercise_file:
        st.subheader("🎧 Review Your Exercise")
        st.audio(exercise_file)
