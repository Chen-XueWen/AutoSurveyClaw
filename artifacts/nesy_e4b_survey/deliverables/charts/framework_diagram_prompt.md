# Framework Diagram Prompt

**Paper**: Synapse: A Functional Taxonomy of Neurosymbolic AI Architectures

## Image Generation Prompt

A clean, vector-art, technical architecture diagram illustrating a multi-pass data flow process, suitable for a top-tier ML conference paper. The style must be flat, professional, and highly structured, using subtle drop shadows for depth, strictly avoiding any photorealism. The layout should flow logically from left to right, depicting refinement stages. The background color is pure white. Use a sophisticated, academic color palette: muted blue (#4477AA) for initial steps, teal (#44AA99) for filtering/refinement, warm yellow-gold (#CCBB44) for key outputs/axes, and soft purple (#AA3377) for expert validation.

The diagram must feature four distinct, sequential modules connected by directional arrows.
Module 1 (Initial Input, Boxed in muted blue): Labeled "Initial Corpus Query" with sub-labels: "arXiv," "Semantic Scholar," "Keywords (e.g., Neurosymbolic AI)".
Module 2 (First Pass, Boxed in teal): Labeled "Systematic Screening Pass" with flowing arrows indicating refinement. Sub-labels: "Time Filter (2019+)," "Venue Priority (NeurIPS/ICML)."
Module 3 (Second Pass/Refinement, Boxed in a lighter teal/grey): Labeled "Expert Curation & Functional Categorization." This module should show an arrow pointing into a central concept box (colored warm yellow-gold) labeled "Functional Maturation Axis."
Module 4 (Final Output, Boxed in soft purple): Labeled "Final Taxonomy Set." This box should contain three smaller, interconnected conceptual nodes: "Structural Embedding," "Knowledge Graph Integration," and "Causal Modeling."

Use minimal text; labels must be concise. Arrows should be clean, curved vectors. Ensure high information density without feeling cluttered. The overall composition should convey rigorous, iterative refinement leading to a high-level, abstract taxonomy.

## Usage Instructions

1. Copy the prompt above into an AI image generator (DALL-E 3, Midjourney, Ideogram, etc.)
2. Generate the image at high resolution (2048x1024 or similar landscape)
3. Save as `framework_diagram.png` in the same `charts/` folder
4. Insert into the paper's Method section using:
   - LaTeX: `\includegraphics[width=\textwidth]{charts/framework_diagram.png}`
   - Markdown: `![Framework Overview](charts/framework_diagram.png)`
