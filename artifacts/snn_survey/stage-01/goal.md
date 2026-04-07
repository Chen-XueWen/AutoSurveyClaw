# Survey Project: my-survey

## **Topic**
**Systematic Review of Neural Architectures for Set-Structured Data (Set Neural Networks)**

## **Scope**
*   **Inclusion (In Scope):**
    *   **Core Architectures:** Deep Sets, PointNet/PoinNet++, Set Transformers, Dynamic Graph CNNs, Permutation Equivariant/Invariant Networks.
    *   **Problem Setting:** Input data represented as unordered collections (sets) where cardinality varies and order does not matter.
    *   **Applications:** Point cloud processing, graph representation learning (as sets of nodes), multi-agent systems, particle physics simulations, and recommendation systems (sets of items).
    *   **Time Period:** January 2017 (DeepSets seminal work) to Present.
*   **Exclusion (Out of Scope):**
    *   Standard Convolutional Neural Networks (CNNs) or Recurrent Neural Networks (RNNs/LSTMs) applied to fixed-grid or sequential data where permutation invariance is not the primary constraint.
    *   Pure mathematical set optimization without neural network components.
    *   Survey papers without original empirical results or theoretical contributions (secondary surveys excluded).
    *   Non-English publications.

## **SMART Goal**
To conduct a systematic literature review that identifies, selects, and analyzes **60 to 100 high-quality primary studies** on set-based neural architectures by the project completion date. This survey will produce a unified taxonomy of permutation-invariant operations and a comparative analysis of computational complexity versus representational power across identified architectures, thereby reducing fragmentation in the current literature and providing a reference framework for practitioners selecting set-based models.

## **Inclusion Criteria**
1.  **Publication Venue:** Peer-reviewed conference proceedings (e.g., NeurIPS, ICML, ICLR, CVPR, ICRA) or high-impact journals (e.g., IEEE TPAMI, JMLR).
2.  **Relevance:** Papers must explicitly propose or evaluate neural network layers/functions designed for set-valued inputs (permutation invariance/equivariance).
3.  **Recency:** Published between January 2017 and the current date (to capture the evolution post-DeepSets).
4.  **Language:** English.
5.  **Accessibility:** Full text available for extraction.
6.  **Quality Score:** Each selected paper must receive a minimum quality assessment score of **4.0/5.0** based on the `SurveyQualityRubric_v1` (clarity of problem definition, methodological rigor, reproducibility of results).

## **Exclusion Criteria**
1.  Papers that treat sets merely as a batch dimension without specific architectural modifications for set properties.
2.  Pre-prints (arXiv) unless the work has been published in a peer-reviewed venue or is a seminal citation with significant follow-up impact.
3.  Papers focusing solely on set operations (e.g., maximum, minimum) without neural network integration.
4.  Papers where the primary contribution is a dataset rather than a neural architecture.
5.  Papers with critical methodological flaws (e.g., lack of baseline comparison, non-reproducible experimental setup).

## **Constraints**
*   **Target Paper Count:** 75 papers (±25% variance allowed based on density of recent literature).
*   **Quality Threshold:** Minimum score of **4.0/5.0** on the `SurveyQualityRubric_v1` (evaluating theoretical soundness, empirical validation, and clarity).
*   **Timeline:** 12 Weeks (Search: 2 weeks, Screening: 3 weeks, Extraction/Analysis: 5 weeks, Writing/Review: 2 weeks).
*   **Tools:** PRISMA 2020 guidelines, Zotero for citation management, Python (Pandas) for data extraction.

## **Success Criteria**
A high-quality survey of this topic is achieved when:
1.  **Taxonomy Completeness:** The resulting taxonomy covers at least 80% of the identified methodological approaches (e.g., sum-aggregation, attention-based, graph-based).
2.  **Gap Identification:** The survey explicitly identifies at least 3 unresolved research gaps (e.g., computational cost for high-cardinality sets, lack of standard benchmarks).
3.  **Reproducibility:** All key architectural formulas and loss functions are derived and verified.
4.  **Citation Coverage:** The survey includes all seminal works (DeepSets, PointNet, Set Transformers) and >90% of papers citing these works with significant methodological extensions.
5.  **Usability:** The final output includes a decision matrix to help practitioners select architectures based on cardinality and invariance requirements.

## **Generated**
2023-10-27T14:30:00Z