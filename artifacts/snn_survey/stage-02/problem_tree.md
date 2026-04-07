# Survey Strategy Decomposition: Neural Architectures for Set-Structured Data

## **Key Survey Questions**
*These questions directly address the SMART goals and success criteria, ensuring the survey delivers a unified taxonomy and decision framework.*

1.  **How do modern architectures mathematically guarantee permutation invariance versus equivariance, and what are the theoretical expressiveness bounds of these constraints?**
    *   *Rationale:* Addresses the "theoretical soundness" quality criterion and forms the foundation of the unified taxonomy.
2.  **What is the quantifiable trade-off between computational complexity (specifically regarding set cardinality $N$) and representational power across aggregation, attention, and graph-based methods?**
    *   *Rationale:* Directly supports the "comparative analysis of computational complexity" goal and informs the practitioner decision matrix.
3.  **How has the architectural paradigm evolved from early sum-aggregation (DeepSets) and point-wise processing (PointNet) to attention-based and dynamic graph approaches (Set Transformers, DGCNN)?**
    *   *Rationale:* Ensures "Taxonomy Completeness" by capturing the methodological evolution from 2017 to present.
4.  **Which architectural patterns demonstrate superior performance and robustness in specific application domains (e.g., geometric point clouds vs. relational graph data vs. unordered sequence modeling)?**
    *   *Rationale:* Addresses "Usability" by enabling the creation of the domain-specific selection criteria.
5.  **What are the critical unresolved limitations regarding scalability, dynamic set updates, and generalization that define the current research frontier?**
    *   *Rationale:* Explicitly targets the "Gap Identification" success criterion (minimum 3 gaps).

---

## **Search Themes**
*These themes guide the systematic search strings (Boolean logic) to ensure coverage of the 60-100 target papers within the 2-week search window.*

*   **Theme 1: Core Theoretical Constraints**
    *   *Keywords:* `("permutation invariance" OR "permutation equivariance" OR "set function" OR "symmetric function") AND ("neural network" OR "deep learning" OR "attention")`
    *   *Focus:* Papers explicitly proving or utilizing invariance/equivariance properties.
*   **Theme 2: Architectural Mechanisms**
    *   *Keywords:* `("Deep Sets" OR "PointNet" OR "Set Transformer" OR "Dynamic Graph CNN" OR "Attention on Sets" OR "Row-wise aggregation")`
    *   *Focus:* Identifying specific methodological families for the taxonomy.
*   **Theme 3: Application Domains**
    *   *Keywords:* `("point cloud" OR "particle physics" OR "multi-agent" OR "graph neural network" OR "recommendation system" OR "set-based recommendation")`
    *   *Focus:* Ensuring the scope covers the specified application areas without drifting into fixed-grid CNNs.
*   **Theme 4: Scalability & Complexity**
    *   *Keywords:* `("cardinality" OR "O(N^2)" OR "scalability" OR "computational efficiency" OR "large set")`
    *   *Focus:* Filtering for papers that address the complexity vs. power trade-off.
*   **Theme 5: Benchmarks & Evaluation**
    *   *Keywords:* `("benchmark" OR "evaluation" OR "ModelNet" OR "ShapeNet" OR "MoleculeNet" OR "KITTI")`
    *   *Focus:* Identifying papers with rigorous empirical validation (Quality Score $\ge$ 4.0).

---

## **Taxonomy Directions**
*Proposed dimensions to organize the 75 selected papers into a coherent framework.*

1.  **Output Constraint Dimension**
    *   **Invariant:** Output is a single vector regardless of input order (e.g., classification, aggregation).
    *   **Equivariant:** Output is a set where reordering input reorders output (e.g., point-wise coordinate prediction).
    *   **Mixed:** Hybrid operations depending on the layer.
