# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
using a `0.x.0` scheme.

## [0.4.0] — 2026-08-19

Free Games now counts free **games**, and the list sensors stay inside the recorder's
attribute limit so their history is actually persisted.

### Fixed

- **State attributes no longer exceed the recorder's 16 KB limit.** `sensor.gaming_hub_free_games_count`
  serialised to **68 KB** (4.2× the limit) and `sensor.gaming_hub_deals` to **25 KB**. Above
  `MAX_STATE_ATTRS_BYTES` the recorder stores *no* attributes at all, so both entities logged a
  warning on every restart and came back from history with empty attributes:

  ```
  WARNING [homeassistant.components.recorder.db_schema] State attributes for
  sensor.gaming_hub_free_games_count exceed maximum size of 16384 bytes.
  ```

  Measured on live data after this release: free games count **11.7 KB (72% of the limit)**,
  deals **7.2 KB (44%)**.

- **`sensor.gaming_hub_free_games_count` counted DLC and loot keys as free games.** GamerPower
  returns every PC giveaway, and on a typical day ~80% are DLC or in-game loot key drops. The
  sensor reported ~96 "free games" when about 20 were actually games.

### Added

- **Giveaway types** option (Free Games step, default `game` + `early_access`) — which GamerPower
  giveaway types count as free games. Add `dlc`, `loot`, or `other` for the full firehose.
- **Max entries in card attributes** option (default `30`) — a deterministic ceiling on how many
  entries reach the `data` / `on_sale` attributes, independent of what the upstream APIs return.
- Automatic attribute trimming as a final safety net: the serialised payload is measured and
  trailing entries are dropped if it still would not fit. Logs at `debug` level when it trims.
- `early_access` is now its own giveaway type instead of being folded into `other`.

### Changed

- **Free games are ordered by expiry, soonest first**, with undated giveaways last. Anything that
  reads only the first N entries now keeps the ones that need attention.
- The attribute cap applies to the attribute payload only. The **sensor state, the calendar, and
  `binary_sensor.gaming_hub_free_game_expiring_soon` always see the full list**, so automations
  that count deals are unaffected by how many entries fit in the attributes.
- Watchlist-driven sensors (`price_tracker_deals`, `wishlist_games_on_sale`) get the safety net
  but no fixed cap — every entry there is a game you explicitly added.

### Removed

- `data[n].box_art_url` (Upcoming Media Card format). The card never read this field — it uses
  `poster`, falling back from `fanart` — and it was a third copy of the same URL, 16% of the payload.
  `on_sale[n].box_art_url` is unaffected and remains the image source for Nintendo Wishlist Card.
- `data[n].fanart` when identical to `poster`. It is still sent when the two genuinely differ
  (Epic entries), and Upcoming Media Card falls back to `poster` when it is absent.
- `on_sale[n].backgroundart`. Nintendo Wishlist Card tests this field for truthiness only, to pick
  a CSS background position — it never reads it as a URL, and renders the image from `box_art_url`.
  No data source provides a wide image distinct from the cover, so the field carried a duplicate
  URL worth 28% of the payload.

### Upgrade notes

- **`sensor.gaming_hub_free_games_count` will drop from ~96 to ~20** on first refresh. This is the
  corrected value, not a regression. Restore the old behaviour by adding `dlc` and `loot` under
  **Settings → Devices & Services → HA Gaming Hub → Reconfigure → Free Games**.
- Dashboards using `image_style: backgroundart` on Nintendo Wishlist Card take the card's other CSS
  branch. The image still renders, from `box_art_url`.
- No migration required. Existing config entries pick up the new defaults automatically.
- Prefer an uncapped payload with no history? Exclude the entities in `configuration.yaml` instead —
  see [Why the attribute lists are capped](README.md#why-the-attribute-lists-are-capped).

## [0.3.0] — 2026-07-09

### Fixed

- PSN and Xbox presence discovery on non-English Home Assistant instances ([#1]). Account discovery
  relied on hardcoded English `entity_id` suffixes (`_online_status`, `_now_playing`), which the
  native integrations generate from the *translated* friendly name — so on a non-English HA, PSN
  accounts never appeared in the config flow at all.
  - PSN account selection now uses an entity selector filtered to the `playstation_network`
    integration; sensors are resolved from the device by `translation_key` and stored as real
    `entity_id`s.
  - The Xbox now-playing fallback looks for a `media_player` on the same device instead of guessing
    English suffixes.
  - Existing English configurations keep working without reconfiguration.
- Manifest version was still `0.1.0`.

### Added

- Italian translation for the PSN config step.

Thanks to **@adamjthompson** for the detailed report.

## [0.2.0] — 2026-05-06

### Added

- **PlayStation Network support** via the native HA PlayStation Network integration — online status,
  current game, and session duration, matching Steam and Xbox.
- **Score sensor** (`sensor.gaming_hub_<slug>_score`) — Metacritic score via IsThereAnyDeal, with
  OpenCritic score as an attribute when present. Requires an ITAD API key.
- **Cost Per Hour sensor** (`sensor.gaming_hub_<slug>_cost_per_hour`) — best price ÷ main story
  hours from HowLongToBeat.
- **Session tracking** — `sensor.gaming_hub_<account>_session_duration` plus the
  `ha_gaming_hub_session_started` / `ha_gaming_hub_session_ended` events.
- **Watchlist services** — `ha_gaming_hub.add_to_watchlist` and `ha_gaming_hub.remove_from_watchlist`.
- **Deals Calendar** (`calendar.gaming_hub_deals`) — ITAD Flash Sales as calendar events. Requires
  an ITAD API key.
- **Free game expiry alert** (`binary_sensor.gaming_hub_free_game_expiring_soon`).

### Fixed

- CheapShark `/games` returns the field `price`, not `salePrice` — root cause of all
  "best price = $0.00" reports.
- `howlongtobeatpy` search no longer blocks the HA event loop.
- Game Pass / subscription $0 listings excluded from best price calculation.
- `sensor.gaming_hub_<slug>_best_price` state class corrected to `total` (`measurement` is invalid
  for a monetary device class).

### Changed

- **Breaking:** `sensor.gaming_hub_gaming_hub_deals` renamed to `sensor.gaming_hub_deals`. Home
  Assistant keys entities by `unique_id`, which did not change, so instances created before this
  release keep the old `entity_id` in their registry — rename it under **Settings → Entities** if
  you want the new one.

## [0.1.0] — 2026-04-25

Initial public release.

### Added

- **Free Games** module — Epic Games Store + GamerPower, with ⭐ Steam wishlist matching.
- **Price Tracker** module — CheapShark + optional ITAD, with Steam wishlist matching.
- **Presence** module — Steam and Xbox online status.
- Unified `sensor.gaming_hub_deals` combining free games and deals in one card.
- HA events for automations: new free game, deal found, historical low, friend online.
- Helper sensors: next expiry, wishlist deals count.
- Reconfigure support — change any setting without reinstalling.

[0.4.0]: https://github.com/nuggetz/ha-gaming-hub/releases/tag/v0.4.0
[0.3.0]: https://github.com/nuggetz/ha-gaming-hub/releases/tag/v0.3.0
[0.2.0]: https://github.com/nuggetz/ha-gaming-hub/releases/tag/v0.2.0
[0.1.0]: https://github.com/nuggetz/ha-gaming-hub/releases/tag/v0.1.0
[#1]: https://github.com/nuggetz/ha-gaming-hub/issues/1
