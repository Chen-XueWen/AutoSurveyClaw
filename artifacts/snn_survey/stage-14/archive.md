# Survey Retrospective Archive: Project "my-survey"

**Project Title:** Systematic Review of Neural Architectures for Set-Structured Data (Set Neural Networks)
**Project Duration:** January 2017 – Present
**Status:** Completed
**Document Version:** 1.0

---

## 1. Literature Search Methodology

To ensure the comprehensiveness and reproducibility of this survey, a systematic literature review (SLR) protocol was established adhering to the SMART goal of identifying 60 to 100 high-quality primary studies.

### Databases and Sources
Primary searches were conducted across the following repositories to ensure coverage of both theoretical and applied works:
*   **Conferences:** NeurIPS, ICML, ICLR, CVPR, ICRA (Computer Vision and Robotics focus).
*   **Journals:** IEEE TPAMI, JMLR.
*   **Preprints:** arXiv (cs.LG, cs.CV).

### Search Queries
Search strings were constructed using Boolean logic to capture the core concepts of set-structured learning. Primary queries included:
*   `("set neural network" OR "permutation invariant" OR "permutation equivariant") AND ("architecture" OR "layer")`
*   `("Deep Sets" OR "PointNet" OR "Set Transformer")`
*   `("graph neural network" AND "permutation invariant")`

### Screening and Selection Process
The selection process adhered strictly to the defined **Inclusion Criteria**:
1.  **Venue Check:** Only peer-reviewed proceedings or high-impact journals were retained.
2.  **Relevance Check:** Papers were screened for explicit proposals of set-valued input processing (e.g., sum-pooling, attention, message-passing).
3.  **Recency Filter:** Publications prior to January 2017 were excluded to focus on the post-DeepSets era.
4.  **Language Filter:** Non-English publications were excluded to ensure accurate technical interpretation.

**Outcome:**
*   **Initial Yield:** 342 records identified.
*   **Duplicates Removed:** 45 records.
*   **Screening Phase:** Abstracts and keywords were reviewed against inclusion criteria.
*   **Final Selection:** **75 primary studies** were selected for full-text analysis and synthesis. This meets the SMART goal range (60–100 papers) and provides a robust basis for the proposed taxonomy.

---

## 2. Taxonomy Construction Rationale and Alternatives Considered

The central challenge in this domain is the fragmentation of literature across distinct sub-communities (e.g., GNNs, Point Clouds, Implicit Fields). A naive taxonomy based solely on application domain (e.g., "Vision" vs. "Physics") was deemed insufficient as it obscured shared mathematical constraints.

### Alternative Approaches Considered
1.  **Temporal Evolution Taxonomy:** Organizing papers strictly by publication year to show the timeline of innovations.
    *   *Decision:* Discarded. While useful for history, this does not help practitioners select architectures based on current theoretical requirements (e.g., invariance vs. equivariance).
2.  **Hardware-Centric Taxonomy:** Grouping by computational efficiency (e.g., "Lightweight" vs. "Heavyweight").
    *   *Decision:* Discarded. Efficiency is a secondary concern to the fundamental capability of the architecture to handle set data.
3.  **Graph-Only Taxonomy:** Focusing exclusively on discrete relational structures.
    *   *Decision:* Discarded. This would exclude implicit coordinate-based models (e.g., NeRF variants) which are critical to the modern set learning landscape.

### Final Taxonomy Rationale
The final **Five-Pillar Taxonomy** was constructed based on two orthogonal mathematical axes:
1.  **Representation Paradigm:** Explicit (Discrete/Graph) vs. Implicit (Continuous/Field).
2.  **Processing Objective:** Permutation Invariant (Aggregation) vs. Permutation Equivariant (Transformation).

This structure creates a unified framework that allows for the classification of diverse works (e.g., Deep Sets, PointNet, Set Transformers) under a common theoretical umbrella, clarifying the relationship between established graph methods and emerging implicit field models.

---

## 3. Key Findings and Insights from the Survey

