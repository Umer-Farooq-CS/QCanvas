"""
Educational Agent Module

This module implements the Educational Agent, responsible for providing
explanations, learning materials, and educational content for generated
code and quantum algorithms.
"""

from typing import Dict, Any, Optional, List
import requests
import json
import os

from .base_agent import BaseAgent
from ..rag.retriever import Retriever
from ..tools.analyzer import CircuitAnalyzer
from ..cirq_rag_code_assistant.config import get_config
from ..cirq_rag_code_assistant.config.logging import get_logger
from ..cirq_rag_code_assistant.bedrock_client import get_bedrock_runtime_client
from ..agent_prompts import EDUCATIONAL_SYSTEM

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

logger = get_logger(__name__)


class EducationalAgent(BaseAgent):
    """Provides educational explanations and learning materials."""
    
    PROMPT_LOW = """Explain this quantum code in the simplest way possible for someone who has never seen quantum computing.

CODE:
{code}

ALGORITHM: {algorithm}

Rules:
- Use everyday analogies (coins, boxes, etc.)
- No math symbols or formulas
- Maximum 3-4 short sentences per section
- Avoid all jargon - if you must use a term, explain it like explaining to a child

Format your response EXACTLY like this:

## What This Code Does
[1-2 simple sentences]

## Step by Step
- [simple step 1]
- [simple step 2]
- [simple step 3]

## Key Ideas
- **[Concept]**: [one sentence simple explanation with analogy]
"""

    PROMPT_INTERMEDIATE = """Explain this Google Cirq quantum circuit for someone learning quantum computing.

CODE:
{code}

CIRCUIT ANALYSIS:
{analysis_text}

ALGORITHM: {algorithm}

Rules:
- Define technical terms when first used
- Include what each gate does
- Explain the purpose of each step
- Keep explanations clear but thorough

Format your response EXACTLY like this:

## Overview
[2-3 sentences explaining what this code does and why]

## Step-by-Step Explanation
1. **[Code line]**: [explanation of what it does and why]
2. **[Code line]**: [explanation]
[continue for each important line]

## Quantum Concepts Used
- **[Concept name]**: [clear explanation, 2-3 sentences]

## Code Structure
[Brief paragraph about how the code is organized]
"""

    PROMPT_HIGH = """Provide a detailed technical explanation of this Google Cirq quantum circuit.

CODE:
{code}

CIRCUIT ANALYSIS:
{analysis_text}

ALGORITHM: {algorithm}

Rules:
- Include mathematical intuition (state vectors, transformations)
- Explain WHY each gate choice was made
- Discuss the quantum state at each stage
- Reference relevant quantum computing principles

Format your response EXACTLY like this:

## Overview
[Detailed summary including the algorithm's purpose and quantum advantage]

## Detailed Step-by-Step Analysis
1. **`[code]`**
   - *What it does*: [technical explanation]
   - *State after*: [describe quantum state, e.g., |psi> = ...]
   - *Why this gate*: [reasoning]

[Continue for each line]

## Quantum Concepts In Depth
### [Concept 1]
[Detailed explanation with mathematical context]

### [Concept 2]
[Detailed explanation]

## Architecture Analysis
[Analysis of code structure, gate sequence logic, potential improvements]
"""

    PROMPT_VERY_HIGH = """Provide an exhaustive graduate-level explanation of this quantum circuit.

CODE:
{code}

CIRCUIT ANALYSIS:
{analysis_text}

ALGORITHM: {algorithm}

Rules:
- Full mathematical formalism with state evolution at each step
- Bra-ket notation and matrix representations where relevant
- Connections to quantum information theory
- Hardware implementation considerations
- Noise and error analysis
- Optimization suggestions with alternatives

Format your response EXACTLY like this:

## Theoretical Overview
[Comprehensive overview including mathematical foundations, connections to quantum information theory]

## Complete State Evolution Analysis
For each operation, show the full state transformation:

### Step 1: [Operation]
- **Code**: `[code line]`
- **Initial state**: |psi_0> = [state]
- **Operator**: [matrix or gate description]
- **Final state**: |psi_1> = [resulting state]
- **Physical interpretation**: [what this means]

[Continue for all operations]

## Quantum Concepts - Formal Treatment
### [Concept]
- **Definition**: [formal definition]
- **Mathematical representation**: [formulas]
- **Role in this circuit**: [specific application]

## Implementation Considerations
- **Gate decomposition**: [how gates map to hardware]
- **Noise sensitivity**: [which operations are most susceptible]
- **Suggested optimizations**: [concrete improvements]

## Alternative Approaches
[Other ways to achieve the same result, with trade-offs]
"""

    def _get_prompt_for_depth(self, depth: str) -> str:
        """Return the appropriate prompt template based on depth level."""
        depth_map = {
            "low": self.PROMPT_LOW,
            "intermediate": self.PROMPT_INTERMEDIATE,
            "high": self.PROMPT_HIGH,
            "very_high": self.PROMPT_VERY_HIGH,
        }
        prompt = depth_map.get(depth, self.PROMPT_INTERMEDIATE)
        logger.info(f"Using depth level: {depth}")
        return prompt

    def __init__(
        self,
        retriever: Retriever,
        analyzer: Optional[CircuitAnalyzer] = None,
        model: Optional[str] = None,
        provider: Optional[str] = None,
        temperature: Optional[float] = None,
    ):
        """
        Initialize the EducationalAgent.
        
        Args:
            retriever: Retriever instance for educational content
            analyzer: CircuitAnalyzer instance
            model: LLM model name
            provider: LLM provider ("ollama", "openai", "anthropic")
            temperature: Generation temperature
        """
        super().__init__(name="EducationalAgent")
        self.retriever = retriever
        self.analyzer = analyzer or CircuitAnalyzer()
        
        cfg = get_config()
        edu_model_cfg = cfg.get("agents", {}).get("educational", {}).get("model", {})
        
        self.model = model or edu_model_cfg.get("model", "anthropic.claude-haiku-4-5-20251001-v1:0")
        self.provider = (provider or edu_model_cfg.get("provider", "aws")).lower()
        if self.provider == "aws":
            inference_profile_arn = (
                edu_model_cfg.get("inference_profile_arn")
                or os.getenv("BEDROCK_INFERENCE_PROFILE_ARN")
                or os.getenv("BEDROCK_INFERENCE_PROFILE_ARN_EDUCATIONAL")
            )
            if inference_profile_arn:
                logger.info("Using Bedrock inference profile ARN for EducationalAgent Converse")
                self.model = inference_profile_arn
        self.temperature = temperature if temperature is not None else edu_model_cfg.get("temperature", 0.2)
        
        self.max_tokens = edu_model_cfg.get("max_tokens", 2000)
        self.top_p = edu_model_cfg.get("top_p", 1.0)
        self.frequency_penalty = edu_model_cfg.get("frequency_penalty", 0.0)
        self.presence_penalty = edu_model_cfg.get("presence_penalty", 0.0)
        
        logger.info(f"EducationalAgent using config from: agents.educational.model")
        logger.info(f"Model: {self.model}, Provider: {self.provider}")
        
        self._init_llm_client()
        
    def _init_llm_client(self):
        """Initialize the LLM client based on provider."""
        if self.provider == "ollama":
            self.ollama_base_url = os.getenv("OLLAMA_HOST", "http://localhost:11434")
            self.client = None
            self._bedrock_client = None
        elif self.provider == "aws":
            self.ollama_base_url = None
            self.client = None
            self._bedrock_client = get_bedrock_runtime_client(read_timeout=180)
        elif self.provider == "openai":
            if not OPENAI_AVAILABLE:
                raise ImportError("OpenAI library required for OpenAI provider")
            self.client = OpenAI()
            self._bedrock_client = None
        elif self.provider == "anthropic":
            if not ANTHROPIC_AVAILABLE:
                raise ImportError("Anthropic library required for Anthropic provider")
            self.client = anthropic.Anthropic()
            self._bedrock_client = None
        else:
            logger.warning(f"Unknown provider {self.provider}, defaulting to placeholder generation.")
            self._bedrock_client = None

    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate educational explanations.
        
        Args:
            task: Task dictionary with 'code' or 'circuit' and optional 'depth', 'algorithm'
            
        Returns:
            Result dictionary with explanations and learning materials
        """
        code = task.get("code", "")
        circuit = task.get("circuit")
        depth = task.get("depth", "intermediate")
        algorithm = task.get("algorithm", "quantum circuit")
        
        if not code and not circuit:
            return {
                "success": False,
                "error": "Either 'code' or 'circuit' is required",
            }
        
        try:
            analysis = None
            if circuit:
                analysis = self.analyzer.analyze(circuit)
            
            explanations = self._generate_explanations(
                code=code,
                circuit=circuit,
                analysis=analysis,
                depth=depth,
                algorithm=algorithm,
            )
            
            learning_materials = self._retrieve_learning_materials(algorithm)
            
            return {
                "success": True,
                "explanations": explanations,
                "learning_materials": learning_materials,
                "analysis": analysis,
            }
            
        except Exception as e:
            logger.error(f"EducationalAgent error: {e}")
            return {
                "success": False,
                "error": str(e),
            }
    
    def _generate_explanations(
        self,
        code: str,
        circuit: Any,
        analysis: Optional[Dict[str, Any]],
        depth: str,
        algorithm: Optional[str],
    ) -> Dict[str, Any]:
        """Generate educational explanations using LLM."""
        
        analysis_text = "No detailed analysis available."
        if analysis:
            metrics = analysis.get("metrics", {})
            analysis_text = f"Qubits: {metrics.get('num_qubits')}\nDepth: {metrics.get('depth')}\nOps: {metrics.get('num_operations')}"

        depth_normalized = depth.lower().replace(" ", "_").replace("-", "_")
        prompt_template = self._get_prompt_for_depth(depth_normalized)
        
        prompt = prompt_template.format(
            code=code,
            analysis_text=analysis_text,
            algorithm=algorithm,
            depth=depth
        )
        
        try:
            response_text = self._call_llm(prompt)
            
            return {
                "markdown": response_text.strip(),
                "depth": depth_normalized,
            }
            
        except Exception as e:
            logger.error(f"Error generating explanations with LLM: {e}")
            return self._fallback_explanations(code, analysis, algorithm)

    def _call_llm(self, prompt: str) -> str:
        """Call the configured LLM provider."""
        if self.provider == "ollama":
            url = f"{self.ollama_base_url.rstrip('/')}/api/generate"
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
            }
            resp = requests.post(url, json=payload, timeout=180)
            resp.raise_for_status()
            return resp.json().get("response", "")
        elif self.provider == "aws":
            response = self._bedrock_client.converse(
                modelId=self.model,
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                system=[{"text": EDUCATIONAL_SYSTEM}],
                inferenceConfig={
                    "maxTokens": self.max_tokens,
                    "temperature": self.temperature,
                },
            )
            return response["output"]["message"]["content"][0]["text"]
        elif self.provider == "openai":
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a quantum computing educator. Format your responses in markdown."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                top_p=self.top_p,
                frequency_penalty=self.frequency_penalty,
                presence_penalty=self.presence_penalty,
                response_format={"type": "json_object"}
            )
            return response.choices[0].message.content
            
        elif self.provider == "anthropic":
            response = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                top_p=self.top_p,
                messages=[
                    {"role": "user", "content": prompt + "\n\nRespond with valid JSON only."}
                ]
            )
            return response.content[0].text
            
        return "{}"

    def _fallback_explanations(self, code, analysis, algorithm):
        """Fallback method if LLM fails."""
        explanations = {
            "overview": f"This code implements {algorithm or 'a quantum circuit'} (Analysis failed).",
            "step_by_step": [],
            "concepts": [],
            "code_structure": "Unknown"
        }
        if code:
             explanations["step_by_step"] = [line.strip() for line in code.split('\n') if line.strip()]
        return explanations
    
    def _retrieve_learning_materials(self, algorithm: Optional[str]) -> List[Dict[str, str]]:
        """Retrieve learning materials for the algorithm."""
        materials = []
        
        if algorithm:
            query = f"{algorithm} algorithm tutorial explanation"
            top_k = get_config().get("rag", {}).get("retrieval", {}).get("top_k_results", 5)
            results = self.retriever.retrieve(query, top_k=top_k)
            
            for result in results:
                entry = result.get("entry", {})
                materials.append({
                    "title": entry.get("description", "Learning Material"),
                    "content": entry.get("code", "")[:500],
                    "source": entry.get("file", ""),
                })
        
        return materials
