import json
import os
import tempfile
import base64
import traceback
import argparse
import boto3
from pianoplayer.fingering import FingeringGenerator

# Check if running in AWS Lambda environment
IN_AWS_LAMBDA = 'AWS_LAMBDA_FUNCTION_NAME' in os.environ

def lambda_handler(event, context):
    """
    AWS Lambda handler function for piano fingering generation
    """
    temp_file_path = None
    input_file_path = None

    try:
        # Handle S3 trigger events
        if 'Records' in event and event['Records'][0].get('eventSource') == 'aws:s3':
            # Get S3 bucket and key information
            record = event['Records'][0]['s3']
            input_bucket = record['bucket']['name']
            input_key = record['object']['key']
            filename = os.path.basename(input_key)
            file_format = os.path.splitext(input_key)[1][1:] or 'musicxml'

            # Output bucket - either use environment variable or append "-output" to input bucket name
            output_bucket = os.environ.get('OUTPUT_S3_BUCKET', f"{input_bucket}-output")
            output_key = f"processed/{filename}"

            print(f"Processing file {input_key} from bucket {input_bucket}")

            # Download the file from S3
            s3 = boto3.client('s3')
            with tempfile.NamedTemporaryFile(suffix=f'.{file_format}', delete=False) as temp_file:
                s3.download_fileobj(input_bucket, input_key, temp_file)
                input_file_path = temp_file.name

            # Process parameters - use default values since this is triggered by S3
            hand_size = 'M'  # Default hand size
            rbeam = 0  # Default right hand part index
            lbeam = 1  # Default left hand part index

        # Handle API Gateway or direct invocation
        else:
            if 'body' in event:
                try:
                    # Parse the request body
                    if isinstance(event['body'], str):
                        body = json.loads(event['body'])
                    else:
                        body = event['body']
                except:
                    return {
                        'statusCode': 400,
                        'body': json.dumps({'error': 'Invalid JSON in request body'})
                    }
            else:
                body = event

            # Validate the required parameters
            if 'music_file' not in body:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'Missing music_file parameter'})
                }

            # Get parameters from request
            hand_size = body.get('hand_size', 'M')
            rbeam = body.get('rbeam', 0)
            lbeam = body.get('lbeam', 1)
            file_format = body.get('file_format', 'musicxml')

            # Decode base64 file content
            file_content = base64.b64decode(body['music_file'])

            # Create a temporary file for input
            with tempfile.NamedTemporaryFile(suffix=f'.{file_format}', delete=False) as temp_file:
                temp_file.write(file_content)
                input_file_path = temp_file.name

            # Set output bucket and key for API Gateway invocation
            output_bucket = body.get('bucket_name', os.environ.get('OUTPUT_S3_BUCKET'))
            output_key = body.get('output_key', f"fingered_scores/{os.path.basename(tempfile.mktemp(suffix='.musicxml'))}")

        # Process the file regardless of invocation source
        try:
            # Create a custom args object for pianoplayer
            args = argparse.Namespace()
            args.rbeam = rbeam  # Right hand part index
            args.lbeam = lbeam  # Left hand part index

            # Process the file using FingeringGenerator
            fg = FingeringGenerator(input_file_path,
                                    hand_size=hand_size,
                                    verbose=True,
                                    args=args)
            fingered_file = fg.process()

            if not fingered_file or not os.path.exists(fingered_file):
                error_msg = "Failed to generate fingered file"
                print(error_msg)
                if 'Records' in event:
                    return {
                        'statusCode': 500,
                        'error': error_msg,
                        'input_bucket': input_bucket,
                        'input_key': input_key
                    }
                else:
                    return {
                        'statusCode': 500,
                        'body': json.dumps({'error': error_msg})
                    }

            # Upload the processed file to S3
            s3 = boto3.client('s3')
            with open(fingered_file, 'rb') as file_data:
                s3.upload_fileobj(file_data, output_bucket, output_key)

            print(f"Successfully processed file and saved to s3://{output_bucket}/{output_key}")

            # For S3 trigger events, just return a simple response
            if 'Records' in event:
                return {
                    'statusCode': 200,
                    'message': 'File processed successfully',
                    'input_bucket': input_bucket,
                    'input_key': input_key,
                    'output_bucket': output_bucket,
                    'output_key': output_key
                }

            # For API Gateway, return a more detailed response with a presigned URL
            presigned_url = s3.generate_presigned_url('get_object',
                                                    Params={'Bucket': output_bucket, 'Key': output_key},
                                                    ExpiresIn=3600)

            result = {
                'statusCode': 200,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'  # For CORS
                },
                'body': json.dumps({
                    's3_bucket': output_bucket,
                    's3_key': output_key,
                    'download_url': presigned_url,
                    'message': 'Successfully generated fingerings and saved to S3'
                })
            }

            return result

        finally:
            # Clean up temporary files
            if input_file_path and os.path.exists(input_file_path):
                os.unlink(input_file_path)
            if fingered_file and os.path.exists(fingered_file):
                os.unlink(fingered_file)

    except Exception as e:
        # Capture the full stack trace for better debugging
        stack_trace = traceback.format_exc()
        error_message = str(e)

        print(f"Error: {error_message}")
        print(f"Traceback: {stack_trace}")

        # Clean up temporary files if they exist
        if input_file_path and os.path.exists(input_file_path):
            try:
                os.unlink(input_file_path)
            except:
                pass

        # Different response format based on invocation type
        if 'Records' in event:
            return {
                'statusCode': 500,
                'error': error_message,
                'traceback': stack_trace,
                'input_bucket': event['Records'][0]['s3']['bucket']['name'],
                'input_key': event['Records'][0]['s3']['object']['key']
            }
        else:
            return {
                'statusCode': 500,
                'body': json.dumps({
                    'error': error_message,
                    'traceback': stack_trace
                })
            }