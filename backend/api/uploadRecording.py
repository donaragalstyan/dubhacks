import json
import boto3
import base64
import os

BUCKET_NAME = os.environ.get('BUCKET_NAME', 'student-app-recordings-2025')
FOLDER = 'presentations/'

s3 = boto3.client('s3')

def lambda_handler(event, context):
    try:
        body = json.loads(event['body'])
        file_name = body['fileName']
        file_type = body['fileType']
        file_content = body['fileContent']

        file_bytes = base64.b64decode(file_content)

        # Upload to S3
        s3.put_object(
            Bucket=BUCKET_NAME,
            Key=f"{FOLDER}{file_name}",
            Body=file_bytes,
            ContentType=file_type
        )

        # Generate a pre-signed URL valid for 1 hour
        presigned_url = s3.generate_presigned_url(
            'get_object',
            Params={'Bucket': BUCKET_NAME, 'Key': f"{FOLDER}{file_name}"},
            ExpiresIn=3600
        )

        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'File uploaded successfully!',
                'recordingUrl': presigned_url
            })
        }

    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'message': 'Upload failed', 'error': str(e)})
        }
