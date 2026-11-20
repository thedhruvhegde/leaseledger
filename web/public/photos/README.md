# Listing photos

The site currently ships **no listing photos**: `manifest.json` is `{}` and every card, detail view and landing tile
shows the generated street-map thumbnail of the block instead. The photo code path is kept so a licensed photo can be
added later without a code change.

## Rights note

Add a photo only if you have the right to show it: your own photo, written permission from the owner/manager (keep
it), or an explicit open license whose terms you follow. Never copy portal photos (Zillow, Apartments.com, Zumper …),
never use a picture of a different building as a stand-in, and never present a generated or edited image as the
property. Remove a photo immediately if an owner asks.

## Adding one

Put the file in `web/public/photos/<listing-id>/` and add an entry to `manifest.json`:

```json
{ "university-towers-2br": [{ "file": "exterior.jpg", "credit": "Jane Doe (own photo)", "source_url": "", "license": "Own photo", "position": "center 30%" }] }
```

The credit is shown as "Photo: <credit>" wherever the photo appears.
