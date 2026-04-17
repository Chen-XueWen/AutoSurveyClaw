# Supporting Data-Frame Dynamics in AI-assisted Decision Making

*source: abstract_only | tokens: 126*

This paper introduces a novel mixed-initiative framework designed to address the limitations of existing AI decision support systems in high-stakes environments. The central problem identified is the inability of current models to support the continuous, iterative interplay between evolving empirical evidence and shifting diagnostic hypotheses—a core component of human sensemaking that is often poorly modeled computationally.

The technical approach is deeply grounded in theoretical frameworks, specifically the data-frame theory of sensemaking and the evaluative AI paradigm. This grounding dictates the architecture: the system is designed not merely to classify, but to facilitate a *collaborative* cycle where both the human expert and the AI agent jointly construct, validate, and adapt hypotheses. This mixed-initiative structure moves beyond simple advisory roles toward true partnership in reasoning.

To achieve this dynamic, interpretable interaction, the framework employs a concept bottleneck model. This component is crucial as it provides a structured, bottleneck representation that enforces interpretability, allowing the system to explicitly articulate *why* a hypothesis is being updated or challenged based on incoming data frames. This mechanism directly bridges the neural processing of raw data with the symbolic manipulation of diagnostic concepts.

The system is demonstrated via an AI-assisted skin cancer diagnosis prototype. While specific benchmark metrics are not provided, the paper claims successful implementation of dynamic hypothesis updating within this diagnostic context. The core contribution lies in its ability to manage the *dynamics* of knowledge—it doesn't just process data points; it models the *process* of sensemaking itself.

In the context of Neurosymbolic AI, this work represents a significant step toward integrating robust neural pattern recognition (via the concept bottleneck) with explicit, theory-driven symbolic reasoning (via data-frame theory). It addresses a key gap in the field by moving beyond static decision boundaries toward modeling the inherently iterative and theory-laden process of expert judgment, making it highly relevant for future research in complex diagnostic and operational decision support systems.