# Final integrated Flask API for HackRx requirements

from flask import Flask, request, jsonify
from sentence_transformers import SentenceTransformer
import os
import requests
from dotenv import load_dotenv
import pdfplumber
from werkzeug.utils import secure_filename
import re
import json as pyjson
import numpy as np
import hashlib
import urllib.request
from urllib.parse import urlparse

load_dotenv()

app = Flask(__name__)
model = SentenceTransformer('all-MiniLM-L6-v2')

# Helper: cosine similarity

def cosine_similarity(a, b):
    a = np.array(a)
    b = np.array(b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

# Helper: call Together.ai

def call_together_api(prompt, model="meta-llama/Llama-3-8b-chat-hf", max_tokens=120, temperature=0.7):
    api_key = os.getenv("TOGETHER_API_KEY")
    if not api_key:
        return {"error": "TOGETHER_API_KEY not set"}
    url = "https://api.together.xyz/v1/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "model": model,
        "prompt": prompt,
        "max_tokens": max_tokens,
        "temperature": temperature
    }
    response = requests.post(url, headers=headers, json=data)
    try:
        return response.json()
    except Exception as e:
        return {"error": str(e)}

# Main required HackRx route

@app.route('/hackrx/run', methods=['POST'])
def hackrx_run():
    # Step 0: Auth check
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return jsonify({"error": "Unauthorized"}), 401

    api_key = auth_header.split(" ")[1]
    expected_api_key = os.getenv("HACKRX_API_KEY")
    if api_key != expected_api_key:
        return jsonify({"error": "Invalid API key"}), 403

    # Step 1: Input validation
    data = request.get_json()
    file_url = data.get('documents')
    questions = data.get('questions', [])

    if not file_url or not questions:
        return jsonify({'error': 'Missing "documents" or "questions"'}), 400

    # Step 2: Download file
    try:
        parsed_url = urlparse(file_url)
        filename = os.path.basename(parsed_url.path)
        filename = secure_filename(filename or "downloaded.pdf")
        temp_path = os.path.join('uploads', filename)
        os.makedirs("uploads", exist_ok=True)
        urllib.request.urlretrieve(file_url, temp_path)
    except Exception as e:
        return jsonify({'error': f'File download failed: {str(e)}'}), 500

    # Step 3: Extract text (PDF only)
    try:
        text = ""
        if filename.lower().endswith('.pdf'):
            with pdfplumber.open(temp_path) as pdf:
                for page in pdf.pages:
                    text += page.extract_text() or ""
        else:
            return jsonify({'error': 'Only PDF supported for /hackrx/run'}), 400
        os.remove(temp_path)
    except Exception as e:
        return jsonify({'error': f'Text extraction failed: {str(e)}'}), 500

    # Step 4: Chunk and embed
    chunk_size = 300
    overlap = 50
    words = text.split()
    chunks = []
    i = 0
    while i < len(words):
        chunk = words[i:i + chunk_size]
        chunks.append(' '.join(chunk))
        i += chunk_size - overlap
    embeddings = model.encode(chunks).tolist()

    # Step 5: Answer each question using LLM
    responses = []
    for question in questions:
        query_embedding = model.encode([question])[0]
        similarities = [cosine_similarity(query_embedding, emb) for emb in embeddings]
        top_indices = np.argsort(similarities)[-3:][::-1]
        relevant_chunks = [chunks[i] for i in top_indices]

        prompt = f"Based on the following insurance policy clauses, answer the user question.\n\n"
        prompt += f"Question: \"{question}\"\n\nRelevant Clauses:\n"
        for j, chunk in enumerate(relevant_chunks, 1):
            prompt += f"{j}. {chunk}\n"
        prompt += "\nReturn a short, clear answer in plain text."

        result = call_together_api(prompt, model="meta-llama/Llama-3-8b-chat-hf", max_tokens=120, temperature=0)
        answer = result.get('choices', [{}])[0].get('text', '').strip()
        responses.append({"question": question, "answer": answer})

    return jsonify({"results": responses})

# Run app locally
if __name__ == '__main__':
    app.run(port=5001)