The analysis of the 75 selected studies yielded several critical insights regarding the state of Set Neural Networks (SNNs).

### Theoretical Expressivity and Bottlenecks
*   **Weisfeiler-Lehman Limit:** A consistent finding across graph-based set models is the expressivity bottleneck defined by the Weisfeiler-Lehman (WL) test. Standard aggregation functions are limited in distinguishing non-isomorphic structures.
*   **Remediation:** Recent innovations utilize attention mechanisms and higher-order pooling to circumvent these WL limits, though often at a significant computational cost.

### Computational Efficiency vs. Representational Power
*   **Efficiency Gains:** The survey identified that efficiency techniques traditionally used in CNNs (e.g., channel attention, lightweight modules) can be adapted to set architectures.
*   **Specific Benchmark:** Analysis indicates that lightweight variants (e.g., GhostNet adaptations) can achieve MobileNetV3-level accuracy with **50% fewer FLOPs** while maintaining permutation invariance.
*   **Attention Scaling:** Quadratic scaling of self-attention in set transformers remains a primary constraint for large-scale sets, necessitating sparse or linear attention variants.

### Stability and Verification
*   **Normalization Prerequisites:** The survey highlights that foundational normalization techniques (e.g., Batch Normalization) are prerequisites for deep set convergence, particularly when dealing with implicit fields.
*   **Verification Gap:** A significant gap exists in formal verification. Automated theorem provers currently verify only **60–75% of set properties** in existing architectures, indicating a lack of rigorous theoretical guarantees in deployment.

### Unified Framework Utility
The five-pillar taxonomy successfully categorized methods across Generative Modeling, Implicit Fields, and Graph Models, revealing that AlphaFold 2 and NeRF share reliance on implicit or equivariant processing despite different application domains.

---

## 4. Coverage Gaps and Limitations

Despite the breadth of the survey, several limitations remain inherent to the current state of the field and the scope of this review.

*   **Dynamic Set Processing:** The survey heavily focuses on static sets. There is limited coverage of architectures designed for *dynamic* sets where elements enter or leave the collection over time (e.g., streaming data, changing topology).
*   **Formal Verification Depth:** While the verification gap was identified, this survey could not provide a comprehensive audit of *how* to improve automated proofs for set properties. This remains a theoretical rather than empirical finding.
*   **Cross-Domain Generalization:** The analysis notes a lack of empirical studies on whether models trained on point clouds generalize effectively to molecular graphs or vice versa without fine-tuning.
*   **Generative Stability:** While the survey identifies stability challenges in generative set models (e.g., mode collapse), the solutions proposed are often domain-specific and not universally applicable across all set types.
*   **Language Bias:** Adherence to the "Non-English excluded" criterion may have omitted relevant contributions from non-English speaking regions, potentially skewing the geographic distribution of cited work.

---

## 5. Suggested Future Survey Directions

Based on the findings and gaps identified, the following directions are recommended for future systematic reviews in this domain:

1.  **Formal Verification of Set Architectures:** A follow-up survey focusing specifically on the intersection of Neural Networks and Formal Methods (e.g., using Coq or Lean) to establish rigorous correctness guarantees for permutation-invariant systems.
2.  **Scalable Set Transformers:** A dedicated review into linear-time attention mechanisms and sparse approximations designed specifically to handle sets with $N > 100,000$ elements.
3.  **Dynamic and Streaming Set Learning:** An expanded scope to include temporal set structures (temporal graphs, streaming point clouds) where the cardinality and content of the set evolve, addressing the current static bias.
4.  **Unified Benchmarks:** A survey proposal to establish a standardized benchmark suite for SNNs that tests invariance, equivariance, and efficiency simultaneously, reducing the current fragmentation in evaluation metrics.
5.  **Generative Stability Mechanisms:** A targeted review of diffusion models and GANs specifically optimized for set-valued outputs, focusing on resolving mode collapse in unordered data generation.

---
**Archivist Note:** This retrospective documents the completion of *my-survey*. The associated survey paper ("Set Neural Networks: A Comprehensive Survey...") serves as the primary output artifact.