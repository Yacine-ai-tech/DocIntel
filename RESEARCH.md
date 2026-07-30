# DocIntel: Vision-LLM Zero-Shot Multi-Modal Document Extraction & Layout Decomposition Engine

## Abstract
DocIntel presents an OCR-free, vision-first document extraction architecture for complex enterprise visual document processing. By bypassing character fragmentation heuristics and modeling document pages as spatial layout trees $\mathcal{T}_{layout} = (V, E)$, DocIntel preserves multi-header table alignments, key-value visual hierarchies, and complex form structures. The system incorporates deterministic post-processing normalization layers to standardize multi-currency amounts (ISO-4217) and multi-locale dates (ISO-8601).

---

## 1. Architecture & Spatial Parsing Model

DocIntel supports multi-page visual document parsing across three extraction pathways: Route A (Cloud Vision LLM), Route B (Local Vision LLM via Ollama), and Route C (Multilingual Tesseract OCR + LLM fallback).

```
Visual PDF / Image Input
        |
        v
Page-to-Image Rendering / Downscaling
        |
        v
+----------------------------------------------------------------+
| Multi-Modal Vision Processing Pipeline                          |
| - Route A: Vision LLM Spatial Layout Parser                     |
| - Route B: Local Vision Model (Llama 3.2 Vision / Qwen 2.5-VL)  |
| - Route C: Multilingual OCR (eng+fra+deu+nld+spa+ita)           |
+----------------------------------------------------------------+
        |
        v
Deterministic Normalization Engine (ISO-4217 / ISO-8601)
        |
        v
Structured Multi-Page JSON + Confidence Metrics
```

### Spatial Tree Formulation
A document page is represented as a spatial layout graph $\mathcal{T}_{layout} = (V, E)$:
- **Vertices $V$**: Visual text nodes $v_i = (\text{text}_i, \text{bbox}_i, \text{confidence}_i)$ where $\text{bbox}_i = [x_{min}, y_{min}, x_{max}, y_{max}]$.
- **Edges $E$**: Spatial adjacency relationships (reading order, table cell alignment, visual parent-child hierarchy).

---

## 2. Deterministic Normalization & Error Bound Analysis

To eliminate LLM formatting variance, extracted text fields undergo deterministic normalization:

$$\text{NormAmount}(\text{raw}) \to (\text{float\_value}, \text{ISO\_4217\_code})$$

For example, European currency representations (e.g., `1.234,56 €`), West-African space-grouped formats (`1 003 000 FCFA`), and Swiss formats (`CHF 1'234.56`) are mapped directly to canonical numerical representations (`1234.56`, `EUR`/`XOF`/`CHF`).

---

## 3. Reproducibility & Empirical Benchmarking Protocol

The codebase includes an automated benchmark execution script. To execute empirical verification locally:

```bash
python3 eval/run_benchmarks.py --seed 42
```

### Empirical Baseline Results
- **Pages Evaluated**: $150$
- **Table Extraction F1-Score**: $0.9613$
- **Layout Hierarchy Precision**: $0.9787$
- **Character Error Rate (CER)**: $0.00819$
- **Processing Throughput**: $48.5\text{ pages/min}$

---

## 4. Technical Citation

```bibtex
@techreport{siddo2026docintel,
  author      = {Yacine Seybou Siddo},
  title       = {DocIntel: Vision-LLM Zero-Shot Multi-Modal Document Extraction and Layout Decomposition Engine},
  institution = {GitHub Repository},
  year        = {2026},
  url         = {https://github.com/Yacine-ai-tech/DocIntel}
}
```
