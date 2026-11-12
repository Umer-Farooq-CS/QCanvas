# Data Directory

This directory contains all data files for the Cirq-RAG-Code-Assistant project.

## 📁 Structure

```
data/
├── datasets/          # Training and evaluation datasets
├── knowledge_base/    # Curated Cirq code snippets and documentation
├── models/            # Pre-trained models and embeddings
└── README.md          # This file
```

## 📊 Datasets

The `datasets/` directory contains:

- **Training datasets** for fine-tuning language models
- **Evaluation datasets** for testing system performance
- **Benchmark datasets** for comparison with other systems
- **Synthetic data** for data augmentation and testing

## 🧠 Knowledge Base

The `knowledge_base/` directory contains:

- **Curated Cirq code snippets** with high-quality implementations
- **Natural language descriptions** for each code example
- **Educational explanations** and step-by-step breakdowns
- **Algorithm templates** for common quantum algorithms
- **Best practices and patterns** for quantum programming

## 🤖 Models

The `models/` directory stores model weights, vector database indices, and local embedding caches. The assistant operates in two modes—cloud-based (AWS Bedrock) and local-based (Ollama)—using the following specific models:

### 🧠 Embedding Models (Semantic Search & RAG Retrieval)
* **Cloud (AWS Bedrock)**: `amazon.nova-2-multimodal-embeddings-v1:0` (1024-dimensional embeddings) – *Default setup for index construction and query embedding*.
* **Local (Sentence-Transformers)**: `BAAI/bge-base-en-v1.5` (768-dimensional) or `sentence-transformers/all-MiniLM-L6-v2` (384-dimensional) – *Used for local embedding generation and FAISS index builds*.

### 🤖 Large Language Models (LLMs) by Agent Role
The system utilizes a multi-agent workflow where different agents serve distinct purposes:

#### **AWS Bedrock (Cloud Mode - Default)**
* **Designer Agent** (generates Google Cirq code from user requirements): `anthropic.claude-sonnet-4-6` (Claude 3.5 Sonnet).
* **Optimizer Agent** (minimizes circuit depth, gate count, and improves fidelity using reinforcement learning/feedback): `anthropic.claude-opus-4-6-v1` (Claude 3 Opus).
* **Validator Agent** (executes circuits locally, parses errors, and guides correction): `anthropic.claude-sonnet-4-6` (Claude 3.5 Sonnet).
* **Educational Agent** (explains code, quantum mechanics concepts, and circuit structure): `anthropic.claude-haiku-4-5-20251001-v1:0` (Claude 3.5 Haiku).

#### **Ollama (Local Mode)**
* **Designer, Optimizer, & Validator Agents**: `qwen2.5-coder:14b-instruct-q4_K_M` (Qwen 2.5 Coder 14B Instruct).
* **Educational Agent**: `llama3.1:8b-instruct-q5_K_M` (Llama 3.1 8B Instruct).

*Note: Model selections and parameters can be configured in [config.json](file:///c:/MyProperty/UNI/QCanvas/QCanvas/Cirq-RAG-Code-Assistant/config/config.json).*

## ⚠️ Important Notes

### Usage Guidelines

- These directories are **automatically created and managed** by the system
- **Do not manually modify** files unless you understand the data format
- The system expects specific file structures and naming conventions

### Git Configuration

- All files in this directory are **ignored by Git** to prevent large files from being committed
- Use **Git LFS** for large model files if needed
- Consider using cloud storage for very large datasets

### Storage Considerations

- **Monitor disk space** as models and datasets can be large
- **Regular cleanup** of temporary files is recommended
- **Backup important models** before major system updates
