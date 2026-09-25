# Raspberry Pi setup — rETH Basis Research Daemon

Run this read-only watcher on a Raspberry Pi so it keeps collecting while your
desktop is off. **No wallet. No private keys. No trading.**

## What you need

- Raspberry Pi **4 or 5** recommended (2GB+ RAM; 4GB nicer)
- **64-bit** Raspberry Pi OS (Bookworm or Trixie) with internet
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

This installs packages (including `libopenblas-dev` for Trixie/Bookworm), creates
`.venv`, creates `.env`, and runs **one test**.

> Note: older scripts used `libatlas-base-dev`, which is gone on Raspberry Pi OS
> Trixie. Current `setup_pi.sh` uses `libopenblas-dev` instead.

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

Optional for public RPC:

```text
POLL_INTERVAL_SECONDS=60
```

Save: `Ctrl+O`, Enter, then `Ctrl+X`.

### 5. Install auto-start (survives reboot)

```bash
sudo ./scripts/install_pi_service.sh
```

This enables **both**:

- `reth-basis` — collector / paper simulator
- `reth-dashboard` — LAN check-in UI on port **8080**

They:

- start when the Pi boots
- restart if they crash
- keep running after you disconnect SSH

## Check-in dashboard (primary)

From your PC or phone on the same Wi‑Fi/LAN:

```text
http://rethpi.local:8080
```

Or use the Pi’s IP:

```text
http://192.168.x.x:8080
```

The page auto-refreshes every 60s and shows:

- live basis / net edge / gas
- interactive charts (basis, rates, P&amp;L, histogram)
- strategy leaderboard and recent paper trades
- window chips: 24h / 7d / 30d / all

**LAN only, no login.** Do not port-forward this to the public internet.

Manual run:

```bash
cd ~/rETHArbi
source .venv/bin/activate
python -m src.dashboard
```

## Daily checks

```bash
sudo systemctl status reth-basis
sudo systemctl status reth-dashboard
tail -f ~/rETHArbi/logs/daemon.log
ls -lh ~/rETHArbi/data/reth_basis.db
```

Offline / copied snapshots (fallback):

- `~/rETHArbi/reports/dashboard.html`
- `~/rETHArbi/reports/daily_report.txt`

## Update the code later

```bash
cd ~/rETHArbi
sudo systemctl stop reth-basis reth-dashboard
git pull
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl start reth-basis reth-dashboard
```

## Power / network tips

- Prefer a proper USB‑C power supply (avoid flaky phone chargers)
- Prefer Ethernet
- Don’t unplug without `sudo shutdown now` when possible
- Collection pauses if the Pi loses power or internet; it resumes when back

## What happens if the Pi reboots?

systemd starts `reth-basis` and `reth-dashboard` again automatically. Old
observations stay in `data/reth_basis.db`.

## Stop / uninstall

```bash
sudo systemctl stop reth-basis reth-dashboard
sudo systemctl disable reth-basis reth-dashboard
```
