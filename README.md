# Gree Plus for Home Assistant

Gree Plus is an unofficial, community-maintained Home Assistant integration for technology enthusiasts. It signs in through GREE OAuth 2.0 and provides a focused set of air-conditioner controls.

This project uses cloud account access. It is separate from Home Assistant's built-in Gree Climate integration, which uses local polling.

## Features

- Discovers residential `ac` and commercial `multiAc` devices.
- Controls power, HVAC mode, target temperature, and fan speed.
- Supports Celsius, Fahrenheit, and model-dependent fractional temperature steps.
- Refreshes on setup, after control commands, or through an explicit user request.
- Renews OAuth tokens when required without background polling.

## Installation

1. Open HACS in Home Assistant.
2. Add this repository as a custom repository with category **Integration**.
3. Download **Gree Plus** and restart Home Assistant.
4. Open **Settings > Devices & services > Add integration** and select **Gree Plus**.

## Configuration

Select the account region and enter the GREE+ account credentials. The password is used for login and is not stored in the Home Assistant config entry.

## Limitations

- Changes made outside Home Assistant require a manual refresh.
- Only power, mode, target temperature, and fan speed are supported.
- Device capabilities depend on data exposed by the cloud API.

## Support

Report defects through the repository issue tracker. Remove account identifiers, tokens, device identifiers, and location data from logs before attaching them.

## Disclaimer

This project is not affiliated with, endorsed by, or supported by Gree Electric Appliances, Inc. GREE and related marks belong to their respective owners. The integration depends on a cloud service that may change or become unavailable without notice. Use it at your own risk, review automations before enabling them, and retain access to the official control method. The maintainers are not responsible for service interruptions, unintended device operation, data loss, or damage resulting from use of this software.

## License

MIT
