# Cirq Code Assistant — Human Evaluation Guidelines

This document provides instructions and guidelines for human evaluators scoring the generated quantum code and educational explanations. Evaluators will assess samples across four key dimensions using a 5-point Likert scale (1 = Poor, 5 = Excellent).

---

## 1. Evaluation Dimensions

### A. Correctness
* **Goal:** Evaluate whether the code correctly implements the requested quantum algorithm and executes without runtime errors.
* **Rubric:**
  * **5 (Excellent):** The code runs and simulates perfectly. It correctly prepares the target quantum state or implements the target algorithm.
  * **4 (Good):** The code compiles and runs, but contains minor logical errors that do not crash execution (e.g., incorrect rotation angle or slightly off gate parameters).
  * **3 (Fair):** The code requires minor syntax corrections or variable definition adjustments to compile and run, but contains the core algorithmic steps.
  * **2 (Poor):** The code fails to compile or crashes on simulation due to major logical errors, invalid type usage, or missing functions.
  * **1 (Unacceptable):** The code is completely wrong, unrelated to the query, or empty.

### B. Readability
* **Goal:** Evaluate code structure, documentation, styling, and comment quality.
* **Rubric:**
  * **5 (Excellent):** The code is highly readable, modular, and well-structured. Variable and qubit names are self-explanatory. Inline comments or docstrings are informative and guide the reader.
  * **4 (Good):** The code is structured and easy to read, but comments are sparse or slightly generic.
  * **3 (Fair):** The code is structured but lacks comments entirely, or uses confusing variable/qubit index conventions.
  * **2 (Poor):** The code is unstructured, uses poor style practices, or is hard to follow.
  * **1 (Unacceptable):** The code is an unreadable single block, spaghetti code, or empty.

### C. Explanation Quality
* **Goal:** Evaluate the quality, accuracy, and educational value of the natural language explanations accompanying the code.
* **Rubric:**
  * **5 (Excellent):** The explanation is clear, accurate, and structured. It explains the theoretical concept of the algorithm and maps it step-by-step to the gates used in the code.
  * **4 (Good):** The explanation is accurate and clear, but lacks structural detail or has slight gaps in mapping theory to code.
  * **3 (Fair):** The explanation is correct but brief, generic, or does not connect theory to code.
  * **2 (Poor):** The explanation is inaccurate, confusing, or too brief to be helpful.
  * **1 (Unacceptable):** No explanation is provided, or the explanation contains gross conceptual errors.

### D. Cirq Idiomacy
* **Goal:** Evaluate whether the code adheres to official and modern Google Cirq design patterns and conventions.
* **Rubric:**
  * **5 (Excellent):** Follows modern Cirq practices (e.g., using `cirq.LineQubit` or `cirq.GridQubit` appropriately, structuring operations via `cirq.Circuit()`, using correct gate syntax, and avoiding deprecated packages).
  * **4 (Good):** Follows standard conventions but includes minor non-idiomatic patterns (e.g., inefficient list appends or redundant moment structures).
  * **3 (Fair):** The code is functional but uses outdated syntax or deprecated methods (e.g., CZPowGate with obsolete exponents).
  * **2 (Poor):** The code relies on deprecated/removed libraries (such as old `cirq.contrib` libraries) or breaks standard Cirq design practices.
  * **1 (Unacceptable):** The code does not look like standard Cirq code or is classical.

---

## 2. Rating Form Template

For each sample, evaluators should fill out the following block in their review:

```markdown
### Sample ID: SAMP-XXX
- **Correctness Score (1-5):** 
- **Readability Score (1-5):** 
- **Explanation Score (1-5):** 
- **Cirq Idiomacy Score (1-5):** 
- **Comments/Notes:** 
```
