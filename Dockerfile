FROM public.ecr.aws/lambda/python:3.11

# Copy requirements file
COPY requirements.txt ${LAMBDA_TASK_ROOT}

# Install the dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy function code and pianoplayer module
COPY lambda_function.py ${LAMBDA_TASK_ROOT}/
COPY pianoplayer/ ${LAMBDA_TASK_ROOT}/pianoplayer/

# Debug: List files to verify everything is in place
RUN ls -la ${LAMBDA_TASK_ROOT}/
RUN ls -la ${LAMBDA_TASK_ROOT}/pianoplayer/

# Explicitly set the command to the Lambda Runtime API handler
CMD ["lambda_function.lambda_handler"]