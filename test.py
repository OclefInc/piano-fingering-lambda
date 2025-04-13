import json
import base64
import os
from lambda_function import lambda_handler

def main():
    # Read the test file name from command line args or use default
    import sys
    test_file = sys.argv[1] if len(sys.argv) > 1 else 'test.musicxml'
    filename = os.path.basename(test_file)

    print(f"Processing {test_file}...")

    # Read a test file
    with open(test_file, 'rb') as f:
        file_content = base64.b64encode(f.read()).decode('utf-8')

    # Create a test event
    test_event = {
        'body': json.dumps({
            'music_file': file_content,
            'hand_size': 'M',
            'file_format': 'musicxml',
            'filename': filename,
            'local_output_dir': 'output'  # Directory where output will be saved
        })
    }

    # Call the lambda handler
    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))

    # Extract and print the output file path if successful
    if result['statusCode'] == 200:
        response_body = json.loads(result['body'])
        if 'output_file' in response_body:
            print(f"\nOutput saved to: {response_body['output_file']}")

if __name__ == "__main__":
    main()