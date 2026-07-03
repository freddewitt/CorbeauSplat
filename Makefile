test:
	.venv/bin/pip install pytest && .venv/bin/pip uninstall -y pytest-qt && .venv/bin/python -m pytest tests/test_ply_cleaner.py -v
