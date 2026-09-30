"""Execute the Editor's offline check against a fresh candidate copy."""
import json
import os
import runpy
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from isolation import filesystem_fence, syscall_fence, python_paths


def main():
    request = json.load(sys.stdin)
    root = Path(request['candidate']).resolve()
    script = Path(request['script']).resolve()
    scratch = Path(request['scratch']).resolve()
    sys.path = [str(root)] + [p for p in sys.path if p and
                (str(Path(sys.base_prefix) / 'lib') in p or
                 str(Path(sys.prefix) / 'lib') in p or p.startswith('/usr/lib/'))]
    sys.dont_write_bytecode = True
    os.chdir(scratch)
    os.environ.update(CANDIDATE_DIR=str(root), TMPDIR=str(scratch))
    if request['isolation']:
        syscall_fence(network=False)
        filesystem_fence(python_paths() + [root, script], [scratch])
    calls = set()

    def trace(frame, event, arg):
        path = Path(frame.f_code.co_filename)
        if event == 'call' and path.is_absolute() and root in path.parents and frame.f_code.co_name != '<module>':
            calls.add(str(path.relative_to(root)) + ':' + frame.f_code.co_name)
        return trace

    completed = False
    sys.settrace(trace)
    try:
        try:
            runpy.run_path(str(script), run_name='__main__')
        except SystemExit as exc:
            if exc.code not in (None, 0):
                raise
        completed = True
    finally:
        sys.settrace(None)
        Path(request['receipt']).write_text(json.dumps({'completed': completed, 'candidate_functions': sorted(calls)}))


if __name__ == '__main__':
    main()
