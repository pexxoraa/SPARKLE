# SPARKLE benchmark evidence

Synthetic corpus and scripted agent/tool harness. No live model or real embedding quality claim.

| Retriever | Recall@1 | Recall@3 | Recall@5 | MRR |
|---|---:|---:|---:|---:|
| lexical | 0.625000 | 0.750000 | 0.750000 | 0.718750 |
| semantic_test_double | 0.562500 | 0.687500 | 0.687500 | 0.674479 |
| hybrid_test_double | 0.625000 | 0.750000 | 0.750000 | 0.736111 |

Dataset: sparkle-retrieval-1; queries: 16; sources: 12; chunks: 14.

Macro Recall@K = relevant chunks retrieved / all judged relevant chunks; Hit@K = any relevant hit; MRR = reciprocal first relevant rank within top 50 (zero if absent).

| Query class | Lexical MRR | Semantic-double MRR | Hybrid-double MRR |
|---|---:|---:|---:|
| distractor | 0.750000 | 0.750000 | 0.750000 |
| language_variation | 0.000000 | 0.000000 | 0.000000 |
| literal | 1.000000 | 1.000000 | 1.000000 |
| multiple | 1.000000 | 1.000000 | 1.000000 |
| semantic_paraphrase | 0.000000 | 0.097222 | 0.092593 |
| title | 1.000000 | 1.000000 | 1.000000 |
| title_body_ambiguity | 1.000000 | 1.000000 | 1.000000 |
| unicode | 1.000000 | 0.666667 | 1.000000 |

## Agent protocol/outcome harness

Tasks: 12; pass rate: 100.00%; validation pass rate: 100.00%.

| Agent | Tasks | Passed |
|---|---:|---:|
| coding | 3 | 3 |
| learning | 3 | 3 |
| personal | 3 | 3 |
| research | 3 | 3 |

Validation: {"validated": 12, "rejected": 0, "inconclusive": 0}

Negative controls: {"wrong_known_answer": "rejected", "missing_evidence": "inconclusive", "subjective_quality": "inconclusive"}

Execution success is not outcome correctness. Scripted choices do not demonstrate autonomous tool selection, teaching, research synthesis or coding quality.

Level 3 BLOCKED. Deployment FROZEN. Real semantic and NVIDIA live evaluation pending.


## Retrieval failures at K=5

lexical: [{"id": "paraphrase", "class": "semantic_paraphrase"}, {"id": "paraphrase2", "class": "semantic_paraphrase"}, {"id": "cross_language", "class": "language_variation"}, {"id": "synonym", "class": "semantic_paraphrase"}]
semantic_test_double: [{"id": "paraphrase", "class": "semantic_paraphrase"}, {"id": "paraphrase2", "class": "semantic_paraphrase"}, {"id": "cross_language", "class": "language_variation"}, {"id": "synonym", "class": "semantic_paraphrase"}, {"id": "accent", "class": "unicode"}]
hybrid_test_double: [{"id": "paraphrase", "class": "semantic_paraphrase"}, {"id": "paraphrase2", "class": "semantic_paraphrase"}, {"id": "cross_language", "class": "language_variation"}, {"id": "synonym", "class": "semantic_paraphrase"}]

Context metrics (before model answer): {"metrics": {"recall@1": 0.625, "hit@1": 0.6875, "recall@3": 0.75, "hit@3": 0.75, "recall@5": 0.75, "hit@5": 0.75, "mrr": 0.71875}, "max_bytes": 12000, "max_knowledge_items": 5, "observed_max_bytes": 549, "answer_quality": "not_measured"}
