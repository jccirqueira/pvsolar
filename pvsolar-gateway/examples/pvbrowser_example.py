"""
Example: pvbrowser Integration with pvSolar Gateway

This example demonstrates how to use the pvSolar Gateway
to send real-time solar data to pvbrowser HMI.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from pvsolar.core.config import load_config
from pvsolar.pvbinder.bridge import PVBrowserBridge, PVBrowserDataConverter


async def main():
    """Main example function."""
    
    # Load configuration
    config = load_config("config/gateway.yaml")
    
    # Create pvbrowser bridge
    bridge = PVBrowserBridge(config.pvbrowser)
    await bridge.start()
    
    print(f"pvbrowser bridge started on port {config.pvbrowser.socket_port}")
    print("Waiting for pvbrowser connections...")
    
    # Example: Simulate inverter data
    example_data = {
        "inverter_name": "Fronius GEN24 Plus 8.0",
        "ac_power": 5420.0,
        "ac_voltage": [220.5, 221.0, 219.8],
        "ac_current": [8.2, 8.1, 8.3],
        "ac_frequency": 60.01,
        "dc_inputs": [
            {"string": 1, "voltage": 380.5, "current": 7.8, "power": 2967.9},
            {"string": 2, "voltage": 382.1, "current": 7.6, "power": 2903.96}
        ],
        "daily_energy": 28500.0,
        "total_energy": 15250000.0,
        "status": "running",
        "operating_state": 4,
        "temperature": 42.5,
        "efficiency": 96.2,
        "ac_frequency": 60.01,
        "custom": {
            "storage": {
                "state_of_charge": 75.0,
                "voltage": 51.2,
                "current": 5.0,
                "power": 256.0,
                "mode": "charging"
            }
        }
    }
    
    # Update data
    await bridge.update_data("inv-001", example_data)
    
    print("\nData sent to pvbrowser:")
    print(f"  AC Power: {example_data['ac_power']} W")
    print(f"  DC Power: {sum(d['power'] for d in example_data['dc_inputs']):.1f} W")
    print(f"  Efficiency: {example_data['efficiency']}%")
    print(f"  Daily Energy: {example_data['daily_energy']/1000:.2f} kWh")
    
    # Convert data for pvbrowser widgets
    print("\npvbrowser Widget Examples:")
    
    # Value widget
    value_widget = PVBrowserDataConverter.to_value_widget(example_data, "ac_power")
    print(f"  Value Widget: {value_widget}")
    
    # Gauge widget
    gauge_widget = PVBrowserDataConverter.to_gauge_data(
        example_data, 
        "efficiency",
        min_val=0,
        max_val=100
    )
    print(f"  Gauge Widget: {gauge_widget}")
    
    # Trend data
    trend_data = PVBrowserDataConverter.to_trend_data(
        example_data,
        ["ac_power", "dc_inputs.0.power", "dc_inputs.1.power"]
    )
    print(f"  Trend Data: {trend_data}")
    
    # Keep running
    print("\nBridge is running. Press Ctrl+C to stop.")
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await bridge.stop()
        print("Bridge stopped.")


if __name__ == "__main__":
    asyncio.run(main())
