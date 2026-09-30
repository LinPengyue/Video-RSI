"""Small offline candidate checks. No Gate data or model credentials."""
import json
import os
import subprocess
import tempfile
from pathlib import Path
from .common import write_json
from .runner import copy_candidate, run_item, stop_process
from .services import Services, OfflineProvider


def candidate_files(root):
    root = Path(root)
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*')
            if p.is_file() and not any(part in ('__pycache__', '.pytest_cache', '.git')
                                      for part in p.relative_to(root).parts)}


def check_candidate_execution(candidate, check_script, row, config, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='candidate-check-') as temp:
        temp = Path(temp)
        services = Services(row, {}, config, temp / 'services', OfflineProvider())
        startup = run_item(candidate, row, services, config, check_only=True)
        result = {'startup': startup['status'], 'executed_files': startup.get('executed_files', []),
                  'tool_check': 'not_run', 'passed': False, 'model_calls': 0}
        if startup['status'] != 'startup_ok':
            result['error'] = startup.get('error', 'candidate import failed')
        elif not Path(check_script).is_file():
            result['tool_check'] = 'missing'
            result['error'] = 'Editor must save analysis/tool_check.py before Gate'
        else:
            snapshot = temp / 'candidate'
            copy_candidate(candidate, snapshot)
            script = temp / 'tool_check.py'
            script.write_bytes(Path(check_script).read_bytes())
            scratch = temp / 'scratch'
            scratch.mkdir()
            receipt = scratch / 'receipt.json'
            request = {'candidate': str(snapshot), 'script': str(script), 'scratch': str(scratch),
                       'receipt': str(receipt), 'isolation': config['execution']['linux_isolation']}
            with tempfile.TemporaryFile(mode='w+b') as log:
                process = subprocess.Popen(
                    [config['execution']['python'], '-I', str(Path(__file__).with_name('check_worker.py'))],
                    stdin=subprocess.PIPE, stdout=log, stderr=log, text=True, start_new_session=True,
                    env={'PATH': '/usr/bin:/bin', 'LANG': 'C.UTF-8', 'PYTHONDONTWRITEBYTECODE': '1'})
                timed_out = False
                try:
                    process.communicate(json.dumps(request), timeout=min(120, config['solver']['timeout_seconds']))
                except subprocess.TimeoutExpired:
                    timed_out = True
                    stop_process(process)
                    process.wait()
                log.seek(0, os.SEEK_END)
                log.seek(max(0, log.tell() - 16000))
                result['tool_check_output'] = log.read().decode(errors='replace')
            record = json.loads(receipt.read_text()) if receipt.is_file() else {}
            result['candidate_functions'] = record.get('candidate_functions', [])
            result['tool_check'] = ('timeout' if timed_out else 'passed' if
                                    process.returncode == 0 and record.get('completed') and
                                    result['candidate_functions'] else 'failed')
            result['passed'] = result['tool_check'] == 'passed'
            result['exit_code'] = process.returncode
        write_json(output / 'engineering_check.json', result)
        return result
