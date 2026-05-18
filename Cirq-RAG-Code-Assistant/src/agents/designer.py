"""
Designer Agent Module

This module implements the Designer Agent, responsible for generating
initial Cirq code from natural language descriptions.

Author: Umer Farooq, Hussain Waseem Syed, Muhammad Irtaza Khan
Email: umerfarooqcs0891@gmail.com
"""

from typing import Dict, Any, Optional
from .base_agent import BaseAgent
from ..rag.generator import Generator
from ..rag.retriever import Retriever
from ..tools.compiler import CirqCompiler
from ..cirq_rag_code_assistant.config.logging import get_logger

logger = get_logger(__name__)


class DesignerAgent(BaseAgent):
    """Generates Cirq code from natural language descriptions."""
    
    def __init__(
        self,
        retriever: Retriever,
        generator: Generator,
        compiler: Optional[CirqCompiler] = None,
        use_rag: bool = True,
    ):
        """
        Initialize the DesignerAgent.
        
        Args:
            retriever: Retriever instance for context retrieval
            generator: Generator instance for code generation
            compiler: Optional compiler for validation
            use_rag: Whether to retrieve RAG context (False for no-RAG ablations)
        """
        super().__init__(name="DesignerAgent")
        self.retriever = retriever
        self.generator = generator
        self.compiler = compiler or CirqCompiler()
        self.use_rag = use_rag
    
    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate Cirq code from natural language description.
        
        Args:
            task: Task dictionary with 'query' and optional 'algorithm'
            
        Returns:
            Result dictionary with generated code and metadata
        """
        query = task.get("query", "")
        algorithm = task.get("algorithm")
        
        if not query:
            return {
                "success": False,
                "error": "Query is required",
            }
        
        try:
            if self.use_rag:
                result = self.generator.generate(
                    query=query,
                    algorithm=algorithm,
                )
            else:
                result = self.generator.generate_direct(query=query)
            
            validation = self.compiler.compile(result["code"], execute=False)
            
            if validation["errors"]:
                return {
                    "success": False,
                    "error": f"Generated code has errors: {validation['errors']}",
                    "code": result["code"],
                    "validation": validation,
                }
            
            return {
                "success": True,
                "code": result["code"],
                "metadata": result.get("metadata", {}),
                "algorithm": result.get("algorithm"),
                "context_used": result.get("context_used", 0),
            }
            
        except Exception as e:
            logger.error(f"DesignerAgent error: {e}")
            return {
                "success": False,
                "error": str(e),
            }