2.  **Processing Mechanism Dimension**
    *   **Aggregation-Based:** Element-wise MLP + Global Symmetric Function (Deep Sets).
    *   **Attention-Based:** Self-attention mechanisms adapted for sets (Set Transformers, Permutation Equivariant Attention).
    *   **Point-wise/Local:** Local feature extraction before aggregation (PointNet, DGCNN).
    *   **Graph-Relational:** Sets of nodes with learned edge relations (GNNs treated as sets).
3.  **Cardinality Handling Dimension**
    *   **Fixed-Size Input:** Requires padding/truncation.
    *   **Variable-Size Input:** Native support for arbitrary $N$ without padding.
    *   **Dynamic Cardinality:** Ability to process sets where $N$ changes dynamically during forward pass.
4.  **Input Modality Dimension**
    *   **Geometric:** 3D coordinates, voxel grids.
    *   **Relational:** Feature vectors without explicit geometry.
    *   **Sequential-as-Set:** Tokenized sequences treated as unordered sets.

---

## **Expected Coverage**
*Specific elements that must be present to meet the Success Criteria.*

*   **Key Methods:**
    *   **Seminal:** Deep Sets (Zaheer et al., 2017), PointNet (Qi et al., 2017), PointNet++ (Qi et al., 2017).
    *   **Attention:** Set Transformer (Izmailov et al., 2019/2020), Permutation Equivariant Transformers (PE-Transformer).
    *   **Graph/Local:** DGCNN (Wang et al., 2019), Dynamic Graph CNN.
    *   **Emerging:** Large-Set Transformers, Efficient Set Attention (for high $N$).
*   **Benchmarks:**
    *   Must cover **ShapeNet**, **ModelNet40**, **KITTI**, and **MoleculeNet** (or similar chemistry datasets) for geometric/physical tasks.
    *   Must cover **CiteSeer/X** or similar for relational tasks.
*   **Application Areas:**
    *   **Geometric Deep Learning:** Point cloud classification/segmentation.
    *   **Physics:** Particle interaction simulations.
    *   **AI Agents:** Multi-agent reinforcement learning (sets of agents).
    *   **Recommendation:** Bag-of-items models.

---

## **Risks**
*Potential pitfalls that could jeopardize the 12-week timeline or the quality of the final survey.*

*   **Risk 1: The "Graph vs. Set" Ambiguity**
    *   *Description:* Graph Neural Networks (GNNs) are often cited in set literature but rely on edge connectivity (topology), which technically violates pure set assumptions unless edges are treated as part of the set content.
    *   *Mitigation:* Strictly define inclusion criteria for GNNs (only include if nodes are treated as an unordered set without prior edge structure, or if the graph is dynamic/learned). Exclude static graph topology assumptions.
*   **Risk 2: Computational Complexity Claims**
    *   *Description:* Many recent "Set Transformer" variants claim $O(N)$ complexity but rely on approximations (e.g., kernelized attention) that may not scale linearly in practice.
    *   *Mitigation:* During extraction, verify empirical scaling plots. If a paper claims linear complexity but shows quadratic scaling in tables, flag for exclusion or nuanced analysis in the "Complexity" section.
*   **Risk 3: Fast-Moving Sub-Field & Citation Lag**
    *   *Description:* The field moves faster than publication cycles; seminal arXiv preprints may not be in peer-reviewed venues yet but are critical for the "Present" scope.
    *   *Mitigation:* Allow for inclusion of high-impact arXiv preprints (citing the seminal works with >50 follow-ups) if they meet the Quality Rubric, to ensure the survey isn't outdated by the time of publication.
*   **Risk 4: Reproducibility & Hyperparameter Sensitivity**
    *   *Description:* Set architectures can be highly sensitive to normalization and initialization, leading to inconsistent results across papers.
    *   *Mitigation:* Focus the "Reproducibility" success criterion on papers that provide code links or detailed normalization strategies in the appendix. Exclude papers where the "set" operation is a minor addition to a standard CNN without specific justification.