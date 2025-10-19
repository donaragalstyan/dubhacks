import json
import uploadRecording

event = {
    "body": json.dumps({
        "fileName": "test.mp3",
        "fileType": "audio/mpeg",
        "fileContent": "<base64 string here>"  # replace with a real base64 audio
    })
}

result = uploadRecording.lambda_handler(event, None)
print(result)
