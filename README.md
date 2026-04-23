# HA Gaming Hub

A HACS custom integration for Home Assistant that brings gaming data into your smart home.

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

---

## Modules

| Module | Description | API Key Required |
| ------ | ----------- | ---------------- |
| **Free Games** | Tracks free game promotions from Epic Games Store and GamerPower | No |
| **Price Tracker** | Monitors game prices and alerts on deals via CheapShark / IsThereAnyDeal | Optional (ITAD) |
| **Presence** | Shows Steam and Xbox online status for tracked accounts | Yes (Steam / Xbox) |

---

## Installation

1. Make sure [HACS](https://hacs.xyz) is installed in your Home Assistant instance.
2. In HACS, go to **Integrations** → click the three-dot menu → **Custom repositories**.
3. Add `https://github.com/nuggetz/ha-gaming-hub` as an **Integration**.
4. Search for **HA Gaming Hub** and install it.
5. Restart Home Assistant.
6. Go to **Settings → Integrations → Add Integration** and search for **HA Gaming Hub**.
7. Follow the config flow to select and configure the modules you want to enable.

---

## Free Games Module

### Entities

| Entity | Type | Description |
| ------ | ---- | ----------- |
| `sensor.gaming_hub_free_games_count` | Sensor | Number of currently available free games |
| `sensor.gaming_hub_free_games_value` | Sensor | Total value of current free games (in your HA currency) |
| `calendar.gaming_hub_free_games` | Calendar | All free games as calendar events, with claim deadlines |

> **Note — currency:** the value sensor is always in USD, as prices are sourced from GamerPower in USD.
> **Note — entity IDs:** if your entities show up as `sensor.free_games_available` instead of `sensor.gaming_hub_free_games_count`, HA has cached the old entity IDs in its registry. Go to **Settings → Entities**, search for "free games", delete the 3 old entries, then reload the integration. The correct IDs will be created on the next load.

### Data sources

- **Epic Games Store** — official free game promotions (current + upcoming), with cover art
- **GamerPower** — aggregator for PC giveaways across Steam, GOG, Itch.io, and more (excluding Epic, to avoid duplicates)

### Displaying free games in the dashboard

The `sensor.gaming_hub_free_games_count` entity exposes a `data` attribute formatted to be compatible with the [Upcoming Media Card](https://github.com/custom-cards/upcoming-media-card).

#### Option A — Upcoming Media Card (recommended, requires HACS frontend install)

Install **Upcoming Media Card** from HACS → Frontend, then add this card to your dashboard:

```yaml
type: custom:upcoming-media-card
entity: sensor.gaming_hub_free_games_count
title: Free Games
max: 10
```

This will display game cover art, platform, price info, and claim deadline in a media-style grid.

#### Option B — Built-in Markdown Card (no extra dependencies)

Use a standard Markdown card with a Jinja2 template to render the list:

```yaml
type: markdown
title: 🎮 Free Games
content: >
  {% set games = state_attr('sensor.gaming_hub_free_games_count', 'data') %}
  {% for g in games[1:] %}
  **[{{ g.title }}]({{ g.deep_link }})**
  {{ g.rating }} — {{ g.price }}
  {% if g.release %}⏳ {{ g.release }}{% endif %}

  ---
  {% endfor %}
```

To include cover art images inline:

```yaml
type: markdown
title: 🎮 Free Games
content: >
  {% set games = state_attr('sensor.gaming_hub_free_games_count', 'data') %}
  {% for g in games[1:] %}
  {% if g.box_art_url %}![]({{ g.box_art_url }}){% endif %}
  **[{{ g.title }}]({{ g.deep_link }})** | {{ g.genres | upper }}
  {{ g.price }}{% if g.release %} — ⏳ {{ g.release }}{% endif %}

  {% endfor %}
```

### `data` attribute format

Each entry in `games[1:]` (skip the first item which is the header template) contains:

| Field | Description |
| ----- | ----------- |
| `title` | Game title |
| `rating` | Platform (e.g. `Epic Games`, `PC, Steam`) |
| `price` | `FREE` or `FREE ($X.XX value)` |
| `release` | Human-readable expiry date, e.g. `Expires 30 Apr 2026` |
| `genres` | Content type: `game`, `dlc`, `loot`, `other` |
| `airdate` | Expiry date as `YYYY-MM-DD` (or `unknown`) |
| `box_art_url` | Wide cover art URL |
| `poster` | Portrait cover art URL (falls back to wide) |
| `deep_link` | Direct URL to the store page / claim page |

---

## Development Status

| Milestone | Description | Status |
| --------- | ----------- | ------ |
| 0 | Setup & Infrastructure | ✅ Done |
| 1 | Free Games module | ✅ Done |
| 2 | Price Tracker module | ⏳ Pending |
| 3 | Presence module (Steam) | ⏳ Pending |
| 4 | Presence module (Xbox) | ⏳ Pending |
