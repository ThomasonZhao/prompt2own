#!/usr/bin/env bash
# One-time setup on a vast.ai VM instance (template "Ubuntu 22.04 VM", vms_enabled=true).
# Usage: bash scripts/vast_setup.sh        (from the repo root, as a sudo-capable user)
set -euo pipefail

echo "== 1. kernel + docker checks (fail fast: if these fail, pick another host)"
sudo sysctl -w vm.mmap_rnd_bits=28
echo "vm.mmap_rnd_bits=28" | sudo tee /etc/sysctl.d/99-cybergym.conf >/dev/null
docker run --rm hello-world >/dev/null && echo "docker OK"
df -h / | tail -1
nproc; free -g | head -2

echo "== 2. system packages"
sudo apt-get update -qq
sudo apt-get install -y -qq tmux git git-lfs jq python3-venv python3-pip curl
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

echo "== 3. node + claude code (host copy; workers inside task containers follow docs/HARNESS.md)"
if ! command -v node >/dev/null; then
  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
  sudo apt-get install -y -qq nodejs
fi
sudo npm install -g @anthropic-ai/claude-code
claude --version

echo "== 4. python env"
uv venv && . .venv/bin/activate
uv pip install -e '.[dev]'
pytest -q

echo "== 5. harness"
mkdir -p third_party
[ -d third_party/cybergym-e2e ] || git clone https://github.com/sunblaze-ucb/cybergym-e2e third_party/cybergym-e2e
uv pip install tomli tomli_w anthropic openai boto3 httpx huggingface_hub docker
docker pull ubuntu/squid:latest

echo "== done. Next (M0): accept dataset terms on Hugging Face, set HF_TOKEN in .env,"
echo "   download metadata, implement scripts/sample_tasks.py:load_index, sample, then pull images"
echo "   for the sampled tasks only. Start the firewall: (cd third_party/cybergym-e2e/scripts && python -m firewall start)"
