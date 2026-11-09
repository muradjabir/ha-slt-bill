# SLT Bill & Broadband (Sri Lanka) - Home Assistant Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=for-the-badge)](https://github.com/hacs/default)
[![GitHub release](https://img.shields.io/github/v/release/muradjabir/ha-slt-bill?style=for-the-badge)](https://github.com/muradjabir/ha-slt-bill/releases)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)

Track your **Sri Lanka Telecom (SLT-Mobitel)** bill balances, invoices, payment history, and broadband data quota usage directly in Home Assistant.

This custom component communicates with the official [MySLT](https://myslt.slt.lk/) self-care API gateway to automatically discover and monitor **all connections and accounts** linked to your MySLT profile.

---

## Features

- **Multi-Connection Support:** Automatically discovers all telephone numbers and fiber connections associated with your MySLT account. Track one, some, or all connections simultaneously.
- **Dedicated Device per Connection:** Each telephone/fiber connection is represented as its own distinct Device in Home Assistant, grouping its billing and broadband sensors.
- **Comprehensive Billing Tracking:**
  - `Outstanding Balance` (in `LKR`, `monetary` device class)
  - `Last Bill Amount` (in `LKR`)
  - `Last Payment Amount` (in `LKR`)
  - `Payment Due Date` (as a `date` entity)
  - `Last Bill Date` (as a `date` entity)
  - `Last Payment Date` (as a `date` entity)
  - `Connection Status` (e.g. `ACTIVE`)
- **Broadband Data Quota Monitoring:**
  - `Broadband Data Used` (in `GB`, `data_size` device class)
  - `Broadband Package` (e.g. `UNLIMITED HOME`)
  - `Broadband Data Remaining` (for capped volume packages)
- **Automatic Token Management:** Authenticates securely via MySLT API and transparently renews session tokens without requiring CAPTCHAs or SMS OTPs.
- **Config Flow & Options Flow:** Simple UI setup with options to customize update polling frequency (minimum 2 hours) and connection selection.

---

## Installation

### Method 1: Via HACS (1-Click Install)

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=muradjabir&repository=ha-slt-bill&category=integration)

1. In Home Assistant, open **HACS** > **Integrations**.
2. Click the **three dots** in the top-right corner and select **Custom repositories**.
3. Add the repository URL:
   ```text
   https://github.com/muradjabir/ha-slt-bill
   ```
4. Select Category: **Integration** and click **Add**.
5. Search for **SLT Bill & Broadband (Sri Lanka)** and click **Download**.
6. Restart Home Assistant.

### Method 2: Manual Installation

1. Download the latest release archive or clone this repository.
2. Copy the `custom_components/slt_bill` directory into your Home Assistant `<config_dir>/custom_components/` folder.
3. Restart Home Assistant.

---

## Configuration

1. In Home Assistant, navigate to **Settings** > **Devices & Services**.
2. Click **Add Integration** in the bottom-right corner.
3. Search for **Sri Lanka Telecom (SLT)**.
4. Enter your **MySLT username / mobile number** and **password**.
5. If you have multiple telephone connections or accounts, select the connections you wish to monitor.
6. Home Assistant will create a dedicated device for each selected connection with all its billing and broadband sensors.

---

## Example Automation: Bill Due Reminder

Get a push notification when your SLT bill is due within 3 days:

```yaml
alias: "SLT Bill Due Reminder"
description: "Send notification when SLT bill payment due date is approaching"
trigger:
  - platform: time
    at: "09:00:00"
condition:
  - condition: template
    value_template: >-
      {% set due = states('sensor.slt_0112288754_0050273956_payment_due_date') %}
      {% if due not in ['unknown', 'unavailable'] %}
        {% set days = (as_datetime(due).date() - now().date()).days %}
        {{ days <= 3 and days >= 0 and states('sensor.slt_0112288754_0050273956_outstanding_balance') | float(0) > 0 }}
      {% else %}
        false
      {% endif %}
action:
  - action: notify.notify
    data:
      title: "SLT Bill Payment Due"
      message: >-
        Your SLT bill of LKR {{ states('sensor.slt_0112288754_0050273956_outstanding_balance') }} is due on {{ states('sensor.slt_0112288754_0050273956_payment_due_date') }}.
mode: single
```

---

## Disclaimer

This integration is an independent open-source project and is not officially affiliated with, endorsed by, or sponsored by Sri Lanka Telecom PLC (SLT-Mobitel).

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

