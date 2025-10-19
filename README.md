# Magic Mirror

## How to Run
In a new venv/conda environment:

1. From the root directory install the required packages:
   ```
   pip install -r backend/requirements.txt
   ```

2. Start the backend server:
   - Open a new terminal in the root directory
   - Run:
     ```
     python backend/run.py
     ```

3. Launch the frontend:
   - Open another terminal and navigate to the frontend subdirectory
   - Run:
     ```
     streamlit run app.py
     ```
   - A window should launch automatically. If it doesn't, terminate the task and run the command again.

4. Using the Application:
   - Once both servers are running, you can upload audio files and explore the page