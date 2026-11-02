"""Execute all four portfolio notebooks with this Python environment."""
import sys
import os
from pathlib import Path
import nbformat
from nbclient import NotebookClient
from jupyter_client import KernelManager

ROOT = Path(__file__).resolve().parents[1]


def main():
    # Keep kernel caches local and out of the published project.
    for key, path in {
        'IPYTHONDIR': ROOT / '.local_archive' / 'ipython',
        'JUPYTER_RUNTIME_DIR': ROOT / '.local_archive' / 'jupyter_runtime',
        'MPLCONFIGDIR': ROOT / '.mplconfig',
    }.items():
        path.mkdir(parents=True, exist_ok=True)
        os.environ[key] = str(path)
    for path in sorted((ROOT / 'notebooks').glob('*.ipynb')):
        print(f'Running {path.name}', flush=True)
        notebook = nbformat.read(path, as_version=4)
        manager = KernelManager(kernel_name='python3')
        # Avoid accidentally using a different globally installed Python kernel.
        manager.kernel_spec.argv = [sys.executable, '-m', 'ipykernel_launcher', '-f', '{connection_file}']
        client = NotebookClient(notebook, km=manager, timeout=600,
                                resources={'metadata': {'path': str(ROOT)}})
        try:
            client.execute()
        finally:
            if client.kc is not None:
                client.kc.stop_channels()
            if manager.has_kernel:
                manager.shutdown_kernel(now=True)
            manager.cleanup_resources()
        nbformat.validate(notebook)
        nbformat.write(notebook, path)
        print(f'OK {path.name}', flush=True)


if __name__ == '__main__':
    main()
