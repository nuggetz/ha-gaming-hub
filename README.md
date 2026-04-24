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

The `sensor.gaming_hub_free_games_count` entity exposes two attributes so it works out of the box with multiple cards: `data` for the [Upcoming Media Card](https://github.com/custom-cards/upcoming-media-card) and `on_sale` for the [Nintendo Wishlist Card](https://github.com/custom-cards/nintendo-wishlist-card).

#### Option A — Nintendo Wishlist Card (best looking, requires HACS frontend install)

Install **Nintendo Wishlist Card** from HACS → Frontend, then add this card to your dashboard:

```yaml
type: custom:nintendo-wishlist-card
entity: sensor.gaming_hub_free_games_count
title: Free Games
```

Displays cover art, title, and "Free / $X.XX value" in the same style as the Nintendo Switch wishlist.

#### Option B — Upcoming Media Card (requires HACS frontend install)

Install **Upcoming Media Card** from HACS → Frontend, then add this card to your dashboard:

```yaml
type: custom:upcoming-media-card
entity: sensor.gaming_hub_free_games_count
title: Free Games
max: 10
```

Displays cover art, platform, expiry date, and claim link in a media-style grid.

#### Option C — Built-in Markdown Card (no extra dependencies)

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

### Attribute formats

The sensor exposes two attributes so it works with multiple cards out of the box.

#### `data` — for Upcoming Media Card

`data[0]` is the header template item. Actual games start at `data[1:]`.

| Field | Description |
| ----- | ----------- |
| `title` | Game title |
| `rating` | Platform (e.g. `Epic Games`, `PC, Steam`) |
| `price` | `FREE` or `FREE ($X.XX value)` |
| `release` | Human-readable expiry, e.g. `Expires 30 Apr 2026` |
| `genres` | Content type: `game`, `dlc`, `loot`, `other` |
| `airdate` | Expiry date as `YYYY-MM-DD` (or `unknown`) |
| `box_art_url` | Wide cover art URL |
| `poster` | Portrait cover art URL (falls back to wide) |
| `deep_link` | Direct URL to the store / claim page |

#### `on_sale` — for Nintendo Wishlist Card

| Field | Description |
| ----- | ----------- |
| `title` | Game title |
| `box_art_url` | Cover art URL |
| `backgroundart` | Wide art URL (same as cover) |
| `sale_price` | `"Free · Steam"` / `"Free · Epic Games"` etc. — store name always shown here |
| `normal_price` | `"$X.XX"` if the original value is known from GamerPower, otherwise empty |
| `percent_off` | Always `100` |

---

## Price Tracker Module

Monitors the price of games you add to a watchlist. For each tracked game the integration creates a set of entities that update automatically and can trigger automations when a deal is found.

### Price data sources

- **CheapShark** — aggregates deals from 30+ stores (Steam, GOG, Humble, Fanatical, GreenManGaming, and more). No API key required.
- **IsThereAnyDeal (ITAD)** — optional enrichment: historical lows, more stores, and richer metadata. Requires a free API key.

### Getting an ITAD API key (optional)

1. Create a free account at [IsThereAnyDeal.com](https://isthereanydeal.com)
2. Go to your [Developer page](https://isthereanydeal.com/dev/app/) (top-right menu → Developer)
3. Create a new application — give it any name (e.g. `Home Assistant`)
4. Copy the **API key** shown in the application details

You can leave this field blank during setup: the integration will use CheapShark-only data, which is already enough for price + discount tracking.

### Configuration

During the initial setup wizard, after selecting **Price Tracker**:

- **IsThereAnyDeal API Key** — paste your key, or leave blank
- **Polling interval** — how often to refresh prices (default: 3 600 s / 1 hour; min 1 h, max 24 h)

After setup, manage your watchlist from **Settings → Integrations → HA Gaming Hub → Configure**:

- Type a game title in **Add game** and submit → a search step shows matching results, pick the correct one
- Select a game in **Remove game** and submit → it and all its entities are deleted immediately

### Entities (per tracked game)

Each game on your watchlist creates 4 entities. Entity IDs use a slugified version of the game title (e.g. `cyberpunk_2077`).

| Entity | Type | Description |
| ------ | ---- | ----------- |
| `sensor.gaming_hub_<slug>_best_price` | Sensor | Current lowest price across all stores (USD) |
| `sensor.gaming_hub_<slug>_best_store` | Sensor | Store offering the best current price |
| `sensor.gaming_hub_<slug>_discount` | Sensor | Current discount percentage (0–100) |
| `binary_sensor.gaming_hub_<slug>_on_sale` | Binary Sensor | `on` when any store has a discount > 0% |
| `binary_sensor.gaming_hub_<slug>_historical_low` | Binary Sensor | `on` when the current best price equals the all-time low |

### Example automation

```yaml
alias: Notify when Cyberpunk 2077 hits historical low
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

### Steam setup

#### 1 — Get a Steam API key

1. Go to [https://steamcommunity.com/dev/apikey](https://steamcommunity.com/dev/apikey) (you must be logged in)
2. Enter any domain in the **Domain Name** field (e.g. `homeassistant.local`) and click **Register**
3. Copy the key shown on the next page

#### 2 — Find your Steam ID or Vanity URL

Open your Steam profile in a browser and look at the URL:

- **Custom URL** → `https://steamcommunity.com/id/`**`yourname`** — enter `yourname` as the Vanity URL
- **Numeric ID** → `https://steamcommunity.com/profiles/`**`76561198XXXXXXXXX`** — enter the 17-digit number directly

You can track multiple accounts: enter one ID or Vanity URL per line in the **Steam IDs / Vanity URLs** field. Vanity URLs are resolved to SteamID64 automatically during setup.

### Xbox setup

Xbox authentication requires a **free personal Azure AD app**. This is a one-time setup (~5 minutes). Microsoft restricts shared client IDs, so each installation needs its own.

#### Step 1 — Register an Azure AD app

1. Go to [https://portal.azure.com](https://portal.azure.com) and sign in with **the same Microsoft account you use for Xbox**
2. In the search bar type **App registrations** and select it
3. Click **New registration**
4. Fill in:
   - **Name**: anything you like (e.g. `HA Gaming Hub`)
   - **Supported account types**: select **Personal Microsoft accounts only**
   - Leave Redirect URI blank
5. Click **Register**
6. You are now on the app overview page — copy the **Application (client) ID** (a UUID like `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)
7. Go to the **Authentication** tab (left sidebar)
8. Scroll to **Advanced settings** → set **Allow public client flows** to **Yes**
9. Click **Save**

#### Step 2 — Configure in HA

During setup, paste the Application (client) ID in the **Xbox App Registration** step.

The integration will then use Microsoft's **Device Code Flow** — no password is stored in Home Assistant:

1. A short code and a URL (`https://microsoft.com/devicelogin`) are displayed
2. Open that URL in any browser, sign in with your Microsoft/Xbox account, and enter the code
3. Return to HA and click **Submit** — the integration verifies authorization
4. If not yet approved, you will see a "pending" message — wait a few seconds and click Submit again
5. Once authorized, your gamertag and tokens are saved securely in HA storage

If you want to skip Xbox for now, check **Skip Xbox setup** and submit. You can reconfigure the integration later to add it.

> **Security note:** tokens are stored in HA's internal storage (not in `configuration.yaml`). They are refreshed automatically before each poll.

### Presence entities

#### Per Steam account

| Entity | Type | Description |
| ------ | ---- | ----------- |
| `binary_sensor.gaming_hub_<steamid>_online` | Binary Sensor | `on` when the account is online (any state except Offline) |
| `sensor.gaming_hub_<steamid>_playing` | Sensor | Current game being played, or `—` if idle |
| `sensor.gaming_hub_<steamid>_status` | Sensor | Detailed status: `Online`, `Away`, `Busy`, `Snooze`, etc. |
| `sensor.gaming_hub_<steamid>_hours_recent` | Sensor | Hours played in the last 2 weeks |

#### Per Xbox account

| Entity | Type | Description |
| ------ | ---- | ----------- |
| `binary_sensor.gaming_hub_xbox_<xuid>_online` | Binary Sensor | `on` when the account is active on Xbox Live |
| `sensor.gaming_hub_xbox_<xuid>_playing` | Sensor | Current game or activity, or `—` if idle |

#### Aggregate

| Entity | Type | Description |
| ------ | ---- | ----------- |
| `binary_sensor.gaming_hub_someone_is_gaming` | Binary Sensor | `on` when **any** tracked account (Steam or Xbox) is actively playing a game |

### Example automations

```yaml
# Turn on a Hue light scene when someone starts gaming
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

# Send a notification when a specific player comes online
alias: Notify when friend comes online
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
