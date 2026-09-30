"""Persistent driver for candidate editing, evaluation, and acceptance."""
import concurrent.futures
import fcntl
import json
import os
import tempfile
import shutil
from pathlib import Path

from .common import read_json, read_jsonl, write_json, public_item, validate_config, GATE_POLICY
from .editor import DeepSeekEditor
from .runner import copy_candidate, run_item
from .services import Services, LocalOCR
from .frame_cost import cost_usage, FRAME_METRIC
from .gate_feedback import POLICY, aggregate_feedback
from .engineering import candidate_files, check_candidate_execution


def indexed(rows):
    result = {}
    for row in rows:
        key = row["sample_id"]
        if not isinstance(key, str) or not key or key in result:
            raise ValueError("missing or duplicate sample ID")
        result[key] = row
    return result


def gate_decision(parent, candidate, labels, config):
    if config['gate']['policy'] != GATE_POLICY:
        raise ValueError('Gate policy mismatch; do not silently rescore an older protocol')
    p, c = indexed(parent), indexed(candidate)
    if set(p) != set(c) or set(p) != set(labels) or not p:
        return {"status": "INCOMPLETE", "accepted": False, "reason": "paired coverage mismatch"}
    if any(row.get("status") == "engineering_error" for row in parent + candidate):
        return {"status": "ENGINEERING_FAILED", "accepted": False, "reason": "candidate or parent did not execute normally"}


    p_correct = {key: p[key].get("status") == "answered" and p[key].get("answer") == labels[key] for key in p}
    c_correct = {key: c[key].get("status") == "answered" and c[key].get("answer") == labels[key] for key in c}
    pn, cn, n = sum(p_correct.values()), sum(c_correct.values()), len(p)
    pu, cu = [cost_usage(row) for row in parent], [cost_usage(row) for row in candidate]
    pf, cf = sum(u["qwen_frames"] for u in pu), sum(u["qwen_frames"] for u in cu)
    ceiling = config["gate"]["max_mean_frames"]


    accuracy_gain = cn > pn and 100 * cf <= 110 * pf
    efficiency_gain = (pn - 1 <= cn <= pn and pf > 0 and 100 * cf <= 80 * pf)
    accepted = (accuracy_gain or efficiency_gain) and (ceiling is None or cf / n <= ceiling)
    return {"status": "ACCEPTED" if accepted else "REJECTED", "accepted": accepted, "n": n,
            "gate_policy": GATE_POLICY,
            "accuracy_branch_passed": accuracy_gain, "efficiency_branch_passed": efficiency_gain,
            "frame_metric": FRAME_METRIC,
            "parent_qwen_failed_frames": sum(u["qwen_failed_frames"] for u in pu),
            "candidate_qwen_failed_frames": sum(u["qwen_failed_frames"] for u in cu),
            "parent_qwen_submitted_frames": sum(u["qwen_submitted_frames"] for u in pu),
            "candidate_qwen_submitted_frames": sum(u["qwen_submitted_frames"] for u in cu),
            "parent_ocr_frames": sum(u["ocr_frames"] for u in pu),
            "candidate_ocr_frames": sum(u["ocr_frames"] for u in cu),
            "parent_correct": pn, "candidate_correct": cn, "accuracy_delta": (cn - pn) / n,
            "fix": sum(c_correct[k] and not p_correct[k] for k in p),
            "harm": sum(p_correct[k] and not c_correct[k] for k in p), "net": cn - pn,
            "parent_mean_frames": pf / n, "candidate_mean_frames": cf / n,
            "parent_invalid": sum(row.get("status") != "answered" for row in parent),
            "candidate_invalid": sum(row.get("status") != "answered" for row in candidate),
            "parent_qwen_calls": sum(row["usage"].get("qwen_calls", 0) for row in parent),
            "candidate_qwen_calls": sum(row["usage"].get("qwen_calls", 0) for row in candidate)}


def initialize(root, seed, config, datasets):
    root = Path(root).resolve()
    if root.exists():
        raise ValueError("new run directory must not already exist")
    validate_config(config)
    validate_datasets(datasets)
    gate_items, gate_oracle = load_split(datasets, "gate")
    root.mkdir(parents=True)

    frozen_gate = root / 'private_gate_inputs.json'
    write_json(frozen_gate, {'items': gate_items, 'oracle': list(gate_oracle.values())})
    datasets = dict(datasets, gate={'snapshot': str(frozen_gate)})
    write_json(root / 'feedback_policy.json', {'policy': POLICY})
    write_json(root / 'version_numbering.json', {'policy': 'accepted_revision_v1'})
    copy_candidate(seed, root / "versions/initial_harness")
    write_json(root / "effective_config.json", config)
    write_json(root / "datasets.json", datasets)
    write_json(root / "current.json", {"version": "initial_harness", "generation": 0, "attempt": 0})
    write_json(root / "state.json", {"next_round": 1, "active_round": None})
    return root


