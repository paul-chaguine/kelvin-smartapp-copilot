import asyncio
from datetime import timedelta

from kelvin.application import KelvinApp, filters
from kelvin.krn import KRNAsset, KRNAssetDataStream
from kelvin.message import ControlChange, Recommendation
from kelvin.message.evidences import Image, Markdown


async def main() -> None:
    """
    Start streaming asset data, monitor motor temperature vs. thresholds,
    and issue speed-reduction recommendations when necessary.
    """
    app = KelvinApp()
    await app.connect()

    # Store the most recent motor_speed values per asset
    latest_motor_speeds: dict[str, float] = {}

    # Process each incoming asset data message
    async for message in app.stream_filter(filters.is_asset_data_message):
        asset_id = message.resource.asset
        data_stream = message.resource.data_stream
        measurement = message.payload

        print(f"Received '{data_stream}' for asset '{asset_id}': {measurement}")

        # Track motor speed measurements for future use
        if data_stream == "motor_speed":
            latest_motor_speeds[asset_id] = measurement
            continue

        # Only act on motor_temperature readings
        if data_stream != "motor_temperature":
            continue

        # Retrieve configured max temperature for this asset
        max_temp = app.assets[asset_id].parameters.get("temperature_max_threshold")

        if max_temp is None:
            print(f"No temperature threshold configured for asset '{asset_id}'. Skipping.")
            continue

        # If current temperature exceeds allowed limit, prepare a recommendation
        if measurement > max_temp:
            print(f"Temperature {measurement}° exceeds limit {max_temp}° for asset '{asset_id}'.")

            # Get last known motor speed; skip if unavailable
            speed = latest_motor_speeds.get(asset_id)
            if speed is None:
                print(f"Missing recent motor speed for '{asset_id}'. Cannot calculate adjustment.")
                continue

            # Reduce speed by 10% for safety
            new_speed_setpoint = speed * 0.9
            if new_speed_setpoint < 0:
                print(f"Calculated new speed setpoint {new_speed_setpoint} is invalid for asset '{asset_id}'.")
                continue

            control_action = ControlChange(
                resource=KRNAssetDataStream(asset_id, "motor_speed_set_point"),
                payload=new_speed_setpoint,
                expiration_date=timedelta(minutes=30),
            )

            # Include step-by-step guidance in markdown
            guidance = Markdown(
                title="Conduct a Thorough Load Assessment",
                markdown=(
                    "- **Measure** discharge pressure and flow rate.\n"
                    "- **Compare** readings to the pump-motor curve.\n"
                    "- **Action:** If pressure is too high, consider trimming impeller or reconfiguring pump staging.\n"
                ),
            )

            # Placeholder for visual evidence (e.g., schematic or infographic)
            infographic = Image(title="Load Assessment Infographic", url="https://kelvin-platform-cdn.kelvin.ai/demo-data/evidences/pcp_motor.jpg")

            # Build the recommendation object
            recommendation = Recommendation(
                resource=KRNAsset(asset_id),
                type="Decrease Speed",
                control_changes=[control_action],
                evidences=[guidance, infographic],
                auto_accepted=app.assets[asset_id].parameters.get("kelvin_closed_loop", False),
                expiration_date=timedelta(minutes=30),
            )

            # Send recommendation to Kelvin for operator review or auto-execution
            await app.publish(recommendation)

            print(f"Published Recommendation: set speed to {new_speed_setpoint} rpm")


if __name__ == "__main__":
    asyncio.run(main())
