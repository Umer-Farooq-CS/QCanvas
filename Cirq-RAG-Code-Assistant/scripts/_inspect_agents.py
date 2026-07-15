import os, sys, inspect
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"
sys.path.insert(0, ".")
from src.agents.designer import DesignerAgent
from src.agents.optimizer import OptimizerAgent
from src.agents.validator import ValidatorAgent
from src.agents.educational import EducationalAgent
print("DesignerAgent  :", inspect.signature(DesignerAgent.__init__))
print("OptimizerAgent :", inspect.signature(OptimizerAgent.__init__))
print("ValidatorAgent :", inspect.signature(ValidatorAgent.__init__))
print("EducationalAgent:", inspect.signature(EducationalAgent.__init__))
