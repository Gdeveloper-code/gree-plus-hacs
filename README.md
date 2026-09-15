# Gree Plus for Home Assistant

[English](README.md) | [Simplified Chinese](README.zh-Hans.md) | [Traditional Chinese](README.zh-Hant.md)

Gree Plus is an unofficial, community-maintained Home Assistant integration for technology enthusiasts. It connects supported GREE+ air conditioners to Home Assistant through the user's GREE+ cloud account.

## Features

- Power, HVAC mode, target temperature, and fan speed controls.
- Celsius, Fahrenheit, and model-dependent temperature steps.
- State refresh after setup and control commands.
- Manual refresh without background polling.

## Requirements

- Home Assistant 2026.9.1 or newer.
- A GREE+ account with at least one supported air conditioner.
- Internet access from Home Assistant to the cloud service.

## Installation

1. Open HACS in Home Assistant.
2. Add this repository as a custom repository in the **Integration** category.
3. Download **Gree Plus** and restart Home Assistant.
4. Open **Settings > Devices & services > Add integration** and select **Gree Plus**.

## Configuration

Select the account region, then sign in with the GREE+ account associated with the devices. Authentication session data is stored by Home Assistant so the integration can reconnect.

If additional verification is requested, open the sign-in link shown by Home Assistant, complete the challenge in your browser, then paste the complete `http://localhost/...` address from the browser address bar. Do not repeatedly submit the credentials form.

## Refresh Behavior

The integration does not poll continuously. It requests state during setup, after control commands, and when a manual entity update is requested. Changes made outside Home Assistant may not appear until the next refresh.

## Limitations

- Supported controls are limited to power, mode, target temperature, and fan speed.
- Available modes and temperature steps depend on device capabilities.
- Operation depends on the availability and compatibility of the cloud service.

## Support and Privacy

Report defects through the repository issue tracker. Before attaching diagnostics or logs, remove account identifiers, authentication data, device identifiers, names, and location information.

## Disclaimer

This project is not affiliated with, endorsed by, or supported by Gree Electric Appliances, Inc. GREE and related marks belong to their respective owners. The cloud service may change or become unavailable without notice. Use this integration at your own risk, review automations before enabling them, and retain access to an official control method. The maintainers are not responsible for service interruptions, unintended device operation, data loss, or resulting damage.

## License

MIT
