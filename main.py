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
    latest_speed: dict[str, float] = {}
    latest_casing_pressure: dict[str, float] = {}
    latest_tubing_pressure: dict[str, float] = {}
    latest_dq: dict[str, float] = {}

    async for message in app.stream_filter(filters.is_asset_data_quality_message):
        
        asset_id = message.resource.asset
        data_quality_metric = message.resource.data_quality
        value = message.payload
        # Track dq measurements for future use
        if data_quality_metric == "kelvin_data_availability":
            latest_dq[asset_id] = value
            print(f"Received '{data_quality_metric}' for asset '{asset_id}': {value}")
    
    # Process each incoming asset data message
    async for message in app.stream_filter(filters.is_asset_data_message):
        asset_id = message.resource.asset
        data_stream = message.resource.data_stream
        measurement = message.payload

        print(f"Received '{data_stream}' for asset '{asset_id}': {measurement}")
        
        if data_stream == "speed":
            latest_speed[asset_id] = measurement
            print(f"Updated latest speed for asset '{asset_id}': {measurement}")

        if data_stream == "casing_pressure":
            latest_casing_pressure[asset_id] = measurement
            print(f"Updated latest casing pressure for asset '{asset_id}': {measurement}")

        if data_stream == "tubing_pressure":
            latest_tubing_pressure[asset_id] = measurement
            print(f"Updated latest tubing pressure for asset '{asset_id}': {measurement}")  

        # Retrieve configured max temperature for this asset
    min_dq = app.assets[asset_id].parameters.get("dataquality_min_threshold")
    print(f"Configured dq threshold for asset '{asset_id}': {min_dq}")

    if min_dq is None:
        print(f"No dq threshold configured for asset '{asset_id}'. Skipping.")

    # If current temperature exceeds allowed limit, prepare a recommendation

    # Get last known motor speed; skip if unavailable
    speed = latest_speed.get(asset_id)
    print(f"Latest speed for asset '{asset_id}': {speed}")
    if speed is None:
        print(f"Missing recent motor speed for '{asset_id}'. Cannot calculate adjustment.")

    # Reduce speed by 10% for safety
    new_speed_setpoint = speed * 0.9
    if new_speed_setpoint < 0:
        print(f"Calculated new speed setpoint {new_speed_setpoint} is invalid for asset '{asset_id}'.")

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

    asyncio.sleep(200)


if __name__ == "__main__":
    asyncio.run(main())
