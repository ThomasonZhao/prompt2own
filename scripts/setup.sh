#!/usr/bin/env bash
# One-time host setup: Ubuntu 22.04 VM (not a container) with Docker and sudo.
# Usage: bash scripts/setup.sh        (from the repo root)
set -euo pipefail

echo "== 1. kernel + docker checks (the harness needs a VM; fail fast here)"
sudo sysctl -w vm.mmap_rnd_bits=28
echo "vm.mmap_rnd_bits=28" | sudo tee /etc/sysctl.d/99-cybergym.conf >/dev/null
docker run --rm hello-world >/dev/null && echo "docker OK"
df -h / | tail -1
nproc; free -g | head -2

echo "== 2. system packages"
sudo apt-get update -qq
sudo apt-get install -y -qq tmux git git-lfs jq python3-venv python3-pip curl rsync
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

echo "== 3. node + claude code (host copy; workers get the harness's pinned version inside task containers)"
if ! command -v node >/dev/null; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
  sudo apt-get install -y -qq nodejs
fi
sudo npm install -g @anthropic-ai/claude-code
claude --version

echo "== 4. official harness (pinned commit)"
mkdir -p third_party
[ -d third_party/cybergym-e2e ] || git clone https://github.com/sunblaze-ucb/cybergym-e2e third_party/cybergym-e2e
git -C third_party/cybergym-e2e checkout -q d0ae0f02e76ebc084389bf21e755f4b41ac9765a
docker pull ubuntu/squid:latest

echo "== 5. python env (3.11) + tests"
uv venv --python 3.11 && . .venv/bin/activate
uv pip install -e '.[dev]'
uv pip install tomli tomli_w anthropic openai boto3 httpx huggingface_hub docker   # harness deps
pytest -q

echo "== done. Next: accept the CyberGym-E2E dataset terms on Hugging Face, fill .env (see .env.example),"
echo "   then: python scripts/fetch_sampled.py   (data + images for the 33 frozen tasks)"
echo "   and start the firewall: (cd third_party/cybergym-e2e/scripts && python -m firewall start --domain openrouter.ai)"
