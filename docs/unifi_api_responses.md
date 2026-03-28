# UniFi Integration API: WiFi Broadcasts

Reference for the WiFi Broadcast endpoints used by this project.

## Get WiFi Broadcast Details

Returns the full current configuration for one WiFi broadcast (SSID).

- Method: `GET`
- Path: `/v1/sites/{siteId}/wifi/broadcasts/{wifiBroadcastId}`
- Path parameters:
	- `siteId` (required, UUID)
	- `wifiBroadcastId` (required, UUID)

### Example Response (200)

```json
{
	"type": "STANDARD",
	"id": "497f6eca-6276-4993-bfeb-53cbbbba6f08",
	"name": "string",
	"metadata": {
		"origin": "string"
	},
	"enabled": true,
	"network": {
		"type": "string"
	},
	"securityConfiguration": {
		"type": "string",
		"radiusConfiguration": null
	},
	"broadcastingDeviceFilter": {
		"type": "string"
	},
	"mdnsProxyConfiguration": {
		"mode": "string"
	},
	"multicastFilteringPolicy": {
		"action": "string"
	},
	"multicastToUnicastConversionEnabled": true,
	"clientIsolationEnabled": true,
	"hideName": true,
	"uapsdEnabled": true,
	"basicDataRateKbpsByFrequencyGHz": {
		"5": 6000,
		"2.4": 2000
	},
	"clientFilteringPolicy": {
		"action": "ALLOW",
		"macAddressFilter": []
	},
	"blackoutScheduleConfiguration": {
		"days": []
	},
	"broadcastingFrequenciesGHz": [
		2.4,
		5
	],
	"hotspotConfiguration": {
		"type": "string"
	},
	"mloEnabled": true,
	"bandSteeringEnabled": true,
	"arpProxyEnabled": true,
	"bssTransitionEnabled": true,
	"advertiseDeviceName": true,
	"dtimPeriodByFrequencyGHzOverride": {
		"5": 1,
		"6": 1,
		"2.4": 1
	}
}
```

## Update WiFi Broadcast

Updates an existing WiFi broadcast on the specified site.

- Method: `PUT`
- Path: `/v1/sites/{siteId}/wifi/broadcasts/{wifiBroadcastId}`
- Path parameters:
	- `siteId` (required, UUID)
	- `wifiBroadcastId` (required, UUID)
- Body: `application/json`

### Required Body Fields

- `type` (string)
- `name` (string)
- `enabled` (boolean)
- `securityConfiguration` (object)
- `multicastToUnicastConversionEnabled` (boolean)
- `clientIsolationEnabled` (boolean)
- `hideName` (boolean)
- `uapsdEnabled` (boolean)
- `broadcastingFrequenciesGHz` (array, values from `2.4`, `5`, `6`)
- `arpProxyEnabled` (boolean)
- `bssTransitionEnabled` (boolean)
- `advertiseDeviceName` (boolean)

### Optional/Common Body Fields

- `network` (object)
- `broadcastingDeviceFilter` (object)
- `mdnsProxyConfiguration` (object)
- `multicastFilteringPolicy` (object)
- `basicDataRateKbpsByFrequencyGHz` (object)
- `clientFilteringPolicy` (object)
- `blackoutScheduleConfiguration` (object)
- `hotspotConfiguration` (object)
- `mloEnabled` (boolean)
- `bandSteeringEnabled` (boolean)
- `dtimPeriodByFrequencyGHzOverride` (object)

### Important Notes

- `PUT` is supported for this endpoint. `PATCH` is not required.
- The GET response includes read-only fields such as `id` and `metadata`.
- Remove read-only fields before sending a PUT body.

### Example PUT Body

```json
{
	"type": "STANDARD",
	"name": "string",
	"network": {
		"type": "string"
	},
	"enabled": true,
	"securityConfiguration": {
		"type": "string",
		"radiusConfiguration": null
	},
	"broadcastingDeviceFilter": {
		"type": "string"
	},
	"mdnsProxyConfiguration": {
		"mode": "string"
	},
	"multicastFilteringPolicy": {
		"action": "string"
	},
	"multicastToUnicastConversionEnabled": true,
	"clientIsolationEnabled": true,
	"hideName": true,
	"uapsdEnabled": true,
	"basicDataRateKbpsByFrequencyGHz": {
		"5": 6000,
		"2.4": 2000
	},
	"clientFilteringPolicy": {
		"action": "ALLOW",
		"macAddressFilter": []
	},
	"blackoutScheduleConfiguration": {
		"days": []
	},
	"broadcastingFrequenciesGHz": [
		2.4,
		5
	],
	"hotspotConfiguration": {
		"type": "string"
	},
	"mloEnabled": true,
	"bandSteeringEnabled": true,
	"arpProxyEnabled": true,
	"bssTransitionEnabled": true,
	"advertiseDeviceName": true,
	"dtimPeriodByFrequencyGHzOverride": {
		"5": 1,
		"6": 1,
		"2.4": 1
	}
}
```