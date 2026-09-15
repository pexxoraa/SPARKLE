"""Run with PYTHONPATH=src python -m benchmarks.run --output-dir PATH."""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from benchmarks.retrieval import run_retrieval
from benchmarks.agents import run_agents


def benchmark_implementation_files(
    root_dir: Path | None = None,
) -> tuple[str, ...]:
    """Return the complete repository code/config surface that can affect a run."""

    root = root_dir or Path(__file__).resolve().parents[1]
    paths = {
        path.relative_to(root).as_posix()
        for package in (root / 'src' / 'sparkle', root / 'benchmarks')
        for path in package.rglob('*.py')
        if path.is_file() and not path.is_symlink()
    }
    for relative in (
        'application/config.json',
        'ai_environment/configurations/models.json',
        'pyproject.toml',
    ):
        path = root / relative
        if path.is_file() and not path.is_symlink():
            paths.add(relative)
    return tuple(sorted(paths))


BENCHMARK_IMPLEMENTATION_FILES = benchmark_implementation_files()


def implementation_hashes(root_dir: Path | None = None) -> dict[str, str]:
    """Hash every repository implementation/config file that can affect a run."""

    root = root_dir or Path(__file__).resolve().parents[1]
    files = (
        BENCHMARK_IMPLEMENTATION_FILES
        if root_dir is None
        else benchmark_implementation_files(root)
    )
    return {
        path: hashlib.sha256((root / path).read_bytes()).hexdigest()
        for path in files
    }


def run_all():
    with tempfile.TemporaryDirectory() as directory:
        root=Path(directory)
        hashes=implementation_hashes()
        return {'schema':'SPARKLE-BENCHMARK/1', 'implementation_sha256':hashes, 'retrieval':run_retrieval(root),
                'agents':run_agents(root/'agents'), 'level_3':'LOCAL_READY_REMOTE_ACCEPTANCE_BLOCKED', 'deployment':'FROZEN'}


def markdown(report):
    lines=['# SPARKLE benchmark evidence','',
           'Synthetic corpus and scripted agent/tool harness. No live model or real embedding quality claim.','',
           '| Retriever | Recall@1 | Recall@3 | Recall@5 | MRR |','|---|---:|---:|---:|---:|']
    for name,result in report['retrieval']['systems'].items():
        m=result['metrics'];lines.append(f"| {name} | {m['recall@1']:.6f} | {m['recall@3']:.6f} | {m['recall@5']:.6f} | {m['mrr']:.6f} |")
    lines+=['',f"Dataset: {report['retrieval']['dataset_version']}; queries: {report['retrieval']['query_count']}; sources: {report['retrieval']['source_count']}; chunks: {report['retrieval']['chunk_count']}.",'',report['retrieval']['definition'],'',
            '| Query class | Lexical MRR | Semantic-double MRR | Hybrid-double MRR |','|---|---:|---:|---:|']
    for cls in report['retrieval']['systems']['lexical']['by_class']:
        vals=[s['by_class'][cls]['mrr'] for s in report['retrieval']['systems'].values()]
        lines.append('| '+cls+' | '+' | '.join(f'{v:.6f}' for v in vals)+' |')
    lines+=['','## Agent protocol/outcome harness','',
            f"Tasks: {report['agents']['task_count']}; pass rate: {report['agents']['pass_rate']:.2%}; validation pass rate: {report['agents']['validation_pass_rate']:.2%}.",
            '', '| Agent | Tasks | Passed |','|---|---:|---:|']
    for agent,row in report['agents']['per_agent'].items():lines.append(f"| {agent} | {row['tasks']} | {row['passed']} |")
    lines+=['','Validation: '+json.dumps(report['agents']['validation_counts']),
            '','Negative controls: '+json.dumps({k:v['validation_status'] for k,v in report['agents']['negative_controls'].items()}),
            '', 'Execution success is not outcome correctness. Scripted choices do not demonstrate autonomous tool selection, teaching, research synthesis or coding quality.',
            '', 'Level 3 local worker readiness is verified; trusted remote/restart acceptance remains blocked. Deployment FROZEN. The latest live Nemotron evidence remains 3/12 and is not rerun by this deterministic benchmark.','']
    lines += ['', '## Retrieval failures at K=5', '']
    for name,system in report['retrieval']['systems'].items():
        lines.append(name+': '+json.dumps(system['failures_at_5']))
    lines += ['', 'Context metrics (before model answer): '+json.dumps(report['retrieval']['context']), '']
    return '\n'.join(lines)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args();report=run_all();args.output_dir.mkdir(parents=True,exist_ok=True)
    (args.output_dir/'results.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    (args.output_dir/'REPORT.md').write_text(markdown(report))
    print(markdown(report))

if __name__=='__main__':main()
