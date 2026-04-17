# Taxonomy for Neurosymbolic AI Literature

## 1. Taxonomy Overview

**Top-Level Organization Principle:** **Functional Maturation Axis.**

The taxonomy organizes the literature not merely by the components combined (e.g., "Graph + NN"), but by the *level of cognitive function* the resulting system is attempting to model, reflecting a progression from basic pattern recognition to complex, human-level reasoning. This structure is highly actionable because researchers can situate their work—or identify the gap—based on whether their contribution primarily addresses **Structure**, **Action**, **Process**, or **Context**.

**Rationale:** The field is maturing. Organizing by *functional maturity* (what the AI *can* do) is more informative for a survey paper than organizing by *methodological component* (what the AI is *made of*). The categories are designed to be **mutually exclusive in their primary focus** (e.g., a paper focused on embedding KGs is primarily in Structure, even if it uses causal inference), but **collectively exhaustive** because advanced systems must address multiple levels simultaneously.

---

## 2. Category Definitions

### A. Structure-Constrained Learning (The Knowledge Anchor)
*   **Definition:** Research focused on injecting explicit, pre-defined knowledge (ontologies, facts, rules) into neural models primarily to guide feature learning, enforce consistency, and prevent the model from learning spurious correlations inherent in raw data.
*   **Distinguishing Criteria:** The primary mechanism involves regularization, knowledge embedding, or graph-to-vector translation. The system is primarily *descriptive* (describing the domain's known facts).
*   **Key Papers:** *Knowledge Graphs of Driving Scenes to Empower...*; *Handbook on Neurosymbolic AI and Knowledge Graphs*.

### B. Causal and Interventional Reasoning (The "Why" Engine)
*   **Definition:** Research focused on moving beyond correlation to model causality ($\text{do}(X)$). These systems aim to determine the necessary and sufficient causes of an outcome and predict outcomes under hypothetical interventions or counterfactual scenarios.
*   **Distinguishing Criteria:** The core task involves manipulating variables or asking "What if?" questions, requiring the formalization of causal graphs (e.g., Judea Pearl's framework). The system is *explanatory*.
*   **Key Papers:** *Causal Neurosymbolic AI: A Synergy Between Causality and Neurosymbolic Methods*; Papers involving counterfactual question generation.

### C. Computationally Executable Logic (The Algorithmic Bridge)
*   **Definition:** Technical research dedicated to making symbolic reasoning mechanisms (like Prolog inference, satisfiability checking, or logical rule application) trainable end-to-end using gradient descent. This addresses the "differentiability bottleneck."
*   **Distinguishing Criteria:** The focus is on the *mathematical mechanism* of integration—developing new computational layers or differentiable programming frameworks—rather than the specific knowledge domain or the final goal. The system is *procedural*.
*   **Key Papers:** *Reasoning in Neurosymbolic AI*; Foundational papers on differentiable logic programming.

### D. Contextual & Cognitive Alignment (The Application Layer)
*   **Definition:** Meta-level research addressing the deployment context, explainability, and interaction model. This category governs *how* the system's output is presented, interpreted, and utilized within a complex, high-stakes human-machine teaming environment.
*   **Distinguishing Criteria:** Evaluation metrics move beyond accuracy to include *certifiability*, *trustworthiness*, *interactivity*, and *adherence to human cognitive models*. The system is *governing*.
*   **Key Papers:** *On the Use of Neurosymbolic AI for Defending Against Cyber Attacks*; *AI Systems that Intelligently Frame Explanations as Questions...*; Work on human-AI teaming protocols.

---

## 3. Hierarchy

*   **I. Structure-Constrained Learning (The Knowledge Anchor)**
    *   A. Knowledge Graph Integration (KG-to-Vector)
        *   1. Schema-Guided Generation (Using KG constraints on text generation)
        *   2. Multi-Hop Reasoning Over KGs
    *   B. Rule-Based Inductive Biasing
        *   1. Ontology-Guided Feature Selection
        *   2. Logic Programming Integration (e.g., Differentiable Prolog)
*   **II. Causal and Interventional Reasoning (The "Why" Engine)**
    *   A. Causal Discovery from Data
        *   1. Structure Learning (Inferring $\text{DAGs}$ from observations)
        *   2. Intervention Simulation ($\text{do}$-calculus application)
    *   B. Counterfactual Prediction
        *   1. Counterfactual Generation (What if variables were different?)
        *   2. Causal Model Refinement (Updating the model based on counterfactual evidence)
*   **III. Computationally Executable Logic (The Algorithmic Bridge)**
    *   A. Gradient-Based Symbolic Inference
        *   1. Differentiable Search Algorithms (e.g., MCTS with gradient flow)
        *   2. Continuous Logic Representation (Encoding formal logic into continuous spaces)
    *   B. Modular/Hybrid Architecture Design
        *   1. Sequential Pipeline Models (NN $\rightarrow$ Logic $\rightarrow$ NN)
        *   2. Joint Optimization Frameworks (Unified loss/objective function)
*   **IV. Contextual & Cognitive Alignment (The Application Layer)**
    *   A. Explainability and Trust (XAI)
        *   1. Traceability and Verification (Showing the exact logical steps)
        *   2. Uncertainty Quantification (Knowing *when* the model doesn't know)
    *   B. Human-AI Interaction Design
        *   1. Interactive Questioning/Scaffolding (Guiding user reasoning)
        *   2. Domain-Specific Workflow Adaptation (e.g., Medical Triage Protocols)

---

## 4. Paper Classification Table

*(Note: Since no specific papers were provided for classification, this table uses representative examples derived from the synthesis text to demonstrate the mapping.)*

| Paper Title / Concept | Primary Category | Sub-Category | Key Contribution |
| :--- | :--- | :--- | :--- |
| *Knowledge Graphs of Driving Scenes...* | I. Structure-Constrained Learning | Multi-Hop Reasoning Over KGs | Uses KG to constrain scene understanding. |
| *Causal Neurosymbolic AI...* | II. Causal and Interventional Reasoning | Causal Discovery from Data | Explicitly models $\text{do}$-calculus alongside learning. |
| *Differentiable Logic Programming* | III. Computationally Executable Logic | Gradient-Based Symbolic Inference | Focuses purely on making logic differentiable. |
| *AI Systems that Intelligently Frame Explanations as Questions...* | IV. Contextual & Cognitive Alignment | Interactive Questioning/Scaffolding | Defines the optimal interaction pattern for users. |
| *Neurosymbolic AI for Network Intrusion Detection* | I. Structure-Constrained Learning | Ontology-Guided Feature Selection | Uses threat ontologies to guide feature extraction. |
| *Advanced Air Mobility (AAM) Integration* | IV. Contextual & Cognitive Alignment | Domain-Specific Workflow Adaptation | Focuses on certifiability and operational protocols. |
| *Enhancing Transcription Factor Prediction via Domain Knowledge...* | I. Structure-Constrained Learning | Schema-Guided Generation | Uses biological pathways (Schema) to constrain prediction. |

---

## 5. Cross-Cutting Themes

These themes do not belong to a single category but represent necessary conditions for advanced NeSyAI systems:

1.  **The Knowledge Engineering Pipeline:** The process of transforming unstructured, qualitative expert knowledge (text, protocols) into a formal, computational structure (KG, Ontology) that can be consumed by the model. (Links I $\rightarrow$ III).
2.  **The Interrogation Loop:** The mechanism where the AI's uncertainty or lack of evidence forces it to generate a question back to the user or environment, rather than just providing a single answer. (Links II $\leftrightarrow$ IV).
3.  **Joint Optimization:** The mathematical imperative to train the symbolic structure and the neural weights simultaneously, ensuring the symbolic scaffolding *drives* the learning objective, not just validates it post-hoc. (Links I $\leftrightarrow$ III).
4.  **Domain Formalization:** The necessity of mapping the high-level, abstract rules of a domain (e.g., "Newton's Laws" in physics, or "FAA regulations" in aviation) into a precise, computable axiomatic base before any AI training can begin. (Links I $\rightarrow$ IV).

---

## 6. Open Challenges by Category

| Category | Critical Unsolved Problem | Research Implication |
| :--- | :--- | :--- |
| **I. Structure-Constrained Learning** | **Automated Knowledge Acquisition (The Ontology Bottleneck):** How to scale KG population from noisy, unstructured text/sensor streams without constant expert intervention. | Developing robust, zero-shot relation extraction and ontology alignment tools. |
| **II. Causal Reasoning** | **Causal Intervention in High-Dimensional Continuous Space:** How to define and estimate the effect of an intervention $\text{do}(X)$ when $X$ is a continuous feature vector (e.g., raw sensor data) rather than a discrete variable. | Developing continuous counterfactual estimation metrics and methods. |
| **III. Computationally Executable Logic** | **Tractability of Infinite Search Spaces:** Developing efficient, gradient-based search algorithms that can handle the combinatorial explosion of inference paths in large, complex rule sets. | Novel sampling techniques or structured pruning methods that preserve logical completeness. |
| **IV. Contextual & Cognitive Alignment** | **Modeling Human Cognitive State:** Creating formal models of user cognitive load, expertise, and trust that dictate the optimal explanation modality (e.g., shifting from declarative to interrogative). | Developing $\text{Human-in-the-Loop}$ feedback loops that actively measure and adapt to human cognitive states. |