import json
import os
import tempfile
import base64
import traceback
import argparse
import sys
from pianoplayer.fingering import FingeringGenerator

# Only import boto3 when running in AWS environment
try:
    import boto3
    IN_AWS_LAMBDA = 'AWS_LAMBDA_FUNCTION_NAME' in os.environ
except ImportError:
    IN_AWS_LAMBDA = False

def lambda_handler(event, context):
    """
    AWS Lambda handler function for piano fingering generation
    """
    temp_file_path = None
    local_output_path = None
    try:
        # Check if this is an API Gateway request
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

        hand_size = body.get('hand_size', 'M')
        # Extract beam parameters (used for identifying right and left hand parts)
        rbeam = body.get('rbeam', 0)  # Default to part 0 for right hand
        lbeam = body.get('lbeam', 1)  # Default to part 1 for left hand

        # Decode base64 file content
        file_content = base64.b64decode(body['music_file'])
        file_format = body.get('file_format', 'musicxml')

        # For local testing, determine output filename
        if not IN_AWS_LAMBDA:
            local_output_dir = body.get('local_output_dir', 'output')
            input_filename = body.get('filename', 'output')
            local_output_path = os.path.join(local_output_dir, f"fingered_{input_filename}.musicxml")

            # Create output directory if it doesn't exist
            os.makedirs(local_output_dir, exist_ok=True)

        # Create a temporary file
        with tempfile.NamedTemporaryFile(suffix=f'.{file_format}', delete=False) as temp_file:
            temp_file.write(file_content)
            temp_file_path = temp_file.name

        try:
            # Create a custom args object that will be used internally by pianoplayer
            args = argparse.Namespace()
            args.rbeam = rbeam  # Right hand part index
            args.lbeam = lbeam  # Left hand part index

            # Process the file using FingeringGenerator
            fg = FingeringGenerator(temp_file_path,
                                   hand_size=hand_size,
                                   verbose=True,
                                   args=args)  # Pass the args object
            fingered_file = fg.process()

            if not fingered_file or not os.path.exists(fingered_file):
                return {
                    'statusCode': 500,
                    'body': json.dumps({
                        'error': 'Failed to generate fingered file'
                    })
                }

            # Different behavior based on environment
            if IN_AWS_LAMBDA:
                # AWS Lambda environment - upload to S3
                bucket_name = body.get('bucket_name', os.environ.get('DEFAULT_S3_BUCKET'))
                file_key = body.get('output_key', f"fingered_scores/{os.path.basename(tempfile.mktemp(suffix='.musicxml'))}")

                if not bucket_name:
                    return {
                        'statusCode': 400,
                        'body': json.dumps({'error': 'Missing bucket_name parameter or DEFAULT_S3_BUCKET environment variable'})
                    }

                # Initialize S3 client
                s3 = boto3.client('s3')

                # Upload the generated file to S3
                with open(fingered_file, 'rb') as file_data:
                    s3.upload_fileobj(file_data, bucket_name, file_key)

                # Generate a presigned URL for temporary access
                presigned_url = s3.generate_presigned_url('get_object',
                                                       Params={'Bucket': bucket_name, 'Key': file_key},
                                                       ExpiresIn=3600)

                result = {
                    'statusCode': 200,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'  # For CORS
                    },
                    'body': json.dumps({
                        's3_bucket': bucket_name,
                        's3_key': file_key,
                        'download_url': presigned_url,
                        'message': 'Successfully generated fingerings and saved to S3'
                    })
                }
            else:
                # Local environment - save to file
                with open(fingered_file, 'rb') as f_src:
                    with open(local_output_path, 'wb') as f_dst:
                        f_dst.write(f_src.read())

                result = {
                    'statusCode': 200,
                    'headers': {
                        'Content-Type': 'application/json'
                    },
                    'body': json.dumps({
                        'output_file': local_output_path,
                        'message': f'Successfully generated fingerings and saved to {local_output_path}'
                    })
                }

            # Clean up temporary files
            if temp_file_path and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
            if fingered_file and os.path.exists(fingered_file):
                os.unlink(fingered_file)

            return result

        except Exception as e:
            # Clean up temporary file
            if temp_file_path and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
            raise e

    except Exception as e:
        # Capture the full stack trace for better debugging
        stack_trace = traceback.format_exc()

        # Clean up any temporary files if they still exist
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except:
                pass

        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'traceback': stack_trace
            })
        }