def load_split(datasets, name):
    spec = datasets[name]
    snapshot = read_json(spec['snapshot']) if name == 'gate' and 'snapshot' in spec else None
    items = snapshot['items'] if snapshot is not None else read_jsonl(spec["public_items"])
    by_id = indexed(items)
    for item in items:
        public_item(item)
        if "video_path" not in item:
            raise ValueError("public manifest requires host video_path")
    oracle = indexed(snapshot['oracle'] if snapshot is not None else read_jsonl(spec["oracle"]))
    if set(by_id) != set(oracle):
        raise ValueError("public/oracle ID coverage differs")
    for key, row in oracle.items():
        if row.get("answer") not in public_item(by_id[key])["options"]:
            raise ValueError("oracle must explicitly map to an actual option")
    return items, oracle


def validate_datasets(datasets):
    train, _ = load_split(datasets, "train")
    gate, _ = load_split(datasets, "gate")
    if set(indexed(train)) & set(indexed(gate)):
        raise ValueError("train and gate sample IDs overlap")
    train_videos = {str(Path(r["video_path"]).resolve()) for r in train}
    gate_videos = {str(Path(r["video_path"]).resolve()) for r in gate}
    if train_videos & gate_videos:
        raise ValueError("train and gate videos overlap")


class Evolution:
    def __init__(self, root, editor=None, services_factory=None):
        self.root = Path(root).resolve()
        policy = self.root / 'feedback_policy.json'
        if not policy.is_file() or read_json(policy).get('policy') != POLICY:
            raise ValueError('Route feedback policy is incompatible; initialize a new route with init')
        self.config = validate_config(read_json(self.root / "effective_config.json"))
        self.datasets = read_json(self.root / "datasets.json")
        if self.datasets['gate'] != {'snapshot': str(self.root / 'private_gate_inputs.json')}:
            raise ValueError('Gate must use the fixed private snapshot created by init')
        self.editor = editor or DeepSeekEditor(self.config)
        self.ocr = LocalOCR(self.config["services"]["ocr_model_root"])
        self.services_factory = services_factory

    def services(self, row, scratch):
        if self.services_factory:
            return self.services_factory(row, scratch)
        return Services(public_item(row), row, self.config, scratch, ocr=self.ocr)

    def evaluate(self, candidate, rows, output, startup_only=False):
        output = Path(output)
        output.mkdir(parents=True, exist_ok=True)

        def one(pair):
            index, row = pair
            path = output / ("item_%06d.json" % index)
            if path.exists():
                existing = read_json(path)
                if existing["sample_id"] != row["sample_id"]:
                    raise ValueError("cached item order mismatch")
                return existing
            with tempfile.TemporaryDirectory(prefix="full-services-") as temp:
                try:
                    services = self.services(row, temp)
                    result = run_item(candidate, row, services, self.config, check_only=startup_only)
                except Exception as exc:

                    result = {"sample_id": row["sample_id"], "status": "engineering_error", "answer": None, "error_type": type(exc).__name__, "usage": {"frames": 0}}
                write_json(path, result)
                return result

        with concurrent.futures.ThreadPoolExecutor(max_workers=self.config["execution"]["concurrency"]) as pool:
            results = list(pool.map(one, enumerate(rows)))
        write_json(output / "results.json", results)
        return results

    def prepare_learning(self, folder, candidate, rows, oracle, results, feedback):
        workspace = folder / "workspace"
        if not workspace.exists():
            workspace.mkdir()
            copy_candidate(candidate, workspace / "candidate")
            (workspace / "analysis").mkdir()
            index = []
            for number, (row, result) in enumerate(zip(rows, results)):
                evidence = oracle[row["sample_id"]]
                outcome = ("execution_error" if result["status"] != "answered" else "correct" if result["answer"] == evidence["answer"] else "wrong")
                relative = "cases/%06d.json" % number
                record = {"item": public_item(row), "gold_answer": evidence["answer"], "gold_path": evidence.get("gold_path"), "gold_evidence": evidence.get("gold_evidence"), "trajectory": result, "program_outcome": outcome}

                record["analysis_metadata"] = {k: row[k] for k in ("question_type", "dataset") if k in row}
                write_json(workspace / "training" / relative, record)
                index.append({"sample_id": row["sample_id"], "outcome": outcome, "path": relative})
            write_json(workspace / "training/index.json", index)
            write_json(workspace / "lineage_feedback.json", aggregate_feedback(feedback))
            previous = folder.parent / ("round_%03d" % (int(folder.name.rsplit("_", 1)[1]) - 1))
            if (previous / "candidate_snapshot").exists():
                copy_candidate(previous / "candidate_snapshot", workspace / "previous_attempt/candidate")

                for name in ("analysis.md", "edit_plan.md", "edit_summary.md"):
                    source = previous / "workspace/analysis" / name
                    if source.is_file():
                        shutil.copyfile(source, workspace / "previous_attempt" / name)
            (workspace / "SERVICES.md").write_text(Path(__file__).parents[1].joinpath("SERVICES.md").read_text())
            for name in ("DIAGNOSIS.md", "INVESTIGATION.md", "investigate.py"):
                shutil.copyfile(Path(__file__).parents[1] / name, workspace / name)
        return workspace

    def advance(self, rounds=1, continue_plan=False):
        with (self.root / "driver.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for _ in range(rounds):
                result = self.one_round(continue_plan)
                continue_plan = False
                if result["status"] not in ("ACCEPTED", "REJECTED", "NO_CHANGE"):
                    return result
            return result

    def finish_round(self, folder, checkpoint, phase, state, number, result):
        result = dict(result, round=number, current=read_json(self.root / 'current.json')['version'],
                      round_limit_reached=number >= self.config.get('evolution', {}).get('max_rounds', 20))
        write_json(folder / 'round_result.json', result)
        phase['phase'] = 'DONE'
        write_json(checkpoint, phase)
        state.update(next_round=number + 1, active_round=None)
        write_json(self.root / 'state.json', state)
        return result

    def one_round(self, continue_plan=False):
        state = read_json(self.root / "state.json")
        pointer = read_json(self.root / "current.json")
        number = state["active_round"] or state["next_round"]
        limit = self.config.get('evolution', {}).get('max_rounds', 20)
        if number > limit:
            return {'status': 'ROUND_LIMIT_REACHED', 'max_rounds': limit, 'current': pointer['version']}
        folder = self.root / ("rounds/round_%03d" % number)
        folder.mkdir(parents=True, exist_ok=True)
        checkpoint = folder / "phase.json"
        if not checkpoint.exists():
            write_json(checkpoint, {"phase": "TRAIN", "parent": pointer["version"]})
        phase = read_json(checkpoint)
        if phase['phase'] == 'DONE':
            result = read_json(folder / 'round_result.json') if (folder / 'round_result.json').exists() else read_json(folder / 'gate_aggregate.json')
            return self.finish_round(folder, checkpoint, phase, state, number, result)
        state["active_round"] = number
        write_json(self.root / "state.json", state)
        parent = self.root / "versions" / phase["parent"]
        train, train_oracle = load_split(self.datasets, "train")
        workspace = folder / "workspace"
        if hasattr(self.editor, "configure_investigation"):
            self.editor.configure_investigation(train, parent, self.ocr)
        if phase["phase"] == "TRAIN":

            train_results = self.evaluate(parent, train, self.root / "training_cache" / phase["parent"])
            previous = self.root / ("rounds/round_%03d/round_result.json" % (number - 1))
            if not previous.exists():
                previous = previous.with_name('gate_aggregate.json')
            self.prepare_learning(folder, parent, train, train_oracle, train_results, read_json(previous) if previous.exists() else {"status": "initial_parent"})
            phase["phase"] = "ANALYSIS"
            write_json(checkpoint, phase)
        if phase["phase"] == "ANALYSIS":

            for name in ("investigate.py", "INVESTIGATION.md", "DIAGNOSIS.md"):
                shutil.copyfile(Path(__file__).parents[1] / name, workspace / name)
            self.editor.run(workspace, folder / "private_editor", "analysis")
            analysis = workspace / "analysis/analysis.md"
            if not analysis.is_file() or not analysis.read_text().strip():
                raise RuntimeError("editor completed without saved analysis")
            phase["phase"] = "PLAN"
            write_json(checkpoint, phase)
        if phase['phase'] == 'PLAN':
            before = candidate_files(workspace / 'candidate')
            self.editor.run(workspace, folder / 'private_editor', 'plan')
            plan = workspace / 'analysis/edit_plan.md'
            if not plan.is_file() or not plan.read_text().strip():
                raise RuntimeError('plan phase did not save edit_plan.md')
            if candidate_files(workspace / 'candidate') != before:
                raise RuntimeError('plan phase must not edit candidate code')
            phase['phase'] = 'WAIT_PLAN' if self.config['editor'].get('pause_after_plan', False) else 'EDIT'
            write_json(checkpoint, phase)
        if phase['phase'] == 'WAIT_PLAN':
            if not continue_plan:
                return {'status': 'WAIT_PLAN', 'round': number, 'plan': str(workspace / 'analysis/edit_plan.md')}
            phase['phase'] = 'EDIT'
            write_json(checkpoint, phase)
        if phase["phase"] == "EDIT":
            plan = workspace / 'analysis/edit_plan.md'
            if not plan.is_file() or not plan.read_text().strip():
                raise RuntimeError('edit requires a saved nonempty edit_plan.md')
            for name in ("investigate.py", "INVESTIGATION.md", "DIAGNOSIS.md"):
                shutil.copyfile(Path(__file__).parents[1] / name, workspace / name)
            self.editor.run(workspace, folder / "private_editor", "edit")
            phase["phase"] = "CHECK"
            write_json(checkpoint, phase)
        if phase["phase"] == "CHECK":
            if candidate_files(workspace / 'candidate') == candidate_files(parent):
                write_json(folder / 'engineering_check.json', {'candidate_changed': False, 'tool_check': 'skipped_no_change', 'gate_run': False})
                return self.finish_round(folder, checkpoint, phase, state, number,
                                         {'status': 'NO_CHANGE', 'accepted': False})

            snapshot = folder / "candidate_snapshot"
            if not snapshot.exists():
                copy_candidate(workspace / "candidate", snapshot)
            elif candidate_files(snapshot) != candidate_files(workspace / 'candidate'):
                raise RuntimeError('candidate changed after snapshot; do not evaluate a stale copy')
            check = check_candidate_execution(snapshot, workspace / 'analysis/tool_check.py',
                                              public_item(train[0]), self.config, folder)
            if not check['passed']:
                return {"status": "ENGINEERING_FAILED", "round": number, "parent": phase["parent"]}
            phase["phase"] = "GATE"
            write_json(checkpoint, phase)
        if phase["phase"] == "GATE":
            rows, oracle = load_split(self.datasets, "gate")

            parent_results = self.evaluate(parent, rows, folder / "private_gate/parent")
            candidate_results = self.evaluate(folder / "candidate_snapshot", rows, folder / "private_gate/candidate")
            aggregate = gate_decision(parent_results, candidate_results, {k: v["answer"] for k, v in oracle.items()}, self.config)
            write_json(folder / "gate_aggregate.json", aggregate)
            if aggregate["status"] not in ("ACCEPTED", "REJECTED"):
                return aggregate
            phase.update(phase="COMMIT", accepted=aggregate["accepted"])
            write_json(checkpoint, phase)
        if phase["phase"] == "COMMIT":
            current = read_json(self.root / "current.json")
            numbering = self.root / 'version_numbering.json'
            sequential = numbering.is_file()
            if sequential and read_json(numbering).get('policy') != 'accepted_revision_v1':
                raise ValueError('unknown version numbering policy')
            if phase["accepted"]:
                if 'target_version' not in phase:
                    if current['version'] != phase['parent'] and sequential:
                        raise RuntimeError('parent pointer changed before version allocation')
                    generation = current['generation'] + 1 if sequential else number
                    phase.update(target_version='H_S%d' % generation, target_generation=generation)
                    write_json(checkpoint, phase)
                target = phase['target_version']
                if current["version"] not in (phase["parent"], target):
                    raise RuntimeError("parent pointer changed concurrently")
                version = self.root / "versions" / target
                if not version.exists():
                    pending = self.root / "versions" / (target + ".pending")
                    if pending.exists():
                        pending.rename(pending.with_name(target + ".interrupted." + str(os.stat(pending).st_mtime_ns)))
                    copy_candidate(folder / "candidate_snapshot", pending)
                    os.replace(pending, version)
                elif candidate_files(version) != candidate_files(folder / 'candidate_snapshot'):
                    raise RuntimeError('version directory conflicts with accepted candidate')
                pointer = {"version": target, "generation": phase['target_generation']}
                if sequential:
                    pointer['attempt'] = number
                write_json(self.root / "current.json", pointer)
            elif current["version"] != phase["parent"]:
                raise RuntimeError("rejected round must keep its parent")
            phase["phase"] = "DONE"
            write_json(checkpoint, phase)
        return self.finish_round(folder, checkpoint, phase, state, number, read_json(folder / 'gate_aggregate.json'))
