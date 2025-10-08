echo Setting up development environment...

git config core.hooksPath .githooks
echo Git hooks path configured.

echo Installing dependencies...
pip install -r requirements.txt

echo Setup completed successfully!
