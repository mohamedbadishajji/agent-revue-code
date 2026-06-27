import boto3
import json
import os
from dotenv import load_dotenv

load_dotenv()

AWS_REGION = os.getenv("AWS_REGION")
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
MODEL_ID = os.getenv("AWS_BEDROCK_MODEL_ID")


def get_bedrock_client():
    """
    Crée et retourne un client AWS Bedrock
    REVUE-32 : Configurer l'accès aux modèles IA
    """
    return boto3.client(
        service_name="bedrock-runtime",
        region_name=AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY
    )


def invoke_llm(prompt: str, system_prompt: str = None, max_tokens: int = 4096) -> str:
    """
    Envoie un prompt à AWS Bedrock et retourne la réponse
    Gère les erreurs de rate limiting et timeout (Bug 1 et Bug 2)
    """
    client = get_bedrock_client()

    messages = [{"role": "user", "content": prompt}]

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "messages": messages
    }

    if system_prompt:
        body["system"] = system_prompt

    try:
        response = client.invoke_model(
            modelId=MODEL_ID,
            body=json.dumps(body)
        )
        response_body = json.loads(response["body"].read())
        return response_body["content"][0]["text"]

    except boto3.exceptions.Boto3Error as e:
        print(f"⚠️ Rate limit ou timeout : {str(e)}")
        raise

    except Exception as e:
        print(f"❌ Erreur AWS Bedrock : {str(e)}")
        raise