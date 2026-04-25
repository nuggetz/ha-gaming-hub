# HA Gaming Hub

![HA Gaming Hub logo](docs/ha_gaming_hub_logo.svg)

A HACS custom integration for Home Assistant that brings gaming data into your smart home.

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![License: MIT](https://img.shields.io/github/license/nuggetz/ha-gaming-hub)](LICENSE)
[![Release](https://img.shields.io/github/v/release/nuggetz/ha-gaming-hub?display_name=tag)](https://github.com/nuggetz/ha-gaming-hub/releases)
[![Issues](https://img.shields.io/github/issues/nuggetz/ha-gaming-hub)](https://github.com/nuggetz/ha-gaming-hub/issues)
[![Last commit](https://img.shields.io/github/last-commit/nuggetz/ha-gaming-hub)](https://github.com/nuggetz/ha-gaming-hub/commits/main)

---

## Modules

| Module | Description | API Key Required |
| ------ | ----------- | ---------------- |
| **Free Games** | Tracks free game promotions from Epic Games Store and GamerPower | No |
| **Price Tracker** | Monitors game prices and deals via CheapShark / IsThereAnyDeal | Optional (ITAD) |
| **Presence** | Shows Steam and Xbox online status for tracked accounts | Yes (Steam / Xbox) |

You can enable any combination of modules during setup. Each module is independent.

---

## Installation

1. Make sure [HACS](https://hacs.xyz) is installed in your Home Assistant instance.
2. In HACS, go to **Integrations** → click the three-dot menu → **Custom repositories**.
3. Add `https://github.com/nuggetz/ha-gaming-hub` as an **Integration**.
4. Search for **HA Gaming Hub** and install it.
5. Restart Home Assistant.
6. Go to **Settings → Integrations → Add Integration** and search for **HA Gaming Hub**.
7. Follow the setup wizard to select and configure your modules.

### Setup screenshots

| Module selection | Free Games config | Presence / Steam config |
| ---------------- | ----------------- | ----------------------- |
| ![Select modules](docs/select-modules.png) | ![Free Games config](docs/free-games-config.png) | ![Presence Steam config](docs/presence-steam-config.png) |

---

## The Unified Deals Sensor

Regardless of which modules you enable, the integration creates a single sensor that combines everything:

**`sensor.gaming_hub_deals`**

| What it shows | Source |
| ------------- | ------ |
| Free games (100% off) | Epic Games Store + GamerPower |
| Watchlist deals | Your Price Tracker watchlist (ITAD / CheapShark) |

State = total item count. The `on_sale` attribute contains every entry in **Nintendo Wishlist Card** format.

Any game that is also in your **Steam wishlist** gets a ⭐ prefix in its `sale_price` field — across both free games and tracked deals — so you never miss a game you actually want.

### Dashboard card

```yaml
type: custom:nintendo-wishlist-card
entity: sensor.gaming_hub_deals
title: Gaming Hub
```

### ⭐ Steam Wishlist Matching

The ⭐ badge is automatic if you:

1. Have the [steam_wishlist](https://github.com/custom-components/steam_wishlist) custom integration installed and configured in HA (the integration already polls your wishlist periodically)
2. Enter your **SteamID64** during HA Gaming Hub setup (Free Games or Price Tracker step)

The integration reads game titles directly from the `steam_wishlist` entities already in your HA, so no extra API calls are needed. If `steam_wishlist` is not installed, it falls back to the Steam Web API (requires a Steam API key).

**Finding your SteamID64:**

- Custom URL (`steamcommunity.com/id/yourname`) → use [steamid.io](https://steamid.io) to convert to the 17-digit numeric ID
- Numeric URL (`steamcommunity.com/profiles/76561198XXXXXXXXX`) → the number in the URL is your SteamID64

---

## Free Games Module

### Entities

| Entity | Type | Description |
| ------ | ---- | ----------- |
| `sensor.gaming_hub_free_games_count` | Sensor | Number of currently available free games |
| `sensor.gaming_hub_free_games_value` | Sensor | Total value of current free games (USD) |
| `calendar.gaming_hub_free_games` | Calendar | All free games as calendar events with claim deadlines |

> **Note — entity IDs:** if your entities show up as `sensor.free_games_available`, HA has cached old IDs. Go to **Settings → Entities**, search for "free games", delete the old entries, then reload the integration.

### Data sources

- **Epic Games Store** — official free game promotions (current + upcoming), with cover art
- **GamerPower** — aggregator for PC giveaways across Steam, GOG, Itch.io, and more (Epic excluded to avoid duplicates)

### Dashboard cards

`sensor.gaming_hub_free_games_count` exposes two attributes: `data` (Upcoming Media Card) and `on_sale` (Nintendo Wishlist Card).

#### Nintendo Wishlist Card

```yaml
type: custom:nintendo-wishlist-card
entity: sensor.gaming_hub_free_games_count
title: Free Games
```

#### Upcoming Media Card

```yaml
type: custom:upcoming-media-card
entity: sensor.gaming_hub_free_games_count
title: Free Games
max: 10
```

#### Markdown Card (no extra dependencies)

```yaml
type: markdown
title: 🎮 Free Games
content: >
  {% set games = state_attr('sensor.gaming_hub_free_games_count', 'on_sale') %}
  {% for g in games %}
  {% if g.box_art_url %}![]({{ g.box_art_url }}){% endif %}
  **{{ g.title }}** — {{ g.sale_price }}
  {% if g.normal_price %}~~{{ g.normal_price }}~~{% endif %}

  ---
  {% endfor %}
```

### Attribute reference

#### `on_sale` — Nintendo Wishlist Card format

| Field | Description |
| ----- | ----------- |
| `title` | Game title |
| `box_art_url` | Cover art URL |
| `backgroundart` | Wide art URL |
| `sale_price` | `"Free · Steam"` / `"Free · Epic Games"` etc. Prefixed with ⭐ when the game is in your Steam wishlist |
| `normal_price` | Original value (`"$X.XX"`) if known from GamerPower, otherwise empty |
| `percent_off` | Always `100` |

#### `data` — Upcoming Media Card format

`data[0]` is the header row. Games start at `data[1:]`.

| Field | Description |
| ----- | ----------- |
| `title` | Game title |
| `rating` | Platform (e.g. `Epic Games`, `PC, Steam`) |
| `price` | `"FREE"` or `"FREE ($X.XX value)"`. Prefixed with ⭐ when in Steam wishlist |
| `release` | Human-readable expiry, e.g. `Expires 30 Apr 2026` |
| `genres` | Content type: `game`, `dlc`, `loot`, `other` |
| `airdate` | Expiry date as `YYYY-MM-DD` (or `unknown`) |
| `box_art_url` | Wide cover art URL |
| `poster` | Portrait cover art (falls back to wide) |
| `deep_link` | Direct URL to the store / claim page |

### Configuration options

During setup, after selecting Free Games:

| Field | Default | Notes |
| ----- | ------- | ----- |
| Polling interval | 1 800 s (30 min) | Min 30 min, max 24 h |
| Steam API Key | *(empty)* | Optional — only needed if `steam_wishlist` integration is not installed |
| SteamID64 | *(empty)* | Optional — required for ⭐ wishlist matching; pre-fills the same field in Price Tracker |

---

## Price Tracker Module

Monitors the price of games you add to a watchlist. For each tracked game the integration creates a set of entities that update automatically and can trigger automations when a deal is found.

### Price data sources

- **CheapShark** — aggregates deals from 30+ stores (Steam, GOG, Humble, Fanatical, GreenManGaming, and more). No API key required.
- **IsThereAnyDeal (ITAD)** — optional enrichment: historical lows, more stores, richer metadata. Requires a free API key.

### Getting an ITAD API key (optional)

1. Create a free account at [IsThereAnyDeal.com](https://isthereanydeal.com)
2. Go to your [Developer page](https://isthereanydeal.com/dev/app/) (top-right menu → Developer)
3. Create a new application — any name (e.g. `Home Assistant`)
4. Copy the **API key** shown in the application details

You can leave this field blank: the integration will use CheapShark-only data, which is sufficient for price and discount tracking.

### Managing your watchlist

After setup, go to **Settings → Integrations → HA Gaming Hub → Configure**:

- Type a game title in **Add game** and submit → a search step shows matching results, pick the correct one
- Select a game in **Remove game** and submit → the game and all its entities are deleted immediately

### Entities (per tracked game)

Entity IDs use a slugified version of the game title (e.g. `cyberpunk_2077`).

| Entity | Type | Description |
| ------ | ---- | ----------- |
| `sensor.gaming_hub_<slug>_best_price` | Sensor | Current lowest price across all stores (USD) |
| `sensor.gaming_hub_<slug>_best_store` | Sensor | Store offering the best current price |
| `sensor.gaming_hub_<slug>_discount` | Sensor | Current discount percentage (0–100) |
| `binary_sensor.gaming_hub_<slug>_on_sale` | Binary Sensor | `on` when any store has a discount > 0% |
| `binary_sensor.gaming_hub_<slug>_historical_low` | Binary Sensor | `on` when the current best price equals the all-time low |

The `sensor.gaming_hub_<slug>_best_price` entity also exposes:

| Attribute | Description |
| --------- | ----------- |
| `cheapest_ever_price` | All-time lowest price recorded (USD) |
| `cheapest_ever_date` | Date of the all-time low |
| `in_steam_wishlist` | `true` if the game is in your Steam wishlist |

### Aggregate sensor

`sensor.gaming_hub_price_tracker_deals` aggregates your entire watchlist in Nintendo Wishlist Card format. State = number of games currently on sale. The `on_sale` attribute lists all tracked games with price, store, discount, cover art, and ⭐ where applicable.

```yaml
type: custom:nintendo-wishlist-card
entity: sensor.gaming_hub_price_tracker_deals
title: Price Tracker
```

```yaml
type: markdown
title: 🎮 Price Tracker
content: >
  {% set games = state_attr('sensor.gaming_hub_price_tracker_deals', 'on_sale') %}
  {% for g in games %}
  {% if g.box_art_url %}![]({{ g.box_art_url }}){% endif %}
  **{{ g.title }}** — {{ g.sale_price }}
  {% if g.normal_price %} ~~{{ g.normal_price }}~~{% endif %}{% if g.percent_off %} (-{{ g.percent_off }}%){% endif %}

  ---
  {% endfor %}
```

### Price Tracker configuration options

| Field | Default | Notes |
| ----- | ------- | ----- |
| ITAD API Key | *(empty)* | Optional |
| Polling interval | 3 600 s (1 h) | Min 1 h, max 24 h |
| Steam API Key | *(empty)* | Pre-filled if entered in Free Games step |
| SteamID64 | *(empty)* | Pre-filled if entered in Free Games step |

### Example automation

```yaml
alias: Notify when a wishlisted game hits all-time low
trigger:
  - platform: state
    entity_id: binary_sensor.gaming_hub_cyberpunk_2077_historical_low
    to: "on"
action:
  - service: notify.mobile_app_your_phone
    data:
      title: "Deal alert!"
      message: >
        Cyberpunk 2077 is at its all-time low:
        ${{ states('sensor.gaming_hub_cyberpunk_2077_best_price') }}
        on {{ states('sensor.gaming_hub_cyberpunk_2077_best_store') }}
```

---

## Presence Module

Shows the online and gaming status of Steam and Xbox accounts in real time.

### Steam setup (optional)

Steam tracking is optional. Leave both Steam fields blank to skip it and go straight to the Xbox step.

#### 1 — Get a Steam API key

1. Go to [https://steamcommunity.com/dev/apikey](https://steamcommunity.com/dev/apikey) (must be logged in)
2. Enter any domain (e.g. `homeassistant.local`) and click **Register**
3. Copy the key shown on the next page

> **Tip:** if you entered a Steam API key in the Free Games or Price Tracker step, it will be pre-filled here automatically.

#### 2 — Find Steam IDs or Vanity URLs

- **Custom URL** (`steamcommunity.com/id/yourname`) → enter `yourname` as the Vanity URL
- **Numeric URL** (`steamcommunity.com/profiles/76561198XXXXXXXXX`) → enter the 17-digit number

You can track multiple accounts: one ID or Vanity URL per line. Vanity URLs are resolved to SteamID64 automatically during setup.

### Xbox setup

Xbox support reads data from the **official Home Assistant Xbox integration** — no extra credentials needed on your side.

#### Step 1 — Install the native Xbox integration

1. **Settings → Integrations → Add Integration → Xbox**
2. Complete the OAuth flow (requires Nabu Casa or externally accessible HA)
3. The integration creates `binary_sensor.xbox_<gamertag>_online` entities automatically

#### Step 2 — Link in HA Gaming Hub

During Presence setup, after the Steam step, detected Xbox accounts are listed for selection. If the Xbox integration is not installed, this step is skipped automatically.

### Presence entities

#### Per Steam account

| Entity | Type | Description |
| ------ | ---- | ----------- |
| `binary_sensor.gaming_hub_<steamid>_online` | Binary Sensor | `on` when online (any state except Offline) |
| `sensor.gaming_hub_<steamid>_playing` | Sensor | Current game, or `—` if idle |
| `sensor.gaming_hub_<steamid>_status` | Sensor | Detailed status: `Online`, `Away`, `Busy`, `Snooze`, etc. |
| `sensor.gaming_hub_<steamid>_hours_recent` | Sensor | Hours played in the last 2 weeks |

#### Per Xbox account

| Entity | Type | Description |
| ------ | ---- | ----------- |
| `binary_sensor.gaming_hub_xbox_<xuid>_online` | Binary Sensor | `on` when active on Xbox Live |
| `sensor.gaming_hub_xbox_<xuid>_playing` | Sensor | Current game or activity, or `—` if idle |

#### Aggregate

| Entity | Type | Description |
| ------ | ---- | ----------- |
| `binary_sensor.gaming_hub_someone_is_gaming` | Binary Sensor | `on` when **any** tracked account is actively playing |

### Example automations

```yaml
# Turn on a light scene when someone starts gaming
alias: Gaming light on
trigger:
  - platform: state
    entity_id: binary_sensor.gaming_hub_someone_is_gaming
    to: "on"
action:
  - service: hue.activate_scene
    data:
      group_name: Living Room
      scene_name: Gaming

# Notify when a friend comes online
alias: Friend online
trigger:
  - platform: state
    entity_id: binary_sensor.gaming_hub_76561198XXXXXXXXX_online
    to: "on"
action:
  - service: notify.mobile_app_your_phone
    data:
      message: >
        {{ states('sensor.gaming_hub_76561198XXXXXXXXX_status') }} —
        {{ states('sensor.gaming_hub_76561198XXXXXXXXX_playing') }}
```

---

## Development Status

| Milestone | Description | Status |
| --------- | ----------- | ------ |
| 0 | Setup & Infrastructure | ✅ Done |
| 1 | Free Games module | ✅ Done |
| 2 | Price Tracker module | ✅ Done |
| 3 | Presence module (Steam + Xbox) | ✅ Done |
| 4 | Notifications & automations helpers | ⏳ Pending |
