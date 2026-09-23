# Raspberry Pi setup — rETH Basis Research Daemon

Run this read-only watcher on a Raspberry Pi so it keeps collecting while your
desktop is off. **No wallet. No private keys. No trading.**

## What you need

- Raspberry Pi **4 or 5** recommended (2GB+ RAM; 4GB nicer)
- **64-bit** Raspberry Pi OS (Bookworm) with internet
- MicroSD card (16GB+)
- Power supply
- Optional: Ethernet (more stable than Wi‑Fi)

Python **3.11+** is fine (Pi OS default).

## One-time setup (on the Pi)

### 1. Update the Pi and install git

```bash
sudo apt update
sudo apt install -y git
```

### 2. Download the project

```bash
cd ~
git clone https://github.com/novaheic/rETHArbi.git
cd rETHArbi
```

### 3. Run the installer

```bash
chmod +x scripts/*.sh
./scripts/setup_pi.sh
```

This installs packages, creates `.venv`, creates `.env`, and runs **one test**.

### 4. (Recommended) Set a better Ethereum RPC

```bash
nano .env
```

Change:

```text
ETH_RPC_HTTP=https://ethereum.publicnode.com
```

to an Alchemy / Infura / QuickNode HTTPS URL if you have one.  
PublicNode can work, but paid/free API keys are more reliable for weeks of collecting.

Save: `Ctrl+O`, Enter, then `Ctrl+X`.

### 5. Install auto-start (survives reboot)

```bash
sudo ./scripts/install_pi_service.sh
```

The daemon now:

- starts when the Pi boots
- restarts if it crashes
- keeps running after you disconnect SSH

## Daily checks

```bash
sudo systemctl status reth-basis
tail -f ~/rETHArbi/logs/daemon.log
ls -lh ~/rETHArbi/data/reth_basis.db
```

Open reports (if you copy them off the Pi):

- `~/rETHArbi/reports/dashboard.html`
- `~/rETHArbi/reports/daily_report.txt`

## Update the code later

```bash
cd ~/rETHArbi
sudo systemctl stop reth-basis
git pull
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl start reth-basis
```

## Power / network tips

- Prefer a proper USB‑C power supply (avoid flaky phone chargers)
- Prefer Ethernet
- Don’t unplug without `sudo shutdown now` when possible
- Collection pauses if the Pi loses power or internet; it resumes when back

## What happens if the Pi reboots?

systemd starts `reth-basis` again automatically. Old observations stay in
`data/reth_basis.db`.

## Stop / uninstall

```bash
sudo systemctl stop reth-basis
sudo systemctl disable reth-basis
```
