import asyncio
from datetime import timedelta

from kelvin.application import KelvinApp, filters
from kelvin.krn import KRNAsset, KRNAssetDataStream
from kelvin.message import ControlChange, Recommendation
from kelvin.message.evidences import Image, Markdown


async def stream_data_quality_messages(app: KelvinApp) -> None:
    async for message in app.stream_filter(filters.is_asset_data_quality_message):
        asset_id = message.resource.asset
        data_quality_metric = message.resource.data_quality
        dq_value = message.payload
        # Track dq measurements for future use
        print(f"Received '{data_quality_metric}' for asset '{asset_id}': {dq_value}")
        return asset_id, data_quality_metric, dq_value

# Process each incoming asset data message
async def stream_asset_data_messages(app: KelvinApp) -> None:
    async for message in app.stream_filter(filters.is_asset_data_message):
        asset_id = message.resource.asset
        data_stream = message.resource.data_stream
        measurement = message.payload
        print(f"Updated latest {data_stream} for asset '{asset_id}': {measurement}")
        return asset_id, data_stream, measurement

async def main() -> None:
    """
    Start streaming asset data, monitor motor temperature vs. thresholds,
    and issue speed-reduction recommendations when necessary.
    """
    app = KelvinApp()
    await app.connect()

    # Store the most recent motor_speed values per asset

    # results = await asyncio.gather(
    #     stream_data_quality_messages(app),stream_asset_data_messages(app)
    # ) 

    results = await stream_asset_data_messages(app)

    # latest_dq_metric = results[0].data_quality_metric
    # print(f"Data quality metric is '{latest_dq_metric}'")
    # latest_dq_value = results[0].dq_value
    # print(f"Latest data quality value for asset '{asset_id}': {latest_dq_value}")

    asset_id = results[0].asset_id
    print(f"Processing data for asset '{asset_id}'")
    latest_metric = results[0].data_stream
    if latest_metric == "speed":
        latest_speed = results[0].measurement
        print(f"Latest speed for asset '{asset_id}': {latest_speed}")
    elif latest_metric == "casing_pressure":
        latest_casing_pressure = results[0].measurement
        print(f"Latest casing pressure for asset '{asset_id}': {latest_casing_pressure}")
    elif latest_metric == "tubing_pressure":
        latest_tubing_pressure = results[0].measurement
        print(f"Latest tubing pressure for asset '{asset_id}': {latest_tubing_pressure}")

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
