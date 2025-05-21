import asyncio
from datetime import timedelta
from typing import AsyncGenerator

from kelvin.application import KelvinApp, filters
from kelvin.krn import KRNAsset, KRNAssetDataStream
from kelvin.message import ControlChange, Number, Recommendation


async def main() -> None:
    """
    Main entry point for the Kelvin Application.

    - Connects the app to Kelvin.
    - Subscribes to a filtered stream of "motor_temperature" input messages.
    - Monitors temperature values and issues either a control change or a recommendation based on predefined asset parameters.
    """
    app = KelvinApp()
    await app.connect()

    # Stream messages where the input type matches "motor_temperature"
    temperature_stream: AsyncGenerator[Number, None] = app.stream_filter(filters.input_equals("motor_temperature"))

    async for message in temperature_stream:
        asset = message.resource.asset
        temperature_value = message.payload

        print(f"Received temperature value: {temperature_value} for asset: {asset}")

        # Fetch maximum allowed temperature threshold for the asset
        max_temp_threshold = app.assets[asset].parameters["temperature_max_threshold"]

        if temperature_value > max_temp_threshold:

            print(f"Temperature exceeds threshold: {max_temp_threshold}")

            # Construct a control change to adjust motor speed
            motor_speed_adjustment = ControlChange(
                resource=KRNAssetDataStream(asset, "motor_speed_set_point"),  # Targeting the motor speed set point
                payload=temperature_value - (temperature_value * 0.1),  # Reduce motor speed by 10% of temperature value
                expiration_date=timedelta(minutes=10),  # Set expiration date for the control change
            )

            # Determine asset control mode
            is_closed_loop = app.assets[asset].parameters.get("kelvin_closed_loop", False)

            if is_closed_loop:
                # Directly publish the control change if in closed loop mode
                await app.publish(motor_speed_adjustment)

                print(f"Published Control Change: Decreased motor speed by {motor_speed_adjustment.payload}")
            else:
                # Publish a recommendation if manual action is required
                recommendation = Recommendation(
                    resource=KRNAsset(asset),  # Targeting the asset itself
                    type="Decrease Speed",  # What is the recommendation about
                    control_changes=[motor_speed_adjustment],  # Include the control change in the recommendation
                )
                await app.publish(recommendation)

                print(f"Published Recommendation: Suggest decreasing motor speed by {motor_speed_adjustment.payload}")


if __name__ == "__main__":
    asyncio.run(main())
