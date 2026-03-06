# BoxCar Ride-Sharing Simulation

A discrete-event simulation (DES) model for analyzing ride-sharing system performance in Squareshire. This project evaluates driver and rider satisfaction metrics under various operational scenarios.

## Diagrams

- <a href="https://htmlpreview.github.io/?https://github.com/VanceF-21/BoxCar-RideSharing-Simulation/blob/main/assets/driver_rider_flowchart.html" target="_blank">Driver & Rider Flowchart</a> — Interactive flowchart illustrating the driver and rider lifecycle in the simulation.

## Project Structure

```
boxcar_simulation/
├── src/                    # Core simulation modules
│   ├── __init__.py
│   ├── entities.py         # Driver, Rider entity classes
│   ├── events.py           # Event system
│   ├── simulation.py       # Simulation engine
│   ├── matching.py         # Matching algorithms
│   ├── statistics.py       # Statistics collection
│   ├── logger.py           # Logging utility
│   └── utils.py            # Helper functions
├── analysis/               # Data analysis modules
│   ├── __init__.py
│   ├── data_analysis.py    # Input data analysis
│   └── output_analysis.py  # Output results analysis
├── config.py               # Configuration loader
├── config.json             # Configuration parameters (EDIT THIS)
├── main.py                 # Main entry point
├── data/                   # Input data files
├── output/                 # Output results
└── requirements.txt        # Dependencies
```

## Quick Start

### Install Dependencies
```bash
pip install -r requirements.txt
```

### Run Simulation

Basic run:
```bash
python main.py 
```

Specify scenario:
```bash
python main.py --scenario baseline --replications 10
```

Data-driven scecario:
```bash
python main.py --scenario data-driven --replications 10
```

Compare 2 scenarios:
```bash
python main.py --compare
```

### Command Line Arguments

| Argument | Description | Default |
|----------|-------------|---------|
| `--scenario, -s` | Select scenario (baseline, high_demand, etc.) | baseline |
| `--replications, -r` | Number of experiment replications | 10 |
| `--time, -t` | Simulation time (hours) | 1000 |
| `--matching, -m` | Matching algorithm (nearest, fifo, zoned, batch) | nearest |
| `--compare, -c` | Compare all scenarios | False |
| `--verbose, -v` | Enable detailed output | False |
| `--output, -o` | Output directory | ./output |
| `--seed` | Random seed | 42 |

## Configuration Parameters

All parameters are stored in `config.json`. Modify this file to customize the simulation.

### Simulation Settings

| Parameter | Path | Description | Default | Unit |
|-----------|------|-------------|---------|------|
| `simulation_time` | `simulation.simulation_time` | Total simulation duration | 1000.0 | hours |
| `warmup_time` | `simulation.warmup_time` | Warm-up period (excluded from statistics) | 5.0 | hours |
| `random_seed` | `simulation.random_seed` | Seed for reproducibility | 42 | - |
| `verbose` | `simulation.verbose` | Enable detailed console output | false | - |

### Map Settings

| Parameter | Path | Description | Default | Unit |
|-----------|------|-------------|---------|------|
| `size` | `map.size` | Square map side length | 20.0 | miles |

### Driver Parameters

| Parameter | Path | Description | Default | Unit |
|-----------|------|-------------|---------|------|
| `arrival_rate` | `driver.arrival_rate` | Driver arrival rate (Poisson process λ) | 3.0 | drivers/hour |
| `availability_min` | `driver.availability_min` | Minimum availability duration | 5.0 | hours |
| `availability_max` | `driver.availability_max` | Maximum availability duration | 8.0 | hours |

**Note**: Driver availability follows a Uniform distribution U(min, max). The inter-arrival time follows an Exponential distribution with rate λ.

### Rider Parameters

| Parameter | Path | Description | Default | Unit |
|-----------|------|-------------|---------|------|
| `arrival_rate` | `rider.arrival_rate` | Rider arrival rate (Poisson process λ) | 30.0 | riders/hour |
| `patience_rate` | `rider.patience_rate` | Abandonment rate parameter | 5.0 | /hour |

**Note**: Rider patience (time before abandonment) follows an Exponential distribution with rate λ. A `patience_rate` of 5.0 means an average patience of 1/5 = 0.2 hours = 12 minutes.

### Trip Parameters

| Parameter | Path | Description | Default | Unit |
|-----------|------|-------------|---------|------|
| `avg_speed` | `trip.avg_speed` | Average vehicle speed | 20.0 | mph |
| `time_variation` | `trip.time_variation` | Trip time variation coefficient | 0.2 | - |

### Fare Parameters

| Parameter | Path | Description | Default | Unit |
|-----------|------|-------------|---------|------|
| `base_fare` | `fare.base_fare` | Base fare per trip | 3.0 | £ |
| `per_mile_rate` | `fare.per_mile_rate` | Rate per mile traveled | 2.0 | £/mile |
| `petrol_cost_per_mile` | `fare.petrol_cost_per_mile` | Fuel cost per mile (driver expense) | 0.20 | £/mile |

**Fare Calculation**: `Total Fare = base_fare + per_mile_rate × distance`

**Driver Profit**: `Profit = Total Fare - petrol_cost_per_mile × distance`

## Scenarios

Scenarios are predefined parameter combinations in `config.json`. Each scenario overrides specific parameters from the defaults.

| Scenario | Description | Key Changes |
|----------|-------------|-------------|
| `baseline` | Default BoxCar assumptions | Standard parameters |
| `high_demand` | 50% more riders | `rider.arrival_rate: 45.0` |
| `more_drivers` | 67% more drivers | `driver.arrival_rate: 5.0` |
| `longer_patience` | Riders more patient (avg 20 min) | `rider.patience_rate: 3.0` |
| `faster_traffic` | 25% faster average speed | `trip.avg_speed: 25.0` |
| `surge_pricing` | Higher fares during peak | `base_fare: 5.0, per_mile_rate: 3.0` |
| `data_driven` | Parameters from real data analysis | Estimated from data files |

### Adding Custom Scenarios

Add a new scenario in `config.json` under the `scenarios` section:

```json
"scenarios": {
    "my_custom_scenario": {
        "_description": "My custom scenario description",
        "driver": {"arrival_rate": 4.0},
        "rider": {"arrival_rate": 40.0, "patience_rate": 4.0}
    }
}
```

Then run:
```bash
python main.py --scenario my_custom_scenario
```

## Performance Metrics

### Rider Satisfaction
- **Abandonment Rate**: Percentage of riders who leave before getting matched
- **Average Waiting Time**: Mean time from rider arrival to pickup

### Driver Satisfaction
- **Average Hourly Earnings**: Mean profit per hour of availability
- **Gini Coefficient**: Measure of earnings inequality (0 = perfect equality, 1 = maximum inequality)
- **Utilization Rate**: Percentage of time drivers spend on trips vs. idle


