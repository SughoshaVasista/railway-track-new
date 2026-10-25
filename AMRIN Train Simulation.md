# AMRIN Train Simulation

This directory contains the railway switching simulation and its local decision receiver. It is simulation and decision-support software, not live railway signalling control.

## Setup

On Ubuntu, install SUMO with `sudo apt-get install sumo sumo-tools sumo-doc`. Install Python dependencies with `python3 -m pip install traci requests flask` when they are not already available. Verify with `sumo --version` and `netconvert --version`.

Generate the SUMO network from this directory:

```bash
netconvert --node-files=nodes.nod.xml --edge-files=edges.edg.xml --output-file=network.net.xml
sumo -c sim.sumocfg --no-step-log
# Optional GUI sanity check:
sumo-gui -c sim.sumocfg
```

## Decision tests and scenarios

Run the standalone tests with:

```bash
python3 -m unittest discover -s . -p 'test_*.py'
for scenario in clear_clear s3_on_A s2_on_A_B_occupied both_s3; do
  python3 scenario.py "$scenario" > "demo/${scenario}.json"
done
```

The expected outcomes are `MAINTAIN / Track A`, `SWITCH / Track B`, `MAINTAIN / Track A`, and `EMERGENCY_STOP / no target`, respectively. The decision payload contains `rules_checked`, which is consumed by the frontend.

## Local POST demo

Start the stub in one terminal:

```bash
python3 tiny_stub.py
```

Then use the pure-Python fallback in another terminal:

```bash
python3 plan_b_stub.py s3_on_A
```

The fallback produces the same JSON schema as the SUMO controller and is the supported path when SUMO is unavailable. With SUMO, run `python3 controller.py s3_on_A`; replace `ENDPOINT` in `controller.py` with the real backend URL when one exists.
