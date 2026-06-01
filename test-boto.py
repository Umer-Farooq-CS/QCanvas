import boto3
s = boto3.Session(region_name='us-east-1')
client = s.client('bedrock-runtime')
resp = client.invoke_model(
    modelId='amazon.nova-2-multimodal-embeddings-v1:0',
    body=b'{"input":"test"}',
    contentType='application/json',
    inferenceProfileArn='arn:aws:bedrock:us-east-1:776217504506:application-inference-profile/psdvfkbtwajc'
)
print(resp['body'].read().decode())