# Requests from the data agent

## 1. (optional, not blocking) `Listing.board_included: bool = False`
- What: a boolean on `Listing` meaning the charge includes food/board.
- Why: ICC co-op charges (icc-escher-single, icc-escher-double, icc-baker-double) cover "furnished room, internet, utilities, groceries, cleaning supplies". Without a flag the engine compares a rent+food price against rent-only prices, which makes co-ops look ~$300-400/mo more expensive than they are.
- Proposed code: `board_included: bool = False  # charge includes groceries/meals (ICC co-ops)`
- Workaround now: the fact is stated in each co-op listing's `notes`; the engine may key on `building_type == "coop"`.